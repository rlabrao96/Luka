"""Cuotas (installment purchases) service layer.

Chunk C owns only the read-side aggregate used by `/budgets/v2` — the full
CRUD surface (create/list/cancel, router routes, validation) is added later
by Chunk E on top of this module. Keep this file minimal and additive so E
can append without refactoring anything here.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.budgets.cuota_models import CuotaPurchase


def _month_bounds(month: date) -> tuple[date, date]:
    """Return (first_day, last_day) for the given month.

    `month` is expected to already be day=1 but we don't assume it.
    """
    first = date(month.year, month.month, 1)
    last_day_num = calendar.monthrange(month.year, month.month)[1]
    last = date(month.year, month.month, last_day_num)
    return first, last


async def get_active_cuotas_summary(
    db: AsyncSession,
    *,
    scope: str,
    user_id: uuid.UUID | None = None,
    household_id: uuid.UUID | None = None,
    month: date,
    currency: str,
) -> dict:
    """Aggregate active cuotas for a month, scoped personal or household.

    Returns `{"this_month": Decimal, "future_total": Decimal, "active_count": int}`.

    - `this_month`: sum of `monthly_amount` for cuotas where
      `first_cuota_date <= month_end` AND `last_cuota_date >= month_start`.
      This is the committed installment cost the user will see on their
      statement this calendar month.
    - `future_total`: sum of `monthly_amount * (installments_total - installments_paid)`
      across still-active cuotas. A rough forward-commitment line the UI
      uses for the cuotas card. Intentionally scope-wide so users see their
      total debt overhang, not just this month's slice.
    - `active_count`: number of active cuotas matching the scope filter.

    Filters on `currency` and `status == "active"`. Scope switches between
    personal (user_id) and household (household_id) — exactly one must be
    provided per scope.
    """
    if scope not in ("personal", "household"):
        raise ValueError(f"invalid scope: {scope!r}")
    if scope == "personal" and user_id is None:
        raise ValueError("scope='personal' requires user_id")
    if scope == "household" and household_id is None:
        raise ValueError("scope='household' requires household_id")

    month_start, month_end = _month_bounds(month)

    query = select(CuotaPurchase).where(
        CuotaPurchase.status == "active",
        CuotaPurchase.currency == currency,
    )
    if scope == "personal":
        query = query.where(CuotaPurchase.user_id == user_id)
    else:
        query = query.where(CuotaPurchase.household_id == household_id)

    result = await db.execute(query)
    cuotas = list(result.scalars().all())

    this_month = Decimal("0")
    future_total = Decimal("0")
    active_count = len(cuotas)

    for c in cuotas:
        # "Is the cuota alive this calendar month?" — any overlap between
        # [first_cuota_date, last_cuota_date] and [month_start, month_end].
        if c.first_cuota_date <= month_end and c.last_cuota_date >= month_start:
            this_month += Decimal(c.monthly_amount)
        remaining_installments = max(0, int(c.installments_total) - int(c.installments_paid))
        future_total += Decimal(c.monthly_amount) * Decimal(remaining_installments)

    return {
        "this_month": this_month,
        "future_total": future_total,
        "active_count": active_count,
    }


# ---------------------------------------------------------------------------
# Chunk E extension point: CRUD functions (create_cuota, list_active_cuotas,
# cancel_cuota, etc.) get appended below this line. Keep the aggregate helper
# above stable — v2_service imports `get_active_cuotas_summary` by name.
# ---------------------------------------------------------------------------
