"""Contribution mode service.

Owns the logic that decides how each household member's income contributes
to the household pot, based on their `contribution_mode`:

- ``full``          — full real income counts toward the household pot
- ``fixed``         — only ``fixed_contribution_amount`` counts; real income is private
- ``reimbursement`` — nothing counts; the member keeps their own expenses separate

PRIVACY INVARIANT
-----------------
For members with ``contribution_mode='fixed'``, this module NEVER queries
or returns their real income. The dispatch in ``income_for_household_view``
is structured so that a ``fixed`` branch cannot fall through to a real-income
query; any refactor must preserve this by construction (not by chance).

This module was extracted from ``modules.budgets.v2_service`` by Chunk D of
the budget-v2 sprint. The previous inline implementation lived at
``v2_service._real_income_for_user`` / ``v2_service._household_income``;
behavior is identical and the pytest suite
``tests/test_budget_v2_endpoint.py`` is the end-to-end regression gate.
Additional unit-level regressions live in ``tests/test_contribution_modes.py``.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.transactions.models import Transaction
from modules.transactions.totals import counts_toward_totals_clauses


_ZERO = Decimal("0")
_VALID_MODES = frozenset({"full", "fixed", "reimbursement"})


# --------------------------------------------------------------- month bounds


def _month_bounds_datetime(month: date) -> tuple[datetime, datetime]:
    """Return ``(first_day, first_day_next)`` as UTC datetimes.

    Kept local so this module has no back-reference to `v2_service`.
    """
    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    if month.month == 12:
        next_year, next_month = month.year + 1, 1
    else:
        next_year, next_month = month.year, month.month + 1
    first_day_next = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
    # Touch calendar to ensure the tuple is a valid month (no KeyError surprises).
    calendar.monthrange(month.year, month.month)
    return first_day, first_day_next


# --------------------------------------------------------------- dataclasses


@dataclass
class OtherMemberContribution:
    user_id: uuid.UUID
    display_name: str
    amount: Decimal
    mode: str  # "full" | "fixed"


@dataclass
class HouseholdIncomeBreakdown:
    total: Decimal
    caller_sources: dict[str, Decimal] = field(default_factory=dict)
    caller_other_income: Decimal = field(default_factory=lambda: _ZERO)
    other_members: list[OtherMemberContribution] = field(default_factory=list)


# --------------------------------------------------------------- personal view


async def income_for_personal_view(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> Decimal:
    """Return the caller's own real income for the month.

    Personal view always shows real income — the ``fixed`` redaction only
    applies to the household view, where one member must not see another
    member's raw income.

    Sum is over ``Transaction`` rows with ``transaction_type='income'``
    scoped to ``(user_id, household_id, currency, month)``.
    """
    first_day, first_day_next = _month_bounds_datetime(month)
    q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user_id,
        Transaction.household_id == household_id,
        Transaction.transaction_type == "income",
        *counts_toward_totals_clauses(),
        Transaction.currency == currency,
        Transaction.transaction_date >= first_day,
        Transaction.transaction_date < first_day_next,
    )
    r = await db.execute(q)
    raw = r.scalar() or 0
    return Decimal(str(raw))


# -------------------------------------------------------------- household view


async def income_for_household_view(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> Decimal:
    """Return household income total, contribution-mode-aware.

    Per-member dispatch::

        full          -> income_for_personal_view (real income in currency)
        fixed         -> fixed_contribution_amount (only if fixed_contribution_currency == currency)
        reimbursement -> 0

    PRIVACY INVARIANT: the ``fixed`` branch never touches the member's
    real income. If you refactor this, preserve that property by construction.
    """
    member_rows = await db.execute(
        select(
            HouseholdMember.user_id,
            HouseholdMember.contribution_mode,
            HouseholdMember.fixed_contribution_amount,
            HouseholdMember.fixed_contribution_currency,
        ).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )

    total = _ZERO
    for user_id, mode, fixed_amount, fixed_currency in member_rows:
        if mode == "full":
            total += await income_for_personal_view(
                db,
                user_id=user_id,
                household_id=household_id,
                month=month,
                currency=currency,
            )
        elif mode == "fixed":
            # PRIVACY: we never read the fixed member's real income.
            if fixed_amount is not None and fixed_currency == currency:
                total += Decimal(str(fixed_amount))
        else:
            # reimbursement (or any unknown future mode) -> 0
            continue
    return total


# ------------------------------------------------ caller-relative breakdown


async def income_breakdown_for_household_view(
    db: AsyncSession,
    *,
    caller_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> HouseholdIncomeBreakdown:
    """Return a caller-relative breakdown of household income for the month.

    PRIVACY INVARIANT
    -----------------
    - Caller's sources are computed from their own transactions + their own
      user_category_preferences, so only the caller sees their category mix.
    - For every non-caller active member:
        * full          -> read real income via income_for_personal_view
        * fixed         -> read fixed_contribution_amount only; NEVER touch
                           their real income transactions
        * reimbursement -> skipped (contributes $0 to the pot)
    - `total` equals the sum of caller_sources + caller_other_income +
      other_members amounts. Note this differs from `income_for_household_view`
      when the caller's own contribution_mode is `fixed` or `reimbursement`:
      the breakdown always shows the caller's REAL income (personal-view
      semantics), whereas the scalar accessor would redact it down to the
      fixed_contribution_amount or zero. The household-view Sankey (Task 9)
      uses the breakdown value intentionally — the caller is allowed to see
      their own real income because they're querying their own view.
    """
    first_day, first_day_next = _month_bounds_datetime(month)

    # 1. Caller's income transactions grouped by category.
    caller_tx_rows = await db.execute(
        select(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(
            Transaction.user_id == caller_id,
            Transaction.household_id == household_id,
            Transaction.transaction_type == "income",
            *counts_toward_totals_clauses(),
            Transaction.currency == currency,
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
        .group_by(Transaction.category)
    )
    raw_caller_totals: dict[str | None, Decimal] = {}
    for category, total in caller_tx_rows:
        raw_caller_totals[category] = Decimal(str(total))

    # 2. Caller's income category preferences (drives source labeling).
    #    Only categories configured by the user become named sources;
    #    everything else drops into caller_other_income.
    pref_rows = await db.execute(
        text("""
            SELECT category, sort_order
            FROM user_category_preferences
            WHERE user_id = :uid AND category_type = 'income'
            ORDER BY sort_order
        """),
        {"uid": str(caller_id)},
    )
    known_income_categories = {row.category for row in pref_rows}

    caller_sources: dict[str, Decimal] = {}
    caller_other_income = _ZERO
    for category, total in raw_caller_totals.items():
        if category and category in known_income_categories and total > _ZERO:
            caller_sources[category] = total
        else:
            caller_other_income += total

    # 3. Other members (non-caller, active).
    #    PRIVACY: the dispatch gates on contribution_mode BEFORE any
    #    read of transaction data — it is structurally impossible for a
    #    fixed-mode member's real income to be queried.
    member_rows = await db.execute(
        text("""
            SELECT hm.user_id, u.full_name, hm.contribution_mode,
                   hm.fixed_contribution_amount, hm.fixed_contribution_currency
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            WHERE hm.household_id = :hid
              AND hm.left_at IS NULL
              AND hm.user_id != :caller_id
        """),
        {"hid": str(household_id), "caller_id": str(caller_id)},
    )
    other_members: list[OtherMemberContribution] = []
    for row in member_rows:
        if row.contribution_mode == "full":
            amt = await income_for_personal_view(
                db,
                user_id=row.user_id,
                household_id=household_id,
                month=month,
                currency=currency,
            )
            if amt > _ZERO:
                other_members.append(
                    OtherMemberContribution(
                        user_id=row.user_id,
                        display_name=row.full_name,
                        amount=amt,
                        mode="full",
                    )
                )
        elif row.contribution_mode == "fixed":
            # PRIVACY: never query their real income transactions.
            if (
                row.fixed_contribution_amount is not None
                and row.fixed_contribution_currency == currency
            ):
                other_members.append(
                    OtherMemberContribution(
                        user_id=row.user_id,
                        display_name=row.full_name,
                        amount=Decimal(str(row.fixed_contribution_amount)),
                        mode="fixed",
                    )
                )
        # reimbursement mode -> skip (contributes $0)

    # 4. Compute the total.
    total = (
        sum(caller_sources.values(), start=_ZERO)
        + caller_other_income
        + sum((m.amount for m in other_members), start=_ZERO)
    )

    return HouseholdIncomeBreakdown(
        total=total,
        caller_sources=caller_sources,
        caller_other_income=caller_other_income,
        other_members=other_members,
    )


# ----------------------------------------------------------- update settings


async def update_contribution(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    mode: str,
    fixed_amount: Decimal | None = None,
    fixed_currency: str | None = None,
) -> HouseholdMember:
    """Update a member's contribution mode (and optional fixed amount/currency).

    Validation:
      - ``mode`` must be one of ``full | fixed | reimbursement``.
      - When ``mode == 'fixed'`` both ``fixed_amount`` and ``fixed_currency``
        are required, and ``fixed_amount`` must be > 0.
      - When ``mode != 'fixed'`` we clear the fixed fields for cleanliness
        (so a later flip back to ``fixed`` can't accidentally reuse stale values).

    The caller is responsible for the commit — we ``flush`` but do not commit,
    so the router can wrap this in its own transaction boundary (and the test
    fixture can roll back inside its SAVEPOINT).
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid contribution mode: {mode!r}")

    if mode == "fixed":
        if fixed_amount is None or fixed_currency is None:
            raise ValueError("fixed mode requires both fixed_amount and fixed_currency")
        amount_dec = Decimal(str(fixed_amount))
        if amount_dec <= _ZERO:
            raise ValueError("fixed_amount must be greater than 0")
        currency_norm = fixed_currency.upper()
    else:
        amount_dec = None
        currency_norm = None

    row = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    member = row.scalar_one_or_none()
    if member is None:
        raise ValueError(f"no active membership for user {user_id} in household {household_id}")

    member.contribution_mode = mode
    member.fixed_contribution_amount = amount_dec
    member.fixed_contribution_currency = currency_norm
    await db.flush()
    return member
