"""Household-scoped and personal-scoped `known_bills` readers for the budget endpoints.

The existing `modules.subscriptions.service.get_detected_subscriptions` is
strictly user-scoped. Budget-v2 / v3 need both a household-scoped and a
user-scoped sum, each filtered by effective `split_type`:

- Household known bills: subscriptions with effective `split_type='shared'`
- Personal known bills: subscriptions with effective `split_type='personal'`

"Effective" means: `subscription_overrides.split_type` if set, otherwise the
raw `split_type` from `detect_from_rows` (which reads it from
`transaction_splits.split_type` defaulting to 'personal').

This module does NOT filter by `contribution_mode` (that's `v2_service`'s job
when it constructs the household-level aggregate).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.subscriptions.service import get_detected_subscriptions


_ZERO = Decimal("0")


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
        # split_type was already resolved by _merge_overrides — override wins
        # over inferred, so this read reflects the effective value.
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
