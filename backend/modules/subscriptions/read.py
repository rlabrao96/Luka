"""Household-scoped and personal-scoped `known_bills` readers for the budget endpoints.

Two flavors:

1. **Scheduled totals** (`get_*_known_bills`) — full sum of active recurring
   bills in a currency, regardless of whether they've been paid this month.
   Useful when you want the forward-looking "how much do subscriptions cost
   per month" figure.

2. **Unpaid totals** (`get_*_unpaid_known_bills`) — scheduled total minus any
   subscription that already has a matching transaction this month. A
   subscription counts as paid when a transaction exists in the month with
   the same merchant_key and an amount within ±10% of the scheduled amount
   (`_PAID_TOLERANCE`). The full scheduled amount is deducted on a match
   (over-pays due to utilities lumped into a lease still count as fully paid).

   Budget-v2 uses the unpaid readers so the Sankey doesn't double-count
   subscription payments once against `Gastos fijos` and again inside the
   actual-spend breakdown.

"Effective split_type" = `subscription_overrides.split_type` if set,
otherwise the raw `split_type` inferred from `transaction_splits`.

None of these functions filter by `contribution_mode` — that's `v2_service`'s
job when aggregating the household-level response.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.subscriptions.service import get_detected_subscriptions


_ZERO = Decimal("0")
_PAID_TOLERANCE = Decimal("0.10")  # ±10% on amount match


def _month_bounds(month: date) -> tuple[datetime, datetime]:
    first = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    days = calendar.monthrange(month.year, month.month)[1]
    # first day of the next calendar month
    if month.month == 12:
        next_first = datetime(month.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_first = datetime(month.year, month.month + 1, 1, tzinfo=timezone.utc)
    _ = days
    return first, next_first


async def _sum_user_bills_by_split_type(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    wanted_split_type: str,
) -> Decimal:
    """Sum recurring bills for one user in `currency` where the effective
    split_type matches `wanted_split_type`."""
    payload = await get_detected_subscriptions(db, user_id)
    total = _ZERO
    for item in payload["items"]:
        if item.get("status") != "active":
            continue
        if item.get("currency") != currency:
            continue
        if item["split_type"] == wanted_split_type:
            last = item.get("last_amount") or _ZERO
            total += last if isinstance(last, Decimal) else Decimal(str(last))
    return total


async def get_user_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum the monthly total of ALL detected recurring bills for one user in
    `currency`, regardless of split_type. Used by the legacy v2 personal view
    entry points that don't yet discriminate between personal and shared."""
    payload = await get_detected_subscriptions(db, user_id)
    summary = payload.get("summary_by_currency") or {}
    curr_summary = summary.get(currency)
    if not curr_summary:
        return _ZERO
    total = curr_summary.get("total_recurring") or _ZERO
    return total if isinstance(total, Decimal) else Decimal(str(total))


async def get_user_personal_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum of one user's recurring bills that are PERSONAL (not shared with
    the household). Used by the v3 personal view Sankey."""
    return await _sum_user_bills_by_split_type(db, user_id, currency, "personal")


async def get_user_shared_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum of one user's recurring bills that are SHARED with the household.
    Used by v2_service to symmetrically subtract reimbursement members'
    contribution when computing household known_bills."""
    return await _sum_user_bills_by_split_type(db, user_id, currency, "shared")


async def get_household_known_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum of household SHARED recurring bills across every active member
    in `currency`. Active = `left_at IS NULL`. Only items whose effective
    split_type is 'shared' contribute — personal-tagged subs are excluded.

    The caller (`v2_service`) is responsible for adjusting the result based
    on contribution_mode — e.g. subtracting reimbursement members' bills,
    which don't hit the household pot.
    """
    member_rows = await db.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    total = _ZERO
    for (user_id,) in member_rows:
        total += await _sum_user_bills_by_split_type(db, user_id, currency, "shared")
    return total


# ---------------------------------------------------------------- unpaid


async def _paid_subscription_amounts_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    currency: str,
    month: date,
    split_type_filter: str | None,
) -> Decimal:
    """Sum of scheduled `last_amount` for the user's subscriptions that have
    been paid this month.

    A subscription is considered paid when a transaction exists in `month`
    whose merchant_key matches and whose `ABS(amount)` is within ±10% of the
    subscription's `last_amount`. Over-pays (e.g. rent + utilities lumped
    together) still count as fully paid — we return the full scheduled
    amount on match.

    `split_type_filter`: "shared" | "personal" | None (any).
    """
    payload = await get_detected_subscriptions(db, user_id)
    active = [
        item
        for item in payload["items"]
        if item.get("status") == "active"
        and item.get("currency") == currency
        and (split_type_filter is None or item.get("split_type") == split_type_filter)
    ]
    if not active:
        return _ZERO

    merchant_keys = sorted({item["merchant_name"] for item in active if item.get("merchant_name")})
    if not merchant_keys:
        return _ZERO

    first, next_first = _month_bounds(month)

    # Pull every this-month expense for this user that shares a merchant_key
    # with an active subscription. One query regardless of subscription count.
    rows = await db.execute(
        text(
            """
            SELECT COALESCE(m.normalized_name, t.raw_merchant_name) AS merchant_key,
                   ABS(t.amount) AS amt
            FROM transactions t
            LEFT JOIN merchants m ON m.id = t.merchant_id
            WHERE t.user_id = :uid
              AND t.transaction_type = 'expense'
              AND t.currency = :ccy
              AND t.transaction_date >= :first
              AND t.transaction_date <  :first_next
              AND COALESCE(m.normalized_name, t.raw_merchant_name) = ANY(:keys)
            """
        ),
        {
            "uid": str(user_id),
            "ccy": currency,
            "first": first,
            "first_next": next_first,
            "keys": merchant_keys,
        },
    )
    tx_by_key: dict[str, list[Decimal]] = {}
    for row in rows:
        tx_by_key.setdefault(row.merchant_key, []).append(Decimal(str(row.amt)))

    paid = _ZERO
    for item in active:
        mkey = item.get("merchant_name")
        last_raw = item.get("last_amount")
        if not mkey or not last_raw:
            continue
        last = last_raw if isinstance(last_raw, Decimal) else Decimal(str(last_raw))
        if last <= _ZERO:
            continue
        tolerance = last * _PAID_TOLERANCE
        matches = [a for a in tx_by_key.get(mkey, []) if abs(a - last) <= tolerance]
        if matches:
            paid += last
    return paid


async def get_user_unpaid_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    month: date,
) -> Decimal:
    """Total scheduled bills for the user in `currency`, minus those already
    paid this month. See module docstring for match rules."""
    scheduled = await get_user_known_bills(db, user_id, currency)
    paid = await _paid_subscription_amounts_for_user(
        db,
        user_id=user_id,
        currency=currency,
        month=month,
        split_type_filter=None,
    )
    return max(_ZERO, scheduled - paid)


async def get_user_shared_unpaid_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    month: date,
) -> Decimal:
    """Shared-split scheduled bills for the user minus those paid this month."""
    scheduled = await _sum_user_bills_by_split_type(db, user_id, currency, "shared")
    paid = await _paid_subscription_amounts_for_user(
        db,
        user_id=user_id,
        currency=currency,
        month=month,
        split_type_filter="shared",
    )
    return max(_ZERO, scheduled - paid)


async def get_household_unpaid_known_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
    month: date,
) -> Decimal:
    """Household SHARED scheduled bills across active members, minus those
    already paid this month.

    Matching is per-user: a subscription owned by member A is considered paid
    only when member A has a matching transaction this month. If A and B both
    have the same merchant subscription, each is evaluated independently.
    """
    member_rows = await db.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    total = _ZERO
    for (user_id,) in member_rows:
        total += await get_user_shared_unpaid_known_bills(db, user_id, currency, month)
    return total
