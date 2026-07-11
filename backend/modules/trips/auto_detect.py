"""Trip settlement auto-detect — Phase 6 Tasks 6.0 + 6.2 + 6.3.

When a freshly-inserted ``transactions`` row looks like a settlement payment
between Luka attendees on a trip with non-zero outstanding balance, write a
``notifications`` row of type ``trip_settlement_suggestion`` so the user can
confirm/dismiss from the Saldos tab or global notifications inbox.

Spec reference: ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.7.

────────────────────────────────────────────────────────────────────────────
Discovery findings (Task 6.0)
────────────────────────────────────────────────────────────────────────────

1) **Post-insert hook surface for transactions.**

   There is **no** centralized SQLAlchemy ``after_insert`` event listener and
   no single "post_process_transaction" gateway. ``Transaction`` rows are
   inserted at four distinct entry points:

   - ``backend/jobs/tasks.py:421`` — email parser (Gmail/Outlook ingestion job).
   - ``backend/modules/plaid/sync.py:228`` — Plaid sync worker.
   - ``backend/modules/bank_connect/router.py:413`` — Luka Connect (bank
     scraping) ingestion.
   - ``backend/modules/whatsapp/handler.py:354`` — manual expense via WhatsApp.

   Each path has its own commit/flush sequence. To stay non-blocking and
   minimise risk we wire ``try_match_settlement`` only into the **central**
   path that is actually relevant for settlement detection: the Plaid sync
   path (``modules/plaid/sync.py``) — Zelle / Venmo / CashApp settlements
   land via Plaid for US users in v1. Email and bank_connect paths can be
   added in v2 once the heuristic is validated; for v1 we additionally hook
   the WhatsApp handler so manual-entered settlements also trigger.

   Every call site wraps the invocation in ``try/except`` so a trip module
   error never blocks the underlying transaction insert.

2) **Notifications module.**

   ``backend/modules/notifications/models.py`` — ``Notification`` row has:
   ``user_id, type:str (free string, no enum), title:str, payload:JSONB,
   status:str (default "unread"), created_at, updated_at, read_at``.

   ``backend/modules/notifications/service.py:create_notification(db, user_id,
   type, title, payload=None)`` — commits internally. Since ``type`` is a
   free string column, **no migration** is required to introduce
   ``"trip_settlement_suggestion"``.

3) **Subscription detection — for excluding subscriptions from suggestions.**

   There is **no** ``subscription_id`` foreign-key on ``transactions`` (the
   spec language is aspirational). Subscriptions are detected dynamically
   from transaction history and cached in
   ``detected_subscriptions_cache(user_id PK, result_json JSONB)`` —
   ``backend/modules/subscriptions/service.py:127``. Each cached item carries
   a ``merchant_name`` field (matched against
   ``COALESCE(merchants.normalized_name, transactions.raw_merchant_name)``).

   For the suggestions inbox we exclude any transaction whose merchant key
   matches an active item in this cache. v2 hardening: real ``subscription_id``
   FK column once the subscriptions module is normalised.

4) **Person / wallet / Zelle-Venmo detection.**

   ``backend/modules/reconciliation/wallets.py`` handles wallet-funding
   transfer detection (BofA→Venmo same-amount pairs), but does **not** expose
   a "is this counterparty a Luka user" helper. There is no canonical
   "person detection" function.

   For v1 we use a simple substring heuristic: a transaction is a settlement
   candidate if ``transactions.raw_merchant_name`` (case-insensitive)
   contains the attendee's ``display_name`` OR the attendee's ``full_name``
   first token, OR vice versa. v2 hardening: full-name tokenisation +
   nickname expansion + Plaid counterparty extraction. Tracked in
   ``NEXT-STEPS.md``.

5) **Budget aggregator.**

   ``backend/modules/budgets/v2_service.py:_fetch_month_transactions`` (line
   234) computes per-category totals by joining ``transactions`` ↔
   ``transaction_splits`` and filtering on ``split_type``. The full
   ``Transaction.amount`` is summed — there is no per-row share cut. The
   household-shared path uses the same full amount because
   ``TransactionSplit`` carries a category (``shared``/``personal``) but
   not a ``share_amount`` — household share splitting happens via aggregate
   queries on ``BankAccount.account_type=='joint'`` rather than per-row
   share carving.

   Trip splits live in ``trip_expense_splits.share_amount`` and represent
   a fundamentally different shape (the user's portion of a single transaction).
   The v2_service aggregator does NOT consume ``trip_expense_splits`` today.

   Decision (Task 6.4): the existing Sankey/category aggregator is large
   (>1500 lines, multiple call sites) and reaches into stats / forecasts.
   Extending it to honour ``trip_expense_splits`` is non-trivial — it needs
   a new LEFT JOIN against ``trip_expenses + trip_expense_splits`` plus
   logic that maps the caller's user to a ``TripAttendee.id`` for the
   share-amount lookup. Per the plan's option (b) we mark the integration
   test ``xfail`` with a tracked TODO in ``NEXT-STEPS.md`` — the v1.1
   follow-up will refactor the budget queries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.notifications import service as notifications_service
from modules.transactions.models import Transaction
from modules.trips.balances import compute_balances
from modules.trips.models import (
    Trip,
    TripAttendee,
    TripSettlementDismissal,
)


logger = logging.getLogger(__name__)


_TOLERANCE_RATIO = Decimal("0.05")
# Absolute tolerance cap in MAJOR units, scaled per currency: 5.00 is a
# meaningful cap for USD but microscopic for CLP/COP (≈ USD 0.005), where it
# degraded matching to near-exact only. ~5 USD equivalents, coarse on purpose.
_TOLERANCE_FLOOR_BY_CURRENCY = {
    "CLP": Decimal("5000"),
    "COP": Decimal("20000"),
    "MXN": Decimal("100"),
    "PEN": Decimal("20"),
    "BRL": Decimal("25"),
}
_TOLERANCE_FLOOR_DEFAULT = Decimal("5.00")
_DATE_TAIL_DAYS = 30


def _name_match(raw_merchant: Optional[str], attendee_name: Optional[str]) -> bool:
    """Case-insensitive substring match in either direction.

    Spec §4.7 reuses "the existing merchant-cleaning + person-detection
    logic" — but no such helper exists today (see file docstring item 4).
    The simple substring check works for the most common cases (Zelle to
    "JOHN DOE", Venmo "Cashing out to John D"). v2 hardening: tokenised
    full-name match + nickname expansion + Plaid counterparty.id lookup.
    """
    if not raw_merchant or not attendee_name:
        return False
    a = raw_merchant.strip().lower()
    b = attendee_name.strip().lower()
    if not a or not b:
        return False
    if b in a or a in b:
        return True
    # First-token match on the attendee name (handles "JOHN DOE" → "JOHN").
    first = b.split()[0] if b.split() else ""
    return bool(first and len(first) >= 3 and first in a)


async def _is_dismissed(db: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID) -> bool:
    res = await db.execute(
        select(TripSettlementDismissal).where(
            TripSettlementDismissal.user_id == user_id,
            TripSettlementDismissal.transaction_id == transaction_id,
        )
    )
    return res.scalar_one_or_none() is not None


def _within_tolerance(
    amount_abs: Decimal, outstanding_abs: Decimal, currency: str | None = None
) -> bool:
    """``|amount - outstanding| <= min(5% of outstanding, ~5 USD equivalent)``."""
    if outstanding_abs <= Decimal("0"):
        return False
    delta = abs(amount_abs - outstanding_abs)
    floor = _TOLERANCE_FLOOR_BY_CURRENCY.get((currency or "").upper(), _TOLERANCE_FLOOR_DEFAULT)
    tol = min(outstanding_abs * _TOLERANCE_RATIO, floor)
    return delta <= tol


async def try_match_settlement(
    db: AsyncSession,
    transaction: Transaction,
) -> list[uuid.UUID]:
    """Inspect ``transaction``; emit notifications for matching trips.

    Returns the IDs of any notifications created, for tracing/logging.

    All checks are non-blocking — caller wraps in ``try/except`` so a
    failure here never breaks the underlying transaction insert.
    """
    notifications_created: list[uuid.UUID] = []

    # Filter 1: settlement candidates are real expense/income only.
    if transaction.transaction_type not in ("expense", "income"):
        return notifications_created

    # Filter 2: the user must be marked dismissed once globally.
    if await _is_dismissed(db, transaction.user_id, transaction.id):
        return notifications_created

    txn_date = transaction.transaction_date
    if hasattr(txn_date, "date"):
        txn_date_d: date = txn_date.date()
    else:
        txn_date_d = txn_date  # type: ignore[assignment]

    # Find every active trip the user is on whose date window covers this txn.
    user_trips_q = (
        select(Trip, TripAttendee)
        .join(TripAttendee, TripAttendee.trip_id == Trip.id)
        .where(
            TripAttendee.user_id == transaction.user_id,
            TripAttendee.left_at.is_(None),
            Trip.status != "archived",
        )
    )
    rows = (await db.execute(user_trips_q)).all()

    # Transactions store non-zero-decimal currencies in cents, but the trip
    # ledger (compute_balances + trip_settlements) is in major units. Convert
    # at the boundary so the tolerance check + suggested amount line up.
    from modules.trips.service import _txn_amount_to_major

    abs_amount = _txn_amount_to_major(abs(Decimal(transaction.amount)), transaction.currency or "")

    for trip, my_attendee in rows:
        # Filter 3: date window check (start_date..end_date+30d).
        window_end = trip.end_date + timedelta(days=_DATE_TAIL_DAYS)
        if not (trip.start_date <= txn_date_d <= window_end):
            continue

        # v1 single-currency: skip cross-currency match attempts. The
        # transaction must be in the trip's base currency (or fall back to
        # raw match — we keep the simpler rule for v1).
        if (transaction.currency or "").upper() != trip.base_currency.upper():
            continue

        # Need attendees on this trip OTHER than the caller, with a
        # *Luka identity* (user_id IS NOT NULL) so we can name-match.
        attendees_q = select(TripAttendee).where(
            TripAttendee.trip_id == trip.id,
            TripAttendee.user_id.isnot(None),
            TripAttendee.id != my_attendee.id,
        )
        attendees = (await db.execute(attendees_q)).scalars().all()
        if not attendees:
            continue

        # Resolve full names once for the substring heuristic.
        ids = [a.user_id for a in attendees if a.user_id is not None]
        users_by_id: dict[uuid.UUID, User] = {}
        if ids:
            uq = select(User).where(User.id.in_(ids))
            for u in (await db.execute(uq)).scalars():
                users_by_id[u.id] = u

        # Compute balances once per trip.
        balances = await compute_balances(trip.id, db)
        own_attendee_ids = {my_attendee.id}
        my_net = sum(
            (Decimal(b.net_in_base) for b in balances if b.attendee_id in own_attendee_ids),
            Decimal("0"),
        )

        # For each non-self Luka attendee, see if name matches.
        for other in attendees:
            full = (
                users_by_id.get(other.user_id).full_name if other.user_id in users_by_id else None
            )
            if not (
                _name_match(transaction.raw_merchant_name, other.display_name)
                or _name_match(transaction.raw_merchant_name, full)
            ):
                continue

            # Outstanding balance between caller and ``other`` (pairwise net
            # is approximated by my own net's sign — v1 keeps it simple:
            # `expense` outflow → user is paying down debt → my_net should
            # be negative; `income` inflow → user is receiving payment →
            # my_net should be positive). The spec treats this as a single
            # net per pair which we approximate by the caller's overall net
            # for v1 (single counterparty trips are the dominant case).
            outstanding_abs = abs(my_net)
            if outstanding_abs <= Decimal("0"):
                continue

            # Direction sanity: expense (negative amount) → caller is paying
            # → caller must be a debtor (my_net < 0); income → creditor.
            if transaction.transaction_type == "expense" and my_net >= 0:
                continue
            if transaction.transaction_type == "income" and my_net <= 0:
                continue

            if not _within_tolerance(abs_amount, outstanding_abs, transaction.currency):
                continue

            # Match! Emit the notification.
            payload = {
                "trip_id": str(trip.id),
                "trip_name": trip.name,
                "from_attendee_id": str(
                    my_attendee.id if transaction.transaction_type == "expense" else other.id
                ),
                "to_attendee_id": str(
                    other.id if transaction.transaction_type == "expense" else my_attendee.id
                ),
                "transaction_id": str(transaction.id),
                "suggested_amount": str(abs_amount.quantize(Decimal("0.01"))),
                "currency": trip.base_currency,
            }
            title = f"Posible pago a {other.display_name} en {trip.name}"
            notif = await notifications_service.create_notification(
                db,
                user_id=transaction.user_id,
                type="trip_settlement_suggestion",
                title=title,
                payload=payload,
            )
            notifications_created.append(notif.id)
            # One notification per trip — break the inner attendee loop.
            break

    return notifications_created
