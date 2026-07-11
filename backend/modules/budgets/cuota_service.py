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

from modules.currencies.units import major_unit_quantum
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.budgets.cuota_models import CuotaPurchase
from modules.transactions.models import Transaction


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
        if remaining_installments > 0:
            # Derive from total_amount so the committed outflow always
            # reconciles to the purchase total the user entered (monthly x n
            # drifts by up to n/2 minor units from quantization).
            remaining = Decimal(c.total_amount) - Decimal(c.monthly_amount) * Decimal(
                int(c.installments_paid)
            )
            future_total += max(remaining, Decimal("0"))

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


def _add_months(d: date, months: int) -> date:
    """Add N months to date d, snapping to day=1 semantics.

    The cuotas schema enforces day=1 via business rules (`first_cuota_date`
    is always the first of a statement month), so we reset day to 1 after
    advancing. This dodges Jan 31 → Feb 31 style wrap-arounds entirely.
    """
    year = d.year + (d.month - 1 + months) // 12
    month = (d.month - 1 + months) % 12 + 1
    return date(year, month, 1)


async def create_cuota(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    merchant_name: str,
    total_amount: Decimal,
    currency: str,
    installments_total: int,
    first_cuota_date: date,
    split_type: str = "personal",
    origin_transaction_id: uuid.UUID | None = None,
) -> CuotaPurchase:
    """Create a cuota record. Derives monthly_amount and last_cuota_date.

    - `monthly_amount` = total_amount / installments_total, quantized to 2dp.
    - `last_cuota_date` = first_cuota_date + (installments_total - 1) months,
      with day snapped to 1.
    - Always starts as `status='active'`, `installments_paid=0`.

    The caller (the router layer) is responsible for commit/rollback;
    `create_cuota` only flushes so the returned row has its server-side
    defaults (`created_at`, `updated_at`) materialized.
    """
    if installments_total <= 0:
        raise ValueError("installments_total must be positive")
    if total_amount <= 0:
        raise ValueError("total_amount must be positive")

    # IDOR guard: if the client supplied an origin transaction, verify it
    # belongs to the caller. Otherwise a user could attach their installment
    # record to any transaction UUID they can guess.
    if origin_transaction_id is not None:
        tx_check = await db.execute(
            select(Transaction.id).where(
                Transaction.id == origin_transaction_id,
                Transaction.user_id == user_id,
            )
        )
        if tx_check.scalar_one_or_none() is None:
            raise ValueError("origin_transaction_id not found for this user")

    # Quantize to the currency's payable step (whole pesos for CLP/COP). The
    # summary derives future_total from total_amount, so the rounding drift on
    # monthly_amount x n never compounds (real statements put the remainder on
    # one installment).
    monthly_amount = (total_amount / Decimal(installments_total)).quantize(
        major_unit_quantum(currency)
    )
    last_cuota_date = _add_months(first_cuota_date, installments_total - 1)
    cuota = CuotaPurchase(
        id=uuid.uuid4(),
        user_id=user_id,
        household_id=household_id,
        merchant_name=merchant_name,
        total_amount=total_amount,
        currency=currency,
        installments_total=installments_total,
        installments_paid=0,
        monthly_amount=monthly_amount,
        first_cuota_date=first_cuota_date,
        last_cuota_date=last_cuota_date,
        status="active",
        split_type=split_type,
        origin_transaction_id=origin_transaction_id,
    )
    db.add(cuota)
    await db.flush()
    await db.refresh(cuota)
    return cuota


async def list_active_cuotas(
    db: AsyncSession,
    *,
    scope: Literal["personal", "household"],
    user_id: uuid.UUID | None = None,
    household_id: uuid.UUID | None = None,
) -> list[CuotaPurchase]:
    """Return all active cuotas scoped to a user (personal) or household.

    Rows come back in `first_cuota_date DESC` order so the freshest purchase
    is at the top of any list UI that consumes this.
    """
    stmt = select(CuotaPurchase).where(CuotaPurchase.status == "active")
    if scope == "personal":
        if user_id is None:
            raise ValueError("user_id required for personal scope")
        stmt = stmt.where(CuotaPurchase.user_id == user_id)
    elif scope == "household":
        if household_id is None:
            raise ValueError("household_id required for household scope")
        stmt = stmt.where(CuotaPurchase.household_id == household_id)
    else:
        raise ValueError(f"invalid scope: {scope!r}")

    stmt = stmt.order_by(CuotaPurchase.first_cuota_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def cancel_cuota(
    db: AsyncSession,
    *,
    cuota_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Mark a cuota cancelled. Only the owner (user_id) can cancel.

    Raises LookupError if the cuota doesn't exist or belongs to another user.
    """
    stmt = select(CuotaPurchase).where(
        CuotaPurchase.id == cuota_id,
        CuotaPurchase.user_id == user_id,
    )
    result = await db.execute(stmt)
    cuota = result.scalar_one_or_none()
    if cuota is None:
        raise LookupError(f"cuota {cuota_id} not found for user {user_id}")
    cuota.status = "cancelled"
    await db.flush()
