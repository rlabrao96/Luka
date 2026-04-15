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
    get_household_savings_target,
    get_payday_day_of_month,
    get_savings_target,
)
from modules.budgets.v2_schemas import (
    BudgetV2Response,
    CuotasBlock,
    RiskCategory,
    RunwayBlock,
    SankeyBlock,
    SankeyLink,
    SankeyNode,
    SavingsTargetBlock,
    SpendableBlock,
)
from modules.households.contribution_service import (
    income_for_household_view,
    income_for_personal_view,
)
from modules.households.models import (
    BankAccount,
    Household,
    HouseholdBudgetAllocation,
    HouseholdMember,
)
from modules.subscriptions.read import (
    get_household_known_bills,
    get_user_known_bills,
)
from modules.transactions.models import Transaction


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
) -> Decimal:
    """Sum of known_bills for members in `reimbursement` mode.

    These bills don't hit the household pot — we subtract them from the
    household known_bills sum in the household view.
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
        total += await get_user_known_bills(db, user_id, currency)
    return total


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
    """Pull expense transactions for the month in one query."""
    first_day, first_day_next, _ = _month_bounds_datetime(month)
    base = select(Transaction).where(
        Transaction.household_id == household_id,
        Transaction.currency == currency,
        Transaction.transaction_type == "expense",
        Transaction.transaction_date >= first_day,
        Transaction.transaction_date < first_day_next,
    )
    if view == "personal":
        base = base.where(Transaction.user_id == user_id)
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
        q = select(
            Transaction.category,
            func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("total"),
        ).where(
            Transaction.household_id == household_id,
            Transaction.currency == currency,
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date < first_day_next,
        )
        if view == "personal":
            q = q.where(Transaction.user_id == user_id)
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
) -> dict[str, Decimal]:
    """Return any per-category monthly caps from `category_budgets` for this month."""
    rows = await db.execute(
        text(
            """
            SELECT category, amount FROM category_budgets
            WHERE household_id = :hid AND month = :month
            """
        ),
        {"hid": str(household_id), "month": month},
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

    q = select(Transaction).where(
        Transaction.household_id == household_id,
        Transaction.currency == currency,
        Transaction.transaction_type == "expense",
        Transaction.transaction_date >= fourteen_days_ago,
        Transaction.transaction_date <= today,
    )
    if view == "personal":
        q = q.where(Transaction.user_id == user_id)
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


def _build_sankey(
    *,
    income: Decimal,
    known_bills: Decimal,
    cuotas_this_month: Decimal,
    savings_target: Decimal,
    spendable_amount: Decimal,
    top_risk_totals: list[tuple[str, Decimal]],  # [(category, spent_this_month)]
    other_spent: Decimal,
) -> SankeyBlock:
    """Build the nodes/links block for the Sankey diagram.

    Flow conservation:
      income → [known_bills, cuotas, savings_target, spendable]
      spendable → [per-risk-category spent, other_spent, spent_remaining]

    Overspent months (mtd_spent > spendable_amount): the excess came from
    a non-income source (savings drawdown, credit, prior balance). We add
    a synthetic `otras_fuentes` source node that feeds the extra into
    spendable so the Sankey stays flow-conserving and the user sees the
    shortfall visualized as a distinct inflow.
    """
    total_spent = sum((s for _, s in top_risk_totals), start=_ZERO) + other_spent
    spent_remaining = spendable_amount - total_spent
    if spent_remaining < _ZERO:
        spent_remaining = _ZERO

    # Overspent case: spendable needs to expand to cover the actual outflows,
    # so the Sankey conserves. The "extra" goes into otras_fuentes.
    if total_spent > spendable_amount:
        sankey_spendable = total_spent
        otras_fuentes = total_spent - spendable_amount
    else:
        sankey_spendable = spendable_amount
        otras_fuentes = _ZERO

    nodes: list[SankeyNode] = [
        SankeyNode(id="income", label="Ingresos", value=income),
    ]
    if otras_fuentes > _ZERO:
        nodes.append(SankeyNode(id="otras_fuentes", label="Otras fuentes", value=otras_fuentes))
    if known_bills > _ZERO:
        nodes.append(SankeyNode(id="known_bills", label="Gastos fijos", value=known_bills))
    if cuotas_this_month > _ZERO:
        nodes.append(SankeyNode(id="cuotas", label="Cuotas del mes", value=cuotas_this_month))
    if savings_target > _ZERO:
        nodes.append(SankeyNode(id="savings_target", label="Meta de ahorro", value=savings_target))
    if sankey_spendable > _ZERO:
        nodes.append(SankeyNode(id="spendable", label="Disponible", value=sankey_spendable))
    for category, spent in top_risk_totals:
        if spent <= _ZERO:
            continue  # drop zero-spend risk categories from the visualization
        nodes.append(
            SankeyNode(
                id=f"spent_{_slugify(category)}",
                label=category,
                value=spent,
                risk=True,
            )
        )
    if other_spent > _ZERO:
        # Label as "Otras categorías" so it never collides with a category
        # literally named "Otros" that made it into top_risk_totals.
        nodes.append(SankeyNode(id="spent_other", label="Otras categorías", value=other_spent))
    if spent_remaining > _ZERO:
        nodes.append(
            SankeyNode(id="spent_remaining", label="Aún disponible", value=spent_remaining)
        )

    # Income outflow must never exceed income itself. When known_bills +
    # cuotas + savings_target > income (deep-overspent case), we can't
    # honor all of them from income alone; clamp the income → spendable
    # link to whatever income has left and route the rest via otras_fuentes.
    fixed_outflow = known_bills + cuotas_this_month + savings_target
    income_to_spendable = sankey_spendable
    if fixed_outflow + sankey_spendable > income:
        # Prefer honoring fixed_outflow (the user actually paid those);
        # what's left of income flows to spendable, the rest comes from
        # otras_fuentes.
        income_to_spendable = max(_ZERO, income - fixed_outflow)
        extra_needed_from_otras = sankey_spendable - income_to_spendable
        if extra_needed_from_otras > otras_fuentes:
            # The otras_fuentes sized by total_spent-spendable_amount isn't
            # enough to cover this deeper case; expand it.
            extra_otras = extra_needed_from_otras - otras_fuentes
            otras_fuentes += extra_otras
            # Update or insert the otras_fuentes node
            for n in nodes:
                if n.id == "otras_fuentes":
                    n.value = otras_fuentes
                    break
            else:
                nodes.insert(
                    1, SankeyNode(id="otras_fuentes", label="Otras fuentes", value=otras_fuentes)
                )

    links: list[SankeyLink] = []
    if known_bills > _ZERO:
        links.append(SankeyLink(source="income", target="known_bills", value=known_bills))
    if cuotas_this_month > _ZERO:
        links.append(SankeyLink(source="income", target="cuotas", value=cuotas_this_month))
    if savings_target > _ZERO:
        links.append(SankeyLink(source="income", target="savings_target", value=savings_target))
    if income_to_spendable > _ZERO:
        links.append(SankeyLink(source="income", target="spendable", value=income_to_spendable))
    if otras_fuentes > _ZERO:
        links.append(SankeyLink(source="otras_fuentes", target="spendable", value=otras_fuentes))
    for category, spent in top_risk_totals:
        if spent <= _ZERO:
            continue
        links.append(
            SankeyLink(
                source="spendable",
                target=f"spent_{_slugify(category)}",
                value=spent,
            )
        )
    if other_spent > _ZERO:
        links.append(SankeyLink(source="spendable", target="spent_other", value=other_spent))
    if spent_remaining > _ZERO:
        links.append(
            SankeyLink(source="spendable", target="spent_remaining", value=spent_remaining)
        )

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
    assert view in ("personal", "household"), f"invalid view: {view!r}"

    # ---- resolve currency -------------------------------------------------
    if not currency:
        user_row = await db.execute(select(User.preferred_currency).where(User.id == user_id))
        currency = user_row.scalar_one_or_none() or "CLP"

    # Force month=day-1 to match the DATE column convention.
    month = date(month.year, month.month, 1)
    _, _, days_in_month = _month_bounds_datetime(month)
    today_day = _today_day_in_month(month, days_in_month)

    # ---- currencies available --------------------------------------------
    currencies_available = await _currencies_available(
        db, view=view, user_id=user_id, household_id=household_id
    )
    if currency not in currencies_available:
        currencies_available = sorted(set(currencies_available) | {currency})

    # ---- known_bills -----------------------------------------------------
    if view == "personal":
        known_bills = await get_user_known_bills(db, user_id, currency)
    else:
        raw = await get_household_known_bills(db, household_id, currency)
        reimb = await _reimbursement_members_known_bills(db, household_id, currency)
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

    # ---- income ----------------------------------------------------------
    # Contribution-mode dispatch lives in `contribution_service`; this file
    # is a pure caller so the privacy invariant has exactly one enforcement
    # point. Do NOT reintroduce inline income queries here.
    if view == "personal":
        income = await income_for_personal_view(
            db,
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
        )
    else:
        income = await income_for_household_view(
            db,
            household_id=household_id,
            month=month,
            currency=currency,
        )

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
    caps = await _category_caps(db, household_id, month)

    ranked = select_risk_categories(hist_stats, top_n=5)
    risk_categories: list[RiskCategory] = []
    top_risk_totals: list[tuple[str, Decimal]] = []

    for name, _score in ranked:
        mean, std, _n = hist_stats[name]
        spent_this_month = mtd_by_category.get(name, _ZERO)
        cap = caps.get(name) or (mean + std)
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
        top_risk_totals.append((name, spent_this_month))

    # "Other" bucket for the Sankey = everything spent this month that isn't
    # one of the top risk categories. Derive from mtd_spent (not
    # mtd_by_category) so uncategorized transactions — which never make it
    # into mtd_by_category but do count toward mtd_spent — still show up.
    risk_totals_sum = sum((s for _, s in top_risk_totals), start=_ZERO)
    other_spent = mtd_spent - risk_totals_sum
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
    sankey = _build_sankey(
        income=income,
        known_bills=known_bills,
        cuotas_this_month=cuotas_block.this_month,
        savings_target=savings_target_amount,
        spendable_amount=spendable_amount,
        top_risk_totals=top_risk_totals,
        other_spent=other_spent,
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


# `HouseholdBudgetAllocation` import kept so future PRs can hook allocation-based
# caps without touching the import block — Chunk F may use it. Silence lint.
_ = HouseholdBudgetAllocation
_ = BankAccount
_ = Household
