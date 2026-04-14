"""Household-scoped `known_bills` reader for the budget-v2 endpoint.

The existing `modules.subscriptions.service.get_detected_subscriptions` is
strictly user-scoped. The budget-v2 endpoint needs both a user-scoped and a
household-scoped sum, so we wrap the underlying helper here.

This module is intentionally thin — we do NOT filter on `contribution_mode`
(that's `v2_service`'s job when it constructs the household-level aggregate).
Here we just fan out to the subscriptions helper per active member.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import HouseholdMember
from modules.subscriptions.service import get_detected_subscriptions


async def get_user_known_bills(
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum the monthly total of detected recurring bills for one user in `currency`.

    Returns Decimal('0') if there are no detected subscriptions in that
    currency — the subscriptions service returns a dict keyed by currency
    under `summary_by_currency`, so a missing currency key means "nothing".
    """
    payload = await get_detected_subscriptions(db, user_id)
    summary = payload.get("summary_by_currency") or {}
    curr_summary = summary.get(currency)
    if not curr_summary:
        return Decimal("0")
    total = curr_summary.get("total_recurring") or Decimal("0")
    # The service returns Decimal already, but be defensive.
    return total if isinstance(total, Decimal) else Decimal(str(total))


async def get_household_known_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
    currency: str,
) -> Decimal:
    """Sum known bills across every active member of a household in `currency`.

    Active = `left_at IS NULL`. The caller (`v2_service`) is responsible for
    adjusting the result based on contribution_mode — e.g. subtracting
    reimbursement members' bills, which don't hit the household pot.
    """
    member_rows = await db.execute(
        select(HouseholdMember.user_id).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    total = Decimal("0")
    for (user_id,) in member_rows:
        total += await get_user_known_bills(db, user_id, currency)
    return total
