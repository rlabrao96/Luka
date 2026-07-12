"""Budget v2 service layer — computes the full `/budgets/v2/{household_id}` response.

Built from three pillars:
- `forecast.py` — pure math helpers (stats, Gaussian overshoot, pace, runway)
- `cuota_service.get_active_cuotas_summary` — cuotas aggregate block
- `subscriptions.read.get_user_known_bills` / `_household_known_bills` — known bills

Income is delegated to `modules.households.contribution_service` — that
module owns the contribution-mode dispatch (full / fixed / reimbursement)
and is the single enforcement point for the privacy invariant. Do NOT
re-inline income queries here; add them over there and call them from here.

Chunk F will tighten the savings-category exclusion and the
`user_budget_settings` reads. We correctly implement both inline today
so F can refactor without breaking semantics.

Privacy invariant (regression-tested in `tests/test_budget_v2_endpoint.py`
and `tests/test_contribution_modes.py`):
- When `view="household"` and any member has `contribution_mode="fixed"`,
  that member's REAL income must never appear anywhere in the response.
  Only their `fixed_contribution_amount` counts toward household income.
- `reimbursement` members contribute 0 to household income AND their
  known_bills are subtracted from the household known_bills total.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.budgets.cuota_service import get_active_cuotas_summary
from modules.budgets.forecast import (
    category_stats,
    overshoot_probability,
    pace_forecast,
    runway_days,
    select_risk_categories,
    spendable_ceiling,
)
from modules.budgets.savings_categories import is_savings_category
from modules.budgets.user_budget_settings_service import (
    get_household_personal_allocation,
    get_household_savings_target,
    get_payday_day_of_month,
    get_savings_target,
)
from modules.budgets.v2_schemas import (
    BudgetV2Response,
    CuotasBlock,
    DrilldownBlock,
    DrilldownItem,
    RiskCategory,
    RunwayBlock,
    SankeyBlock,
    SankeyLink,
    SankeyNode,
    SavingsTargetBlock,
    SpendableBlock,
)
from modules.households.contribution_service import (
    HouseholdIncomeBreakdown,
    income_breakdown_for_household_view,
)
from modules.households.models import BankAccount, HouseholdMember
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.models import Merchant
from modules.subscriptions.read import (
    get_household_unpaid_known_bills,
    get_user_personal_unpaid_known_bills,
    get_user_shared_unpaid_known_bills,
)
from modules.transactions.models import Transaction, TransactionSplit
from modules.transactions.totals import counts_toward_totals_clauses


_ZERO = Decimal("0")


# ---------------------------------------------------------------- month math


def _month_bounds_datetime(month: date) -> tuple[datetime, datetime, int]:
    """Return (first_day_dt, first_day_next_dt, days_in_month) as UTC datetimes."""
    first_day = datetime(month.year, month.month, 1, tzinfo=timezone.utc)
    if month.month == 12:
        next_year, next_month = month.year + 1, 1
    else:
        next_year, next_month = month.year, month.month + 1
    first_day_next = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    return first_day, first_day_next, days_in_month


def _month_bounds_date(month: date) -> tuple[date, date]:
    first = date(month.year, month.month, 1)
    last = date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])
    return first, last


def _prior_month(month: date, offset: int) -> date:
    """Return the first-of-month `offset` calendar months before `month`."""
    m = month.month - offset
    y = month.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _today_day_in_month(month: date, days_in_month: int) -> int:
    """Current day-of-month clamped to the month if we're viewing a past month."""
    today = datetime.now(timezone.utc).date()
    if today.year == month.year and today.month == month.month:
        return min(today.day, days_in_month)
    # Historical month — treat as fully observed
    return days_in_month


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


async def _fetch_month_transactions(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> list[Transaction]:
    """Pull expense transactions for the month in one query.

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
        base = (
            select(Transaction)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
                (TransactionSplit.split_type == "personal")
                | (TransactionSplit.split_type.is_(None)),
            )
        )
    else:
        base = (
            select(Transaction)
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
    return list(r.scalars().all())


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
    "spending risk".
    """
    # Build a per-category list of 3 monthly totals.
    per_category: dict[str, list[Decimal]] = {}
    for offset in range(1, 4):
        prior_start = _prior_month(month, offset)
        first_day, first_day_next, _ = _month_bounds_datetime(prior_start)

        # Luka stores expense amounts as negative Decimals; take abs() so
        # category totals come out positive and downstream share×CV math
        # (mean/std/cap) works correctly.
        # Personal view uses LEFT JOIN so email-ingested txns with no split row
        # (treated as "personal" in the UI) don't drop out.
        if view == "personal":
            q = (
                select(
                    Transaction.category,
                    func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("total"),
                )
                .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.household_id == household_id,
                    Transaction.currency == currency,
                    Transaction.transaction_type == "expense",
                    *counts_toward_totals_clauses(),
                    Transaction.transaction_date >= first_day,
                    Transaction.transaction_date < first_day_next,
                    (TransactionSplit.split_type == "personal")
                    | (TransactionSplit.split_type.is_(None)),
                )
            )
        else:
            q = (
                select(
                    Transaction.category,
                    func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("total"),
                )
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
        q = q.group_by(Transaction.category)

        rows = await db.execute(q)
        for category, total in rows:
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
        q = (
            select(Transaction)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= fourteen_days_ago,
                Transaction.transaction_date <= today,
                (TransactionSplit.split_type == "personal")
                | (TransactionSplit.split_type.is_(None)),
            )
        )
    else:
        q = (
            select(Transaction)
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
    txns = list(rows.scalars().all())

    total = _ZERO
    for t in txns:
        if is_savings_category(t.category):
            continue
        # Expenses are stored as negative; abs() so the daily burn is positive.
        total += abs(Decimal(str(t.amount)))
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


# ----------------------------------------------------------- sankey builder


def _slugify(text: str) -> str:
    return (
        text.strip()
        .lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace(" ", "_")
        .replace("-", "_")
    )


def _pay_first_fit(
    *,
    target: Decimal,
    remaining_income: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    """First-fit routing primitive used by the Sankey builders.

    Pays `target` out of `remaining_income`, sending the shortfall to
    `otras_fuentes`. Returns `(from_income, from_otras, remaining_income_after)`.
    Every non-trivial target maps to at most two inflow links; flow
    conservation is preserved because from_income + from_otras == target.
    """
    if target <= _ZERO:
        return _ZERO, _ZERO, remaining_income
    from_income = min(remaining_income, target)
    from_otras = target - from_income
    return from_income, from_otras, remaining_income - from_income


def _build_hogar_sankey(
    *,
    breakdown: "HouseholdIncomeBreakdown",
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    personal_allocation: Decimal,
    spendable_amount: Decimal,
    top_spent_totals: list[tuple[str, Decimal]],
    risk_category_set: frozenset[str] = frozenset(),
    other_spent: Decimal,
    income_category_order: list[str],
) -> SankeyBlock:
    """Build the 4-level Hogar Sankey.

    Levels:
      0: income source nodes — caller's `user_category_preferences` rows
         (in sort_order) that have sum > 0, plus one aggregated node per
         other member, plus `otras_fuentes` synthetic node for overspent
         months.
      1: `ingresos_hogar` hub — single node, value = breakdown.total +
         otras_fuentes shortfall.
      2: allocation nodes — `meta_ahorro`, `gastos_fijos`, `cuotas`,
         `gasto_personal` (hidden if personal_allocation == 0),
         `disponible_hogar`.
      3: breakdown of `disponible_hogar` — per-risk-category spent nodes
         plus `spent_other` residual plus `spent_remaining`.

    Flow conservation: every non-source / non-terminal node has
    inflow == outflow == value. The `_pay_first_fit` helper splits any
    allocation target that income can't cover by itself, routing the
    shortfall to `otras_fuentes` which enters at Level 0 alongside the
    source nodes and flows into `ingresos_hogar`.
    """
    total_spent = sum((s for _, s in top_spent_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO
    sankey_spendable = total_spent if total_spent > spendable_amount else spendable_amount

    # Pay each allocation from income via first-fit routing. We only need
    # the shortfall (`ot_*`) because `ingresos_hogar` collapses every source
    # into a single hub — there's no per-allocation income/otras link split
    # like in the personal-view builder (_build_personal_sankey).
    remaining = breakdown.total
    _, ot_kb, remaining = _pay_first_fit(target=known_bills, remaining_income=remaining)
    _, ot_cu, remaining = _pay_first_fit(target=cuotas_this_month, remaining_income=remaining)
    _, ot_st, remaining = _pay_first_fit(target=savings_target, remaining_income=remaining)
    _, ot_pa, remaining = _pay_first_fit(target=personal_allocation, remaining_income=remaining)
    _, ot_sp, remaining = _pay_first_fit(target=sankey_spendable, remaining_income=remaining)

    otras_fuentes_total = ot_kb + ot_cu + ot_st + ot_pa + ot_sp
    ingresos_hogar_value = breakdown.total + otras_fuentes_total

    nodes: list[SankeyNode] = []

    # ---- Level 0: caller's income sources ----
    for category in income_category_order:
        amount = breakdown.caller_sources.get(category, _ZERO)
        if amount > _ZERO:
            nodes.append(
                SankeyNode(
                    id=f"src_{_slugify(category)}",
                    label=category,
                    value=amount,
                    level=0,
                    kind="source",
                )
            )
    if breakdown.caller_other_income > _ZERO:
        nodes.append(
            SankeyNode(
                id="src_otros_ingresos",
                label="Otros ingresos",
                value=breakdown.caller_other_income,
                level=0,
                kind="source",
            )
        )

    # ---- Level 0: other members ----
    for m in breakdown.other_members:
        if m.amount <= _ZERO:
            continue
        label = (
            f"Contribuci\u00f3n fija {m.display_name}"
            if m.mode == "fixed"
            else f"Ingresos {m.display_name}"
        )
        nodes.append(
            SankeyNode(
                id=f"member_{m.user_id}",
                label=label,
                value=m.amount,
                level=0,
                kind="source",
                member_id=str(m.user_id),
            )
        )

    # ---- Level 0: otras_fuentes synthetic source ----
    # When committed outflows (known_bills + cuotas + savings_target +
    # personal_allocation + spendable) exceed real income, this plug keeps
    # the Sankey flow-conserving. It is NOT a real source — the label and
    # frontend color reflect that it represents a deficit to be covered.
    if otras_fuentes_total > _ZERO:
        nodes.append(
            SankeyNode(
                id="otras_fuentes",
                label="Ingresos por cubrir",
                value=otras_fuentes_total,
                level=0,
                kind="deficit",
            )
        )

    # ---- Level 1: income hub ----
    nodes.append(
        SankeyNode(
            id="ingresos_hogar",
            label="Ingresos Hogar",
            value=ingresos_hogar_value,
            level=1,
            kind="hub",
        )
    )

    # ---- Level 2: allocation nodes ----
    # `disponible_hogar` is emitted FIRST so `sort={false}` in the frontend
    # pins it to the top of Level 2. Its label renders ABOVE its rectangle
    # (pass-through hub treatment); the rest of the Level-2 nodes sit below
    # it with their own label styles (bills render labels BELOW; plain
    # allocations render right of the rectangle). Ordering is critical to
    # keep Disponible's above-label from colliding with the below-label of
    # a bill rectangle that would otherwise land right above it.
    if sankey_spendable > _ZERO:
        nodes.append(
            SankeyNode(
                id="disponible_hogar",
                label="Disponible hogar",
                value=sankey_spendable,
                level=2,
                kind="allocation",
            )
        )
    if known_bills > _ZERO:
        nodes.append(
            SankeyNode(
                id="gastos_fijos",
                # `\n` renders as a second line in the frontend tspan layout.
                label="Gastos fijos\npendientes",
                value=known_bills,
                level=2,
                kind="bill",
            )
        )
    if cuotas_this_month > _ZERO:
        nodes.append(
            SankeyNode(
                id="cuotas",
                label="Cuotas del mes",
                value=cuotas_this_month,
                level=2,
                kind="allocation",
            )
        )
    if savings_target > _ZERO:
        nodes.append(
            SankeyNode(
                id="meta_ahorro",
                label="Meta de ahorro",
                value=savings_target,
                level=2,
                kind="allocation",
            )
        )
    if personal_allocation > _ZERO:
        nodes.append(
            SankeyNode(
                id="gasto_personal",
                label="Gasto personal",
                value=personal_allocation,
                level=2,
                kind="allocation",
            )
        )

    # ---- Level 3: disponible_hogar breakdown ----
    # `spent_remaining` ("Aún disponible") is emitted FIRST so d3-sankey
    # lands it at the top of the terminal column — we want the "still
    # available" signal pinned regardless of its dollar size.
    if spent_remaining > _ZERO:
        nodes.append(
            SankeyNode(
                id="spent_remaining",
                label="Aún disponible",
                value=spent_remaining,
                level=3,
                kind="unused",
            )
        )
    for category, spent in top_spent_totals:
        if spent <= _ZERO:
            continue
        nodes.append(
            SankeyNode(
                id=f"spent_{_slugify(category)}",
                label=category,
                value=spent,
                level=3,
                kind="spent",
                risk=category in risk_category_set,
            )
        )
    if other_spent > _ZERO:
        nodes.append(
            SankeyNode(
                id="spent_other",
                label="Otras categorías",
                value=other_spent,
                level=3,
                kind="spent",
            )
        )

    # ---- Links ----
    links: list[SankeyLink] = []

    def _emit(source: str, target: str, value: Decimal) -> None:
        if value > _ZERO:
            links.append(SankeyLink(source=source, target=target, value=value))

    # Level 0 -> Level 1: sources feed into ingresos_hogar
    for category in income_category_order:
        amount = breakdown.caller_sources.get(category, _ZERO)
        _emit(f"src_{_slugify(category)}", "ingresos_hogar", amount)
    if breakdown.caller_other_income > _ZERO:
        _emit("src_otros_ingresos", "ingresos_hogar", breakdown.caller_other_income)
    for m in breakdown.other_members:
        if m.amount > _ZERO:
            _emit(f"member_{m.user_id}", "ingresos_hogar", m.amount)
    if otras_fuentes_total > _ZERO:
        _emit("otras_fuentes", "ingresos_hogar", otras_fuentes_total)

    # Level 1 -> Level 2: ingresos_hogar feeds each allocation
    _emit("ingresos_hogar", "gastos_fijos", known_bills)
    _emit("ingresos_hogar", "cuotas", cuotas_this_month)
    _emit("ingresos_hogar", "meta_ahorro", savings_target)
    _emit("ingresos_hogar", "gasto_personal", personal_allocation)
    _emit("ingresos_hogar", "disponible_hogar", sankey_spendable)

    # Level 2 -> Level 3: disponible_hogar splits. Emit spent_remaining first
    # (mirrors the node order above) so it anchors the top of the column.
    _emit("disponible_hogar", "spent_remaining", spent_remaining)
    for category, spent in top_spent_totals:
        if spent > _ZERO:
            _emit("disponible_hogar", f"spent_{_slugify(category)}", spent)
    _emit("disponible_hogar", "spent_other", other_spent)

    return SankeyBlock(nodes=nodes, links=links)


def _build_personal_sankey(
    *,
    caller_sources: dict[str, Decimal],
    caller_other_income: Decimal,
    gastos_hogar: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    spendable_amount: Decimal,
    top_spent_totals: list[tuple[str, Decimal]],
    risk_category_set: frozenset[str] = frozenset(),
    other_spent: Decimal,
    income_category_order: list[str],
) -> SankeyBlock:
    """Build the Personal Sankey. Structurally identical to the Hogar builder
    but scoped to caller-only income, no `Gasto personal` allocation, and
    no per-other-member nodes.

    Uses a `ingresos_personales` hub at Level 1 for clean routing (mirrors
    the hogar `ingresos_hogar` hub). Level 2 has up to four allocation nodes
    (gastos_fijos_personal, cuotas_personal, meta_ahorro_personal,
    disponible_personal — each hidden if its value is zero). Level 3 has the
    disponible_personal breakdown.
    """
    total_spent = sum((s for _, s in top_spent_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO
    sankey_spendable = total_spent if total_spent > spendable_amount else spendable_amount

    income_total = sum(caller_sources.values(), start=_ZERO) + caller_other_income

    # Pay each allocation from income via first-fit routing. We only need
    # the shortfall (`ot_*`) — the hub absorbs all sources and re-emits to
    # allocations as a single link each.
    remaining = income_total
    _, ot_gh, remaining = _pay_first_fit(target=gastos_hogar, remaining_income=remaining)
    _, ot_kb, remaining = _pay_first_fit(target=known_bills, remaining_income=remaining)
    _, ot_cu, remaining = _pay_first_fit(target=cuotas_this_month, remaining_income=remaining)
    _, ot_st, remaining = _pay_first_fit(target=savings_target, remaining_income=remaining)
    _, ot_sp, remaining = _pay_first_fit(target=sankey_spendable, remaining_income=remaining)

    deficit_total = ot_gh + ot_kb + ot_cu + ot_st + ot_sp
    hub_value = income_total + deficit_total

    nodes: list[SankeyNode] = []

    # Level 0: caller's own sources
    for category in income_category_order:
        amount = caller_sources.get(category, _ZERO)
        if amount > _ZERO:
            nodes.append(
                SankeyNode(
                    id=f"src_{_slugify(category)}",
                    label=category,
                    value=amount,
                    level=0,
                    kind="source",
                )
            )
    if caller_other_income > _ZERO:
        nodes.append(
            SankeyNode(
                id="src_otros_ingresos",
                label="Otros ingresos",
                value=caller_other_income,
                level=0,
                kind="source",
            )
        )
    if deficit_total > _ZERO:
        nodes.append(
            SankeyNode(
                id="deficit_personal",
                label="Ingresos por cubrir",
                value=deficit_total,
                level=0,
                kind="deficit",
            )
        )

    # Level 1: hub
    nodes.append(
        SankeyNode(
            id="ingresos_personales",
            label="Mis ingresos",
            value=hub_value,
            level=1,
            kind="hub",
        )
    )

    # Level 2 — `disponible_personal` emitted FIRST so it pins to the top
    # of the column (matches Hogar layout; prevents bill below-label from
    # colliding with disponible's above-label when the two stack).
    if sankey_spendable > _ZERO:
        nodes.append(
            SankeyNode(
                id="disponible_personal",
                label="Disponible personal",
                value=sankey_spendable,
                level=2,
                kind="allocation",
            )
        )
    if gastos_hogar > _ZERO:
        nodes.append(
            SankeyNode(
                id="gastos_hogar_personal",
                label="Gastos del hogar",
                value=gastos_hogar,
                level=2,
                kind="allocation",
            )
        )
    if known_bills > _ZERO:
        nodes.append(
            SankeyNode(
                id="gastos_fijos_personal",
                # `\n` renders as a second line in the frontend tspan layout.
                label="Gastos fijos\npendientes",
                value=known_bills,
                level=2,
                kind="bill",
            )
        )
    if cuotas_this_month > _ZERO:
        nodes.append(
            SankeyNode(
                id="cuotas_personal",
                label="Cuotas del mes",
                value=cuotas_this_month,
                level=2,
                kind="allocation",
            )
        )
    if savings_target > _ZERO:
        nodes.append(
            SankeyNode(
                id="meta_ahorro_personal",
                label="Meta de ahorro",
                value=savings_target,
                level=2,
                kind="allocation",
            )
        )

    # Level 3: disponible_personal breakdown.
    # spent_remaining first so d3-sankey pins "Aún disponible" to the top of
    # the terminal column regardless of its value (see Hogar builder for the
    # matching logic).
    if spent_remaining > _ZERO:
        nodes.append(
            SankeyNode(
                id="spent_remaining",
                label="Aún disponible",
                value=spent_remaining,
                level=3,
                kind="unused",
            )
        )
    for category, spent in top_spent_totals:
        if spent <= _ZERO:
            continue
        nodes.append(
            SankeyNode(
                id=f"spent_{_slugify(category)}",
                label=category,
                value=spent,
                level=3,
                kind="spent",
                risk=category in risk_category_set,
            )
        )
    if other_spent > _ZERO:
        nodes.append(
            SankeyNode(
                id="spent_other",
                label="Otras categorías",
                value=other_spent,
                level=3,
                kind="spent",
            )
        )

    # Links
    links: list[SankeyLink] = []

    def _emit(source: str, target: str, value: Decimal) -> None:
        if value > _ZERO:
            links.append(SankeyLink(source=source, target=target, value=value))

    # Level 0 -> Level 1 (hub)
    for category in income_category_order:
        amount = caller_sources.get(category, _ZERO)
        _emit(f"src_{_slugify(category)}", "ingresos_personales", amount)
    _emit("src_otros_ingresos", "ingresos_personales", caller_other_income)
    _emit("deficit_personal", "ingresos_personales", deficit_total)

    # Level 1 -> Level 2
    _emit("ingresos_personales", "gastos_hogar_personal", gastos_hogar)
    _emit("ingresos_personales", "gastos_fijos_personal", known_bills)
    _emit("ingresos_personales", "cuotas_personal", cuotas_this_month)
    _emit("ingresos_personales", "meta_ahorro_personal", savings_target)
    _emit("ingresos_personales", "disponible_personal", sankey_spendable)

    # Level 2 -> Level 3: spent_remaining first so it anchors the top.
    _emit("disponible_personal", "spent_remaining", spent_remaining)
    for category, spent in top_spent_totals:
        if spent > _ZERO:
            _emit("disponible_personal", f"spent_{_slugify(category)}", spent)
    _emit("disponible_personal", "spent_other", other_spent)

    return SankeyBlock(nodes=nodes, links=links)


# -------------------------------------------------------------- entry point


async def get_budget_v2(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    month: date,
    currency: str | None,
    view: str,
) -> BudgetV2Response:
    """Build the /budgets/v2 response for the given scope.

    Args:
        db: async session
        household_id: which household to report on
        user_id: authenticated caller (used for personal view + savings target)
        month: first-of-month date
        currency: ISO code ("CLP", "USD"). If None, use the caller's
            `preferred_currency`.
        view: "personal" | "household"
    """
    if view not in ("personal", "household"):
        raise ValueError(f"invalid view: {view!r}")

    # Force month=day-1 to match the DATE column convention.
    month = date(month.year, month.month, 1)
    _, _, days_in_month = _month_bounds_datetime(month)
    today_day = _today_day_in_month(month, days_in_month)

    # ---- currencies available --------------------------------------------
    currencies_available = await _currencies_available(
        db, view=view, user_id=user_id, household_id=household_id
    )

    # ---- resolve currency -------------------------------------------------
    # Priority: explicit query param → user's preferred_currency → first
    # currency with actual transactions → CLP as last resort. This keeps the
    # endpoint working for LATAM countries (CO/MX/PE/BR/US) without forcing
    # a Chilean default on everyone. See CLAUDE.md: never assume CLP.
    if not currency:
        user_row = await db.execute(select(User.preferred_currency).where(User.id == user_id))
        preferred = user_row.scalar_one_or_none()
        currency = preferred or (currencies_available[0] if currencies_available else "CLP")

    if currency not in currencies_available:
        currencies_available = sorted(set(currencies_available) | {currency})

    # ---- known_bills -----------------------------------------------------
    # "Unpaid-this-month" flavor: a subscription that's already been paid (a
    # transaction matches its merchant_key with amount within ±10%) drops out
    # of `known_bills` for this month. The subsequent Sankey flow then shows
    # income = unpaid bills + actual spent, with no double-count of a bill
    # payment showing up both as `Gastos fijos` and under the risk-category
    # breakdown of `Disponible hogar`.
    if view == "personal":
        known_bills = await get_user_personal_unpaid_known_bills(db, user_id, currency, month)
    else:
        raw = await get_household_unpaid_known_bills(db, household_id, currency, month)
        reimb = await _reimbursement_members_known_bills(db, household_id, currency, month)
        known_bills = raw - reimb
        if known_bills < _ZERO:
            known_bills = _ZERO

    # ---- cuotas ----------------------------------------------------------
    if view == "personal":
        cuotas_summary = await get_active_cuotas_summary(
            db,
            scope="personal",
            user_id=user_id,
            month=month,
            currency=currency,
        )
    else:
        cuotas_summary = await get_active_cuotas_summary(
            db,
            scope="household",
            household_id=household_id,
            month=month,
            currency=currency,
        )
    cuotas_block = CuotasBlock(
        this_month=cuotas_summary["this_month"],
        future_total=cuotas_summary["future_total"],
        active_count=cuotas_summary["active_count"],
    )

    # ---- savings target --------------------------------------------------
    if view == "personal":
        savings_target_amount = await _personal_savings_target(db, user_id, currency)
    else:
        savings_target_amount = await _household_savings_target(db, household_id, currency)

    # ---- caller's income category ordering (drives Level 0 source nodes) ----
    income_cat_rows = await db.execute(
        text("""
            SELECT category
            FROM user_category_preferences
            WHERE user_id = :uid AND category_type = 'income'
            ORDER BY sort_order
        """),
        {"uid": str(user_id)},
    )
    income_category_order = [r[0] for r in income_cat_rows]

    # ---- income ----------------------------------------------------------
    if view == "personal":
        # Personal view: caller's own income grouped by category against their
        # user_category_preferences. Bucketed inline rather than going through
        # income_breakdown_for_household_view because the personal view is
        # single-scope and doesn't need the other_members aggregation.
        first_day, first_day_next, _ = _month_bounds_datetime(month)
        caller_tx_rows = await db.execute(
            select(
                Transaction.category,
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.household_id == household_id,
                Transaction.transaction_type == "income",
                *counts_toward_totals_clauses(),
                Transaction.currency == currency,
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
            )
            .group_by(Transaction.category)
        )
        raw_caller: dict[str | None, Decimal] = {}
        for category, total in caller_tx_rows:
            raw_caller[category] = Decimal(str(total))

        known_income_categories = set(income_category_order)
        personal_caller_sources: dict[str, Decimal] = {}
        personal_caller_other_income = _ZERO
        for cat, total in raw_caller.items():
            if cat and cat in known_income_categories and total > _ZERO:
                personal_caller_sources[cat] = total
            else:
                personal_caller_other_income += total
        income = sum(personal_caller_sources.values(), start=_ZERO) + personal_caller_other_income
    else:
        breakdown = await income_breakdown_for_household_view(
            db,
            caller_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
        )
        income = breakdown.total
        # Silence "possibly unbound" warnings — personal_caller_* only used in
        # personal view branch below.
        personal_caller_sources = {}
        personal_caller_other_income = _ZERO

    # ---- personal allocation (household view) / gastos del hogar (personal view) ---
    # Both get passed into `spendable_ceiling` via `personal_allocation` — they
    # play the same role (a fixed outflow before discretionary spend).
    if view == "household":
        personal_allocation_amount = await get_household_personal_allocation(
            db, household_id=household_id, currency=currency
        )
        gastos_hogar_personal = _ZERO
    else:
        personal_allocation_amount = _ZERO
        caller_ratio = await _caller_ratio_share(db, household_id=household_id, user_id=user_id)
        shared_outflows = await _household_shared_outflows(
            db, household_id=household_id, month=month, currency=currency
        )
        gastos_hogar_personal = (shared_outflows * caller_ratio).quantize(Decimal("0.01"))

    # ---- spent (excluding savings-equivalent categories) ----------------
    month_txns = await _fetch_month_transactions(
        db,
        view=view,
        user_id=user_id,
        household_id=household_id,
        month=month,
        currency=currency,
    )
    mtd_spent = _ZERO
    mtd_savings_progress = _ZERO
    mtd_by_category: dict[str, Decimal] = {}
    for t in month_txns:
        # Luka stores expense amounts as negative; normalize to positive
        # before aggregating so spent/category totals are outflows, not net.
        amt = abs(Decimal(str(t.amount)))
        if is_savings_category(t.category):
            mtd_savings_progress += amt
            continue
        mtd_spent += amt
        if t.category:
            mtd_by_category[t.category] = mtd_by_category.get(t.category, _ZERO) + amt

    # ---- spendable -------------------------------------------------------
    spendable_amount = spendable_ceiling(
        income=income,
        known_bills=known_bills,
        cuotas_this_month=cuotas_block.this_month,
        savings_target=savings_target_amount,
        personal_allocation=personal_allocation_amount + gastos_hogar_personal,
    )
    spendable_remaining = spendable_amount - mtd_spent
    if spendable_remaining < _ZERO:
        spendable_remaining = _ZERO  # clamp for display; UI can show an overdraft badge
    pct_used = (mtd_spent / spendable_amount) if spendable_amount > _ZERO else _ZERO
    # Round pct_used to 3 decimal places for a sane API contract.
    pct_used_rounded = Decimal(str(round(float(pct_used), 3))) if pct_used else _ZERO
    spendable_block = SpendableBlock(
        amount=spendable_amount,
        spent=mtd_spent,
        remaining=spendable_remaining,
        pct_used=pct_used_rounded,
    )

    # ---- risk categories -------------------------------------------------
    hist_stats = await _three_month_category_stats(
        db,
        view=view,
        user_id=user_id,
        household_id=household_id,
        month=month,
        currency=currency,
    )
    caps = await _category_caps(db, household_id, month, currency)

    # Risk-alert list (for the RiskAlertBand UI): historical volatility-based,
    # independent of this month's spend. A quiet category with volatile history
    # still belongs here.
    ranked = select_risk_categories(hist_stats, top_n=5)
    risk_categories: list[RiskCategory] = []

    for name, _score in ranked:
        mean, std, _n = hist_stats[name]
        spent_this_month = mtd_by_category.get(name, _ZERO)
        # Explicit None check: a user who sets cap=0 means "don't spend here
        # this month". Using `or` would treat Decimal("0") as falsy and
        # silently fall back to the historical mean+std cap.
        cap = caps[name] if name in caps else (mean + std)
        projected, projected_std = pace_forecast(
            spent_so_far=spent_this_month,
            current_day=today_day,
            days_in_month=days_in_month,
            historical_std=std,
        )
        p_over = overshoot_probability(projected=projected, cap=cap, std=projected_std)
        risk_categories.append(
            RiskCategory(
                name=name,
                spent=spent_this_month,
                cap=cap,
                historical_mean=mean,
                historical_std=std,
                p_overshoot=p_over,
                projected_final=projected,
                alert=p_over > Decimal("0.70"),
            )
        )

    # Sankey level-3 breakdown: top 5 spenders *this month* (not the risk list),
    # so the largest actual categories always get their own node instead of
    # getting lumped into "Otras categorías". The breakdown answers "where did
    # the money go?" while the risk list answers "where might I overshoot?".
    top_spent_totals: list[tuple[str, Decimal]] = sorted(
        ((cat, amt) for cat, amt in mtd_by_category.items() if amt > _ZERO),
        key=lambda kv: kv[1],
        reverse=True,
    )[:5]

    # A node in the breakdown gets the red `risk=True` treatment only if it
    # independently qualified for the alert — big spend doesn't mean unsafe.
    risk_category_set: frozenset[str] = frozenset(rc.name for rc in risk_categories if rc.alert)

    # "Other" bucket for the Sankey = everything spent this month that isn't
    # one of the top spenders. Derive from mtd_spent (not mtd_by_category) so
    # uncategorized transactions — which never make it into mtd_by_category but
    # do count toward mtd_spent — still show up here.
    top_spent_sum = sum((s for _, s in top_spent_totals), start=_ZERO)
    other_spent = mtd_spent - top_spent_sum
    if other_spent < _ZERO:
        other_spent = _ZERO

    # ---- runway ----------------------------------------------------------
    daily_burn = await _daily_burn_14d(
        db, view=view, user_id=user_id, household_id=household_id, currency=currency
    )
    days_remaining = runway_days(spendable_remaining, daily_burn)
    days_to_payday = await _days_to_payday(db, user_id, month, days_in_month)
    runway_block = RunwayBlock(
        days_remaining=days_remaining,
        days_to_payday=days_to_payday,
        daily_burn_14d=daily_burn,
        alert=days_remaining < days_to_payday,
    )

    # ---- savings target block -------------------------------------------
    pct_complete = (
        (mtd_savings_progress / savings_target_amount) if savings_target_amount > _ZERO else _ZERO
    )
    savings_block = SavingsTargetBlock(
        target=savings_target_amount,
        progress=mtd_savings_progress,
        pct_complete=Decimal(str(round(float(pct_complete), 3))) if pct_complete else _ZERO,
    )

    # ---- sankey ----------------------------------------------------------
    if view == "household":
        sankey = _build_hogar_sankey(
            breakdown=breakdown,
            known_bills=known_bills,
            cuotas_this_month=cuotas_block.this_month,
            savings_target=savings_target_amount,
            personal_allocation=personal_allocation_amount,
            spendable_amount=spendable_amount,
            top_spent_totals=top_spent_totals,
            risk_category_set=risk_category_set,
            other_spent=other_spent,
            income_category_order=income_category_order,
        )
    else:
        sankey = _build_personal_sankey(
            caller_sources=personal_caller_sources,
            caller_other_income=personal_caller_other_income,
            gastos_hogar=gastos_hogar_personal,
            known_bills=known_bills,
            cuotas_this_month=cuotas_block.this_month,
            savings_target=savings_target_amount,
            spendable_amount=spendable_amount,
            top_spent_totals=top_spent_totals,
            risk_category_set=risk_category_set,
            other_spent=other_spent,
            income_category_order=income_category_order,
        )

    return BudgetV2Response(
        view=view,
        month=month,
        currency=currency,
        currencies_available=sorted(set(currencies_available)),
        sankey=sankey,
        spendable=spendable_block,
        risk_categories=risk_categories,
        runway=runway_block,
        cuotas=cuotas_block,
        savings_target=savings_block,
    )


# ========================================================= node drilldown
#
# Powers the "click a Sankey node to see the top transactions" UX. Each
# node id routes to a different query — see `get_node_drilldown` for the
# full dispatch table. Unsupported nodes (hubs, synthetic, pass-through)
# return an empty block with an explanatory `empty_reason`.


def _unslugify_match(slug: str, categories: list[str]) -> str | None:
    """Given a slug produced by `_slugify`, find the original category name
    from `categories`. Returns None if no match."""
    return next((c for c in categories if _slugify(c) == slug), None)


async def _top_expense_txns(
    db: AsyncSession,
    *,
    view: str,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
    category_filter: str | None,
    exclude_categories: list[str] | None = None,
    limit: int,
) -> list[DrilldownItem]:
    """Top-N expense transactions by absolute amount for the given scope.

    Scope is defined by `view` (same rules as `_fetch_month_transactions`):
    household → shared splits only, personal → split_type personal OR NULL.
    `category_filter` narrows to one category; `exclude_categories` is the
    inverse (used for the `spent_other` node).
    """
    first_day, first_day_next, _ = _month_bounds_datetime(month)
    base = (
        select(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.raw_merchant_name,
            Transaction.amount,
            Transaction.category,
            Transaction.source_bank_name,
            TransactionSplit.split_type,
            BankAccount.bank_name,
            CanonicalMerchant.display_name.label("merchant_display"),
        )
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
    )
    if view == "personal":
        base = base.outerjoin(
            TransactionSplit, TransactionSplit.transaction_id == Transaction.id
        ).where(
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
        base = base.join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id).where(
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
            TransactionSplit.split_type == "shared",
        )

    if category_filter is not None:
        base = base.where(Transaction.category == category_filter)
    if exclude_categories:
        base = base.where(Transaction.category.notin_(exclude_categories))

    base = base.order_by(func.abs(Transaction.amount).desc()).limit(limit)

    rows = await db.execute(base)
    items: list[DrilldownItem] = []
    for row in rows:
        merchant = row.merchant_display or row.raw_merchant_name or "—"
        items.append(
            DrilldownItem(
                id=str(row.id),
                date=row.transaction_date.date()
                if hasattr(row.transaction_date, "date")
                else row.transaction_date,
                merchant=merchant,
                amount=abs(Decimal(str(row.amount))),
                category=row.category,
                bank_name=row.bank_name or row.source_bank_name,
                split_type=row.split_type,
            )
        )
    return items


async def _top_income_txns(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
    category_filter: str | None,
    limit: int,
) -> list[DrilldownItem]:
    """Top-N income txns for the caller. No income drilldown in hogar view —
    the caller for a household view is not necessarily the owner of the income,
    and we don't want to reveal other members' income-level breakdowns."""
    first_day, first_day_next, _ = _month_bounds_datetime(month)
    stmt = (
        select(
            Transaction.id,
            Transaction.transaction_date,
            Transaction.raw_merchant_name,
            Transaction.amount,
            Transaction.category,
            Transaction.source_bank_name,
            BankAccount.bank_name,
            CanonicalMerchant.display_name.label("merchant_display"),
        )
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "income",
            *counts_toward_totals_clauses(),
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
    )
    if category_filter is not None:
        stmt = stmt.where(Transaction.category == category_filter)
    else:
        # "Otros ingresos" = income with category not in user's known income prefs
        income_cat_rows = await db.execute(
            text(
                """
                SELECT category FROM user_category_preferences
                WHERE user_id = :uid AND category_type = 'income'
                """
            ),
            {"uid": str(user_id)},
        )
        known = [r[0] for r in income_cat_rows]
        if known:
            stmt = stmt.where(
                (Transaction.category.is_(None)) | (Transaction.category.notin_(known))
            )

    stmt = stmt.order_by(func.abs(Transaction.amount).desc()).limit(limit)
    rows = await db.execute(stmt)
    items: list[DrilldownItem] = []
    for row in rows:
        merchant = row.merchant_display or row.raw_merchant_name or "—"
        items.append(
            DrilldownItem(
                id=str(row.id),
                date=row.transaction_date.date()
                if hasattr(row.transaction_date, "date")
                else row.transaction_date,
                merchant=merchant,
                amount=abs(Decimal(str(row.amount))),
                category=row.category,
                bank_name=row.bank_name or row.source_bank_name,
                split_type=None,
            )
        )
    return items


async def get_node_drilldown(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    month: date,
    currency: str | None,
    view: str,
    node_id: str,
    limit: int = 5,
) -> DrilldownBlock:
    """Route a Sankey node id to its top-N transaction list.

    Supported patterns:
    - `src_<slug>` (personal view): income txns of that category
    - `src_otros_ingresos` (personal view): uncategorised / other income
    - `spent_<slug>`: top expense txns in that category (scope by view)
    - `spent_other`: top expense txns outside the top-5 categories
    - `gastos_hogar_personal` (personal view) / `disponible_hogar` (hogar
      view): top shared expense txns across all categories
    - `meta_ahorro` / `meta_ahorro_personal`: top savings-category txns

    Everything else (hubs, synthetic deficit, spent_remaining, member_*)
    returns an empty block with a reason.
    """
    if view not in ("personal", "household"):
        raise ValueError(f"invalid view: {view!r}")

    month = date(month.year, month.month, 1)
    if not currency:
        user_row = await db.execute(select(User.preferred_currency).where(User.id == user_id))
        currency = user_row.scalar_one_or_none() or "CLP"

    # Non-actionable nodes — return empty with hint.
    skip = {
        "ingresos_hogar",
        "ingresos_personales",
        "disponible_personal",
        "otras_fuentes",
        "deficit_personal",
        "spent_remaining",
        "gastos_fijos",
        "gastos_fijos_personal",
        "cuotas",
        "cuotas_personal",
        "gasto_personal",
    }
    if node_id in skip or node_id.startswith("member_"):
        return DrilldownBlock(
            node_id=node_id,
            label=node_id,
            kind="empty",
            empty_reason="Este nodo no tiene transacciones individuales para mostrar.",
            items=[],
        )

    # ---- meta de ahorro -------------------------------------------------
    if node_id in ("meta_ahorro", "meta_ahorro_personal"):
        first_day, first_day_next, _ = _month_bounds_datetime(month)
        stmt = (
            select(
                Transaction.id,
                Transaction.transaction_date,
                Transaction.raw_merchant_name,
                Transaction.amount,
                Transaction.category,
                Transaction.source_bank_name,
                BankAccount.bank_name,
                CanonicalMerchant.display_name.label("merchant_display"),
            )
            .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
            .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
            .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.currency == currency,
                Transaction.transaction_type == "expense",
                *counts_toward_totals_clauses(),
                Transaction.transaction_date >= first_day,
                Transaction.transaction_date < first_day_next,
            )
            .order_by(func.abs(Transaction.amount).desc())
            .limit(limit)
        )
        if view == "personal":
            stmt = stmt.where(Transaction.user_id == user_id)
        rows = await db.execute(stmt)
        items: list[DrilldownItem] = []
        for row in rows:
            if not row.category or not is_savings_category(row.category):
                continue
            items.append(
                DrilldownItem(
                    id=str(row.id),
                    date=row.transaction_date.date()
                    if hasattr(row.transaction_date, "date")
                    else row.transaction_date,
                    merchant=row.merchant_display or row.raw_merchant_name or "—",
                    amount=abs(Decimal(str(row.amount))),
                    category=row.category,
                    bank_name=row.bank_name or row.source_bank_name,
                    split_type=None,
                )
            )
        return DrilldownBlock(
            node_id=node_id, label="Meta de ahorro", kind="transactions", items=items
        )

    # ---- gastos del hogar (shared pool) ---------------------------------
    if node_id in ("gastos_hogar_personal", "disponible_hogar"):
        items = await _top_expense_txns(
            db,
            view="household",  # always shared scope
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
            category_filter=None,
            limit=limit,
        )
        return DrilldownBlock(
            node_id=node_id, label="Gastos del hogar", kind="transactions", items=items
        )

    # ---- income sources (personal view only) ----------------------------
    if node_id.startswith("src_"):
        if view != "personal":
            return DrilldownBlock(
                node_id=node_id,
                label=node_id,
                kind="empty",
                empty_reason="El detalle de ingresos solo está disponible en la vista personal.",
                items=[],
            )
        slug = node_id[len("src_") :]
        if slug == "otros_ingresos":
            items = await _top_income_txns(
                db,
                user_id=user_id,
                household_id=household_id,
                month=month,
                currency=currency,
                category_filter=None,
                limit=limit,
            )
            return DrilldownBlock(
                node_id=node_id, label="Otros ingresos", kind="transactions", items=items
            )
        # Known income category — look up the original name via prefs
        income_cat_rows = await db.execute(
            text(
                """
                SELECT category FROM user_category_preferences
                WHERE user_id = :uid AND category_type = 'income'
                """
            ),
            {"uid": str(user_id)},
        )
        known = [r[0] for r in income_cat_rows]
        cat = _unslugify_match(slug, known)
        if not cat:
            return DrilldownBlock(
                node_id=node_id,
                label=slug,
                kind="empty",
                empty_reason="Categoría no encontrada.",
                items=[],
            )
        items = await _top_income_txns(
            db,
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
            category_filter=cat,
            limit=limit,
        )
        return DrilldownBlock(node_id=node_id, label=cat, kind="transactions", items=items)

    # ---- spent_<slug> / spent_other -------------------------------------
    if node_id.startswith("spent_"):
        # Recompute the top-5 categories we used in the Sankey so `spent_other`
        # can invert it and `spent_<slug>` can resolve the slug back to the
        # original category name.
        mtd_by_category: dict[str, Decimal] = {}
        month_txns = await _fetch_month_transactions(
            db,
            view=view,
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
        )
        for t in month_txns:
            if not t.category or is_savings_category(t.category):
                continue
            amt = abs(Decimal(str(t.amount)))
            mtd_by_category[t.category] = mtd_by_category.get(t.category, _ZERO) + amt
        top_cats = [
            c for c, _ in sorted(mtd_by_category.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]

        if node_id == "spent_other":
            items = await _top_expense_txns(
                db,
                view=view,
                user_id=user_id,
                household_id=household_id,
                month=month,
                currency=currency,
                category_filter=None,
                exclude_categories=top_cats,
                limit=limit,
            )
            return DrilldownBlock(
                node_id=node_id, label="Otras categorías", kind="transactions", items=items
            )

        slug = node_id[len("spent_") :]
        cat = _unslugify_match(slug, list(mtd_by_category.keys()))
        if not cat:
            return DrilldownBlock(
                node_id=node_id,
                label=slug,
                kind="empty",
                empty_reason="Categoría no encontrada.",
                items=[],
            )
        items = await _top_expense_txns(
            db,
            view=view,
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
            category_filter=cat,
            limit=limit,
        )
        return DrilldownBlock(node_id=node_id, label=cat, kind="transactions", items=items)

    return DrilldownBlock(
        node_id=node_id, label=node_id, kind="empty", empty_reason="Nodo no soportado.", items=[]
    )
