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

import uuid
from datetime import date
from decimal import Decimal, ROUND_FLOOR

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.budgets.cuota_service import get_active_cuotas_summary
from modules.budgets.forecast import (
    overshoot_probability,
    pace_forecast,
    runway_days,
    select_risk_categories,
    spendable_ceiling,
)
from modules.budgets.savings_categories import is_savings_category
from modules.budgets.user_budget_settings_service import (
    get_household_personal_allocation,
)
from modules.budgets.v2_schemas import (
    BudgetV2Response,
    CuotasBlock,
    DrilldownBlock,
    DrilldownItem,
    RiskCategory,
    RunwayBlock,
    SavingsTargetBlock,
    SpendableBlock,
)
from modules.households.contribution_service import (
    income_breakdown_for_household_view,
)
from modules.households.models import BankAccount
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.models import Merchant
from modules.subscriptions.read import (
    get_household_unpaid_known_bills,
    get_user_personal_unpaid_known_bills,
)
from modules.transactions.models import Transaction, TransactionSplit
from modules.transactions.totals import counts_toward_totals_clauses


# ---------------------------------------------------------------------------
# H16 split: fetchers live in v2_queries, Sankey builders in v2_sankey.
# The names below are re-exported so existing imports (tests, callers) keep
# working; new code should import from the specific module.
# ---------------------------------------------------------------------------
from modules.budgets.v2_queries import (  # noqa: F401
    _caller_ratio_share,
    _category_caps,
    _currencies_available,
    _daily_burn_14d,
    _days_to_payday,
    _household_savings_target,
    _household_shared_outflows,
    _month_category_sums,
    _personal_savings_target,
    _personal_spent_expr,
    _reimbursement_members_known_bills,
    _three_month_category_stats,
)
from modules.budgets.v2_sankey import (  # noqa: F401
    _build_hogar_sankey,
    _build_personal_sankey,
    _pay_first_fit,
    _slugify,
)
from core.dates import (  # noqa: F401
    month_bounds_datetime as _month_bounds_datetime,
    month_bounds_date as _month_bounds_date,
    prior_month as _prior_month,
    today_day_in_month as _today_day_in_month,
)

_ZERO = Decimal("0")


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
    _, _, days_in_month = _month_bounds_datetime(month, currency)
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
        first_day, first_day_next, _ = _month_bounds_datetime(month, currency)
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
    category_sums = await _month_category_sums(
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
    for category, amt in category_sums:
        if is_savings_category(category):
            mtd_savings_progress += amt
            continue
        mtd_spent += amt
        if category:
            mtd_by_category[category] = mtd_by_category.get(category, _ZERO) + amt

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
    _, _, _days_in_month = _month_bounds_datetime(month, currency)
    _today_day = _today_day_in_month(month, _days_in_month, currency)
    _days_left = max(1, _days_in_month - _today_day + 1)
    safe_today = (spendable_remaining / Decimal(_days_left)).quantize(
        Decimal("1"), rounding=ROUND_FLOOR
    )
    spendable_block = SpendableBlock(
        amount=spendable_amount,
        spent=mtd_spent,
        remaining=spendable_remaining,
        pct_used=pct_used_rounded,
        safe_to_spend_today=safe_today,
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

    Scope is defined by `view` (same rules as `_month_category_sums`):
    household → shared splits only, personal → split_type personal OR NULL.
    `category_filter` narrows to one category; `exclude_categories` is the
    inverse (used for the `spent_other` node).
    """
    first_day, first_day_next, _ = _month_bounds_datetime(month, currency)
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
    first_day, first_day_next, _ = _month_bounds_datetime(month, currency)
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
        first_day, first_day_next, _ = _month_bounds_datetime(month, currency)
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
        category_sums = await _month_category_sums(
            db,
            view=view,
            user_id=user_id,
            household_id=household_id,
            month=month,
            currency=currency,
        )
        for category, amt in category_sums:
            if not category or is_savings_category(category):
                continue
            mtd_by_category[category] = mtd_by_category.get(category, _ZERO) + amt
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
