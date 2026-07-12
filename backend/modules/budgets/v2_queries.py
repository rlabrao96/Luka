"""Budget v2 — async DB fetchers (split from v2_service, see H16).

Everything here reads; nothing writes. The orchestrators in ``v2_service``
compose these into the response. Keep the privacy invariant in mind: income
queries stay in ``modules.households.contribution_service`` — do NOT add
income reads here.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.dates import (
    month_bounds_datetime as _month_bounds_datetime,
    prior_month as _prior_month,
)
from modules.budgets.forecast import category_stats
from modules.budgets.savings_categories import is_savings_category
from modules.budgets.user_budget_settings_service import (
    get_household_savings_target,
    get_payday_day_of_month,
    get_savings_target,
)
from modules.subscriptions.read import (
    get_household_unpaid_known_bills,
    get_user_shared_unpaid_known_bills,
)
from modules.households.models import HouseholdMember
from modules.transactions.models import Transaction, TransactionSplit
from modules.transactions.totals import counts_toward_totals_clauses

_ZERO = Decimal("0")


# ---------------------------------------------------------- reimbursement bills


async def _reimbursement_members_known_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
    month: date,
) -> Decimal:
    """Sum of SHARED unpaid-this-month known_bills for members in `reimbursement`
    mode.

    These bills don't hit the household pot — we subtract them from the
    household known_bills sum in the household view. We subtract
    unpaid-this-month to stay symmetrical with the (now unpaid-adjusted)
    household aggregate; otherwise the subtraction would remove scheduled
    amounts from a total that only counted unpaid ones, dragging the
    household figure below its true unpaid remainder.
    """
    rows = await db.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
            HouseholdMember.contribution_mode == "reimbursement",
        )
    )
    total = _ZERO
    for (user_id,) in rows:
        total += await get_user_shared_unpaid_known_bills(db, user_id, currency, month)
    return total


# ------------------------------------------------------- caller ratio share


async def _caller_ratio_share(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Decimal:
    """Return the caller's share of shared outflows as a fraction in [0, 1].

    Maps `households.split_ratio[i]` (percentages summing to 100) to the i-th
    active member in `joined_at ASC` order, matching the settlement logic in
    `modules.households.service.calculate_settlement`. Falls back to 1/N equal
    split if the ratio is missing or shorter than the active member list.
    """
    ratio_row = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    split_ratio = ratio_row.scalar_one_or_none() or []

    member_rows = await db.execute(
        text(
            """
            SELECT user_id FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
            ORDER BY joined_at ASC
            """
        ),
        {"hid": str(household_id)},
    )
    members = [r[0] for r in member_rows]
    if not members:
        return _ZERO

    try:
        idx = members.index(user_id)
    except ValueError:
        return _ZERO

    if idx < len(split_ratio) and sum(split_ratio) > 0:
        return Decimal(split_ratio[idx]) / Decimal(sum(split_ratio))
    return Decimal(1) / Decimal(len(members))


async def _household_shared_outflows(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> Decimal:
    """Household's total shared outflows this month = shared MTD expenses
    (absolute) + household unpaid shared bills. Drives the personal view's
    `Gastos del hogar` bucket via the caller's ratio."""
    first_day, first_day_next, _ = _month_bounds_datetime(month)
    row = await db.execute(
        select(func.coalesce(func.sum(func.abs(Transaction.amount)), 0))
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .where(
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
            TransactionSplit.split_type == "shared",
        )
    )
    shared_spent = Decimal(str(row.scalar() or 0))
    unpaid_bills = await get_household_unpaid_known_bills(db, household_id, currency, month)
    return shared_spent + unpaid_bills


# ---------------------------------------------------------------- spent


def _personal_spent_expr(user_id: uuid.UUID, currency: str):
    """(joins, expression) for the personal view's effective spent amount.

    Trip-linked transactions count at the CALLER'S share, not the full
    amount (Task 6.4): a $90 group dinner you fronted with a $30 share adds
    $30 to your personal spending. trip_expense_splits.share_amount is in
    MAJOR units (trip-ledger convention) — scale to the transaction table's
    minor units. A trip-linked row where the caller has NO share counts 0.
    """
    from sqlalchemy import and_, case

    from modules.currencies.units import minor_units_per_major
    from modules.trips.models import TripAttendee, TripExpense, TripExpenseSplit

    scale = minor_units_per_major(currency)
    joins = [
        (
            TripExpense,
            and_(
                TripExpense.transaction_id == Transaction.id,
                TripExpense.deleted_at.is_(None),
            ),
        ),
        (
            TripExpenseSplit,
            and_(
                TripExpenseSplit.trip_expense_id == TripExpense.id,
                TripExpenseSplit.attendee_id.in_(
                    select(TripAttendee.id)
                    .where(
                        TripAttendee.trip_id == TripExpense.trip_id,
                        TripAttendee.user_id == user_id,
                    )
                    .scalar_subquery()
                ),
            ),
        ),
    ]
    expr = case(
        (TripExpense.id.is_(None), func.abs(Transaction.amount)),
        else_=func.coalesce(TripExpenseSplit.share_amount, 0) * scale,
    )
    return joins, expr


async def _month_category_sums(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> list[tuple[str | None, Decimal]]:
    """Per-category expense totals for the month — SQL aggregation.

    Returns ``[(category, sum_abs_amount), ...]``. Every consumer only needs
    category sums; the previous version hydrated FULL ORM rows (hundreds per
    household-month, twice per dashboard load).

    Both views filter by effective split_type: household → shared, personal →
    personal. This keeps the two Sankeys additive — a shared expense belongs
    to Hogar and to the personal view's `Gastos del hogar` bucket (via the
    ratio), never to the personal Level-3 category breakdown.
    """
    first_day, first_day_next, _ = _month_bounds_datetime(month)
    # Email-ingested transactions on non-joint accounts have no transaction_splits
    # row at ingestion time (see jobs/tasks.py). The frontend treats a NULL split
    # as "personal", so we do the same here via LEFT JOIN + NULL coalesce —
    # otherwise ~every email-ingested expense drops out of the personal view.
    if view == "personal":
        trip_joins, spent_expr = _personal_spent_expr(user_id, currency)
        base = (
            select(Transaction.category, func.sum(spent_expr).label("total"))
            .group_by(Transaction.category)
            .select_from(Transaction)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        )
        for target, onclause in trip_joins:
            base = base.outerjoin(target, onclause)
        base = base.where(
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
            (TransactionSplit.split_type == "personal") | (TransactionSplit.split_type.is_(None)),
        )
    else:
        base = (
            select(Transaction.category, func.sum(func.abs(Transaction.amount)).label("total"))
            .group_by(Transaction.category)
            .select_from(Transaction)
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
                TransactionSplit.split_type == "shared",
            )
        )
    r = await db.execute(base)
    return [(row[0], Decimal(str(row[1] or 0))) for row in r.all()]


# --------------------------------------------------- historical category stats


async def _three_month_category_stats(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> dict[str, tuple[Decimal, Decimal, int]]:
    """Return per-category (mean, pstdev, n) over the 3 preceding months.

    Savings-equivalent categories are excluded from this — they're not
    "spending risk". ONE query grouped by (month, category) instead of the
    old three sequential per-month queries (M20).
    """
    window_start, _, _ = _month_bounds_datetime(_prior_month(month, 3))
    current_start, _, _ = _month_bounds_datetime(month)
    month_expr = func.date_trunc("month", Transaction.transaction_date).label("month_start")

    # Luka stores expense amounts as negative Decimals; abs() so category
    # totals come out positive for the downstream share×CV math (mean/std/cap).
    # Personal view uses LEFT JOIN so email-ingested txns with no split row
    # (treated as "personal" in the UI) don't drop out.
    if view == "personal":
        trip_joins, spent_expr = _personal_spent_expr(user_id, currency)
        q = (
            select(
                month_expr,
                Transaction.category,
                func.coalesce(func.sum(spent_expr), 0).label("total"),
            )
            .select_from(Transaction)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        )
        for target, onclause in trip_joins:
            q = q.outerjoin(target, onclause)
        q = q.where(
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= window_start,
            Transaction.transaction_date < current_start,
            (TransactionSplit.split_type == "personal") | (TransactionSplit.split_type.is_(None)),
        )
    else:
        q = (
            select(
                month_expr,
                Transaction.category,
                func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("total"),
            )
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= window_start,
                Transaction.transaction_date < current_start,
                TransactionSplit.split_type == "shared",
            )
        )
    q = q.group_by(month_expr, Transaction.category)

    per_category: dict[str, list[Decimal]] = {}
    rows = await db.execute(q)
    for _month_start, category, total in rows:
        if not category or is_savings_category(category):
            continue
        per_category.setdefault(category, []).append(Decimal(str(total)))

    stats: dict[str, tuple[Decimal, Decimal, int]] = {}
    for category, totals in per_category.items():
        stats[category] = category_stats(totals)
    return stats


# ------------------------------------------------------------------ caps


async def _category_caps(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> dict[str, Decimal]:
    """Return per-category monthly caps in `currency` for this month.

    Caps are stored per-currency in `category_budgets`; a USD cap on a
    category is ignored by the CLP view and vice versa. Callers get a plain
    `{category: amount}` dict, same shape as before."""
    rows = await db.execute(
        text(
            """
            SELECT category, amount FROM category_budgets
            WHERE household_id = :hid AND month = :month AND currency = :ccy
            """
        ),
        {"hid": str(household_id), "month": month, "ccy": currency},
    )
    return {r[0]: Decimal(str(r[1])) for r in rows}


# ------------------------------------------------------------ daily burn (14d)


async def _daily_burn_14d(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Trailing 14-day average of non-savings expense spend for this scope."""
    today = datetime.now(timezone.utc)
    fourteen_days_ago = today - timedelta(days=14)

    if view == "personal":
        # LEFT JOIN so email-ingested txns with no split row are included.
        trip_joins, spent_expr = _personal_spent_expr(user_id, currency)
        q = (
            select(Transaction.category, func.sum(spent_expr))
            .group_by(Transaction.category)
            .select_from(Transaction)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        )
        for target, onclause in trip_joins:
            q = q.outerjoin(target, onclause)
        q = q.where(
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= fourteen_days_ago,
            Transaction.transaction_date <= today,
            (TransactionSplit.split_type == "personal") | (TransactionSplit.split_type.is_(None)),
        )
    else:
        q = (
            select(Transaction.category, func.sum(func.abs(Transaction.amount)))
            .group_by(Transaction.category)
            .select_from(Transaction)
            .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= fourteen_days_ago,
                Transaction.transaction_date <= today,
                TransactionSplit.split_type == "shared",
            )
        )
    rows = await db.execute(q)

    total = _ZERO
    for category, amt in rows.all():
        if is_savings_category(category):
            continue
        total += Decimal(str(amt or 0))
    return (total / Decimal("14")) if total > _ZERO else _ZERO


# ----------------------------------------------------- currencies available


async def _currencies_available(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
) -> list[str]:
    """Distinct currencies across transactions for the scope. Sorted asc."""
    q = (
        select(Transaction.currency)
        .where(
            Transaction.household_id == household_id,
        )
        .distinct()
    )
    if view == "personal":
        q = q.where(Transaction.user_id == user_id)
    rows = await db.execute(q)
    currencies = sorted({c for (c,) in rows if c})
    # Always include at least the user's fallback; never return empty list.
    return currencies or []


# ---------------------------------------------------- savings target (settings)


async def _personal_savings_target(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Read the caller's savings target via `user_budget_settings_service`.

    Returns Decimal('0') if no row exists or the row is in a different currency.
    """
    return await get_savings_target(db, user_id=user_id, currency=currency)


async def _household_savings_target(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum savings targets across members whose contribution_mode ∈ {full, fixed}.

    Delegates to `user_budget_settings_service.get_household_savings_target`,
    which excludes reimbursement members per spec Section 5.2.
    """
    return await get_household_savings_target(db, household_id=household_id, currency=currency)


# -------------------------------------------------- payday → days_to_payday


async def _days_to_payday(
    db: AsyncSession,
    user_id: uuid.UUID,
    month: date,
    days_in_month: int,
) -> int:
    """Days from today until the user's next payday.

    If `user_budget_settings.payday_day_of_month` is unset we fall back to
    end-of-month. Clamps to `days_in_month` for short months (e.g. feb 30→28).
    """
    payday_day = await get_payday_day_of_month(db, user_id=user_id)
    today = datetime.now(timezone.utc).date()
    # If we're not viewing the current month, return days_in_month as a stub.
    if not (today.year == month.year and today.month == month.month):
        return days_in_month

    if payday_day is None:
        # Fall back: next payday = end of month.
        payday_day = days_in_month

    payday_day_clamped = min(int(payday_day), days_in_month)
    if today.day <= payday_day_clamped:
        return payday_day_clamped - today.day
    # Payday has passed this month → next payday in next month
    nxt_year, nxt_month = (
        (month.year + 1, 1) if month.month == 12 else (month.year, month.month + 1)
    )
    nxt_days = calendar.monthrange(nxt_year, nxt_month)[1]
    nxt_payday_clamped = min(int(payday_day), nxt_days)
    days_left_this_month = days_in_month - today.day
    return days_left_this_month + nxt_payday_clamped
