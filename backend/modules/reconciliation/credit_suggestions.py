"""Card-issuer credit auto-suggestion detector.

Card programs (Amex Platinum benefits, statement credits, cashback redemptions)
post inflows whose `raw_merchant_name` is the program name (e.g. "Platinum
Resy Credit", "Statement Credit", "Equinox Credit", "Reembolso digital"). The
charge they reimburse lives on the same account but under the merchant name
("Ambrosia"), so the same-account refund detector — which buckets by merchant
identity — never connects them.

This module finds those orphan credit rows, looks back 30 days on the same
account for an unpaired expense matching the credit's amount + currency, and
when there is *exactly one* candidate, emits a `credit_suggestion`
notification asking the user to confirm the link. Confirm → fires
`link_reimbursement_group`. Dismiss → never re-suggest. If either side gets
paired through some other path, the suggestion auto-resolves on the next tick.

Intentionally independent from `refunds.py`. Never auto-links: every
suggestion is gated on user confirmation.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.notifications.models import Notification
from modules.transactions.models import Transaction


# ----------------------------------------------------------------- patterns

# Brand-program tokens: a brand name followed (within a few words) by
# "credit". Matches "Platinum Resy Credit", "Uber Cash Credit", "SAKS Credit",
# "Streaming Credit", "Wireless Credit", "CLEAR Credit", "Equinox Credit",
# "Walmart+ Credit", "Dell Credit", "Hotel Credit", "Airline Credit",
# "Digital Entertainment Credit".
_BRAND_CREDIT_RE = re.compile(
    r"\b(resy|saks|equinox|walmart\+?|uber\s*cash|dell|clear|hotel|streaming"
    r"|wireless|digital\s+entertainment|airline)\b[\w\s\+&-]*\bcredit\b",
    re.IGNORECASE,
)

# Generic credit/cashback/reward/rebate/adjustment vocabulary.
_GENERIC_RE = re.compile(
    r"\b("
    r"statement\s+credit"
    r"|cash\s*back"
    r"|cashback"
    r"|rebate"
    r"|reembolso"  # ES — refund/credit
    r"|reward(s)?"
    r"|redemption"
    r"|adjustment"
    r")\b",
    re.IGNORECASE,
)

# Plain "credit" as a whole word — but reject "credit card" which is a card
# name (e.g. "Bank of America Credit Card"), not a credit transaction.
_PLAIN_CREDIT_RE = re.compile(r"\bcredit\b", re.IGNORECASE)
_CREDIT_CARD_RE = re.compile(r"\bcredit\s+card\b", re.IGNORECASE)


def is_credit_pattern_name(name: str | None) -> bool:
    """True if the raw merchant name looks like a card-issuer credit/program.

    Decisions:
      - "Platinum Resy Credit" → True (brand+credit)
      - "Statement Credit"     → True (generic)
      - "Cashback Reward"      → True (generic)
      - "Reembolso digital"    → True (ES generic)
      - "Equinox Credit"       → True (brand+credit)
      - "Bank of America Credit Card" → False (credit-card name guard)
      - "Best Buy" / "Trader Joe's" / "Amazon" → False
      - "Credit Card Statement" → False (still credit-card phrase)
    """
    if not name:
        return False
    s = name.strip()
    if not s:
        return False
    # Hard rejection: anything containing the literal "credit card" phrase.
    if _CREDIT_CARD_RE.search(s):
        return False
    if _BRAND_CREDIT_RE.search(s):
        return True
    if _GENERIC_RE.search(s):
        return True
    if _PLAIN_CREDIT_RE.search(s):
        return True
    return False


# ----------------------------------------------------------------- detection


@dataclass(frozen=True)
class CreditSuggestion:
    credit_txn_id: uuid.UUID
    counterpart_txn_id: uuid.UUID


_LOOKBACK_DAYS = 30


async def find_credit_suggestions(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = _LOOKBACK_DAYS,
) -> list[CreditSuggestion]:
    """Scan recent credit-pattern inflows and propose 1-to-1 reimbursements.

    Skips silently when there are 0 or >1 candidate counterparts (no nagging
    on ambiguous cases — the manual Vincular UX handles those).
    """
    now = datetime.now(timezone.utc)
    fresh_cutoff = now - timedelta(days=lookback_days)

    credits_q = await session.execute(
        select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.amount > 0,
            Transaction.bank_account_id.is_not(None),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.reimbursement_group_id.is_(None),
            Transaction.source_type.in_(("plaid", "connect")),
            Transaction.transaction_date >= fresh_cutoff,
        )
    )
    suggestions: list[CreditSuggestion] = []
    for credit in credits_q.scalars().all():
        if not is_credit_pattern_name(credit.raw_merchant_name):
            continue

        # One-sided lookback: charge must be on/before the credit, within 30d.
        window_start = credit.transaction_date - timedelta(days=lookback_days)
        cp_q = await session.execute(
            select(Transaction).where(
                Transaction.bank_account_id == credit.bank_account_id,
                Transaction.currency == credit.currency,
                Transaction.amount == -credit.amount,
                Transaction.id != credit.id,
                Transaction.transfer_pair_id.is_(None),
                Transaction.refund_pair_id.is_(None),
                Transaction.reimbursement_group_id.is_(None),
                Transaction.source_type.in_(("plaid", "connect")),
                Transaction.transaction_date >= window_start,
                Transaction.transaction_date <= credit.transaction_date,
            )
        )
        candidates = cp_q.scalars().all()
        if len(candidates) != 1:
            # 0 → nothing to suggest. >1 → ambiguous; let user use manual UX.
            continue
        suggestions.append(
            CreditSuggestion(credit_txn_id=credit.id, counterpart_txn_id=candidates[0].id)
        )
    return suggestions


# ----------------------------------------------------------------- emit/sync

NOTIFICATION_TYPE = "credit_suggestion"


async def _existing_suggestion_pairs(
    session: AsyncSession, user_id: uuid.UUID
) -> dict[tuple[str, str], Notification]:
    """Map (credit_id, counterpart_id) → Notification for every existing
    credit_suggestion (any status) belonging to this user. Used for both
    idempotency (skip dupes) and stale-resolution (mark dismissed when one
    side got paired some other way)."""
    res = await session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    out: dict[tuple[str, str], Notification] = {}
    for n in res.scalars().all():
        payload = n.payload or {}
        c = payload.get("credit_txn_id")
        p = payload.get("counterpart_txn_id")
        if c and p:
            out[(str(c), str(p))] = n
    return out


async def emit_credit_suggestions_for_household(
    session: AsyncSession, household_id: uuid.UUID
) -> dict[str, int]:
    """Run the detector for one household, insert new notifications (deduped),
    and auto-resolve stale ones (either txn already paired elsewhere).

    Returns {"created": int, "auto_resolved": int}.
    """
    suggestions = await find_credit_suggestions(session, household_id)

    # Auto-resolve stale ones: any pending suggestion whose credit OR
    # counterpart now has a non-null pair_id gets dismissed quietly.
    now = datetime.now(timezone.utc)
    auto_resolved = 0
    created = 0

    # Group suggestions by user (credit txn owner) so we can compare against
    # that user's existing notifications.
    if not suggestions:
        # Even with zero new suggestions, do a sweep for stale pending ones.
        pass

    # We need user_ids for new suggestions. Fetch the credits in one go.
    credit_ids = {s.credit_txn_id for s in suggestions}
    credit_rows: dict[uuid.UUID, Transaction] = {}
    if credit_ids:
        res = await session.execute(select(Transaction).where(Transaction.id.in_(credit_ids)))
        credit_rows = {t.id: t for t in res.scalars().all()}

    # Cache existing-suggestions per user_id to avoid N queries.
    by_user_existing: dict[uuid.UUID, dict[tuple[str, str], Notification]] = {}

    async def _get_existing(uid: uuid.UUID):
        if uid not in by_user_existing:
            by_user_existing[uid] = await _existing_suggestion_pairs(session, uid)
        return by_user_existing[uid]

    # 1. Stale-resolution sweep: any pending notification for this household's
    # users where either txn is now paired → dismiss.
    # (We only know "this household" via the credit txn's household_id; we
    # iterate all members' notifications.)
    from modules.households.models import HouseholdMember

    member_ids_q = await session.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    member_user_ids = [r[0] for r in member_ids_q.all()]

    for uid in member_user_ids:
        existing = await _get_existing(uid)
        for (c_id, p_id), notif in existing.items():
            if notif.status in ("dismissed", "actioned"):
                continue
            # Re-check the underlying txns.
            res = await session.execute(
                select(Transaction).where(Transaction.id.in_([uuid.UUID(c_id), uuid.UUID(p_id)]))
            )
            txns = list(res.scalars().all())
            if len(txns) < 2:
                # One side got deleted — auto-resolve.
                notif.status = "dismissed"
                notif.updated_at = now
                auto_resolved += 1
                continue
            stale = any(
                (
                    t.transfer_pair_id is not None
                    or t.refund_pair_id is not None
                    or t.reimbursement_group_id is not None
                )
                for t in txns
            )
            if stale:
                notif.status = "dismissed"
                notif.updated_at = now
                auto_resolved += 1

    # 2. Insert new suggestions (deduped).
    # Need counterpart rows too for payload.
    cp_ids = {s.counterpart_txn_id for s in suggestions}
    cp_rows: dict[uuid.UUID, Transaction] = {}
    if cp_ids:
        res = await session.execute(select(Transaction).where(Transaction.id.in_(cp_ids)))
        cp_rows = {t.id: t for t in res.scalars().all()}

    for s in suggestions:
        credit = credit_rows.get(s.credit_txn_id)
        counterpart = cp_rows.get(s.counterpart_txn_id)
        if credit is None or counterpart is None:
            continue
        existing = await _get_existing(credit.user_id)
        key = (str(s.credit_txn_id), str(s.counterpart_txn_id))
        if key in existing:
            continue  # idempotent

        amount = abs(float(credit.amount))
        title = (
            f"¿Vincular '{credit.raw_merchant_name}' "
            f"{credit.currency} {amount:.2f} con "
            f"'{counterpart.raw_merchant_name}'?"
        )
        payload = {
            "credit_txn_id": str(credit.id),
            "counterpart_txn_id": str(counterpart.id),
            "amount": amount,
            "currency": credit.currency,
            "merchant_credit_name": credit.raw_merchant_name,
            "merchant_counterpart_name": counterpart.raw_merchant_name,
            "credit_date": credit.transaction_date.isoformat(),
            "counterpart_date": counterpart.transaction_date.isoformat(),
            "bank_account_id": str(credit.bank_account_id) if credit.bank_account_id else None,
            "household_id": str(credit.household_id),
        }
        notif = Notification(
            user_id=credit.user_id,
            type=NOTIFICATION_TYPE,
            title=title,
            payload=payload,
            status="unread",
        )
        session.add(notif)
        created += 1
        # update local cache so a follow-up identical pair within this run
        # doesn't double-insert.
        by_user_existing.setdefault(credit.user_id, {})[key] = notif

    await session.flush()
    return {"created": created, "auto_resolved": auto_resolved}
