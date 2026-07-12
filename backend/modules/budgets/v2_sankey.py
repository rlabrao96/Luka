"""Budget v2 — Sankey graph builders (split from v2_service, see H16).

Pure functions: they take already-fetched Decimals and emit SankeyBlock
structures. Flow conservation is regression-tested in
``tests/test_budget_v3_sankey.py`` — every node's inflow must equal its
outflow (±1 minor unit).
"""

from __future__ import annotations

from decimal import Decimal

from modules.budgets.v2_schemas import (
    SankeyBlock,
    SankeyLink,
    SankeyNode,
)
from modules.households.contribution_service import HouseholdIncomeBreakdown

_ZERO = Decimal("0")


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
