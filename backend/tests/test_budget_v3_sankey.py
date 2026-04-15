"""Budget v3 Sankey tests — multi-level structure, caller-relative privacy,
flow conservation, personal allocation wiring."""

from __future__ import annotations

import uuid
from decimal import Decimal

from modules.budgets.v2_schemas import SankeyNode
from modules.budgets.v2_service import _build_hogar_sankey, _build_personal_sankey, _pay_first_fit
from modules.households.contribution_service import (
    HouseholdIncomeBreakdown,
    OtherMemberContribution,
)


class TestSankeyNodeAdditiveFields:
    def test_level_defaults_to_none(self):
        node = SankeyNode(id="income", label="Ingresos", value=Decimal("100"))
        assert node.level is None
        assert node.kind is None
        assert node.member_id is None

    def test_level_accepts_int(self):
        node = SankeyNode(
            id="sueldo",
            label="Sueldo",
            value=Decimal("800"),
            level=0,
            kind="source",
        )
        assert node.level == 0
        assert node.kind == "source"

    def test_member_id_accepts_string(self):
        node = SankeyNode(
            id="other_alice",
            label="Ingresos Alice",
            value=Decimal("500"),
            level=0,
            kind="source",
            member_id="00000000-0000-0000-0000-000000000001",
        )
        assert node.member_id == "00000000-0000-0000-0000-000000000001"


class TestPayFirstFit:
    def test_enough_income_covers_target(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("500"),
        )
        assert from_income == Decimal("100")
        assert from_otras == Decimal("0")
        assert remaining == Decimal("400")

    def test_partial_income_splits_between_income_and_otras(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("30"),
        )
        assert from_income == Decimal("30")
        assert from_otras == Decimal("70")
        assert remaining == Decimal("0")

    def test_zero_income_sends_full_target_to_otras(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("100"),
            remaining_income=Decimal("0"),
        )
        assert from_income == Decimal("0")
        assert from_otras == Decimal("100")
        assert remaining == Decimal("0")

    def test_zero_target_returns_zero_zero(self):
        from_income, from_otras, remaining = _pay_first_fit(
            target=Decimal("0"),
            remaining_income=Decimal("500"),
        )
        assert from_income == Decimal("0")
        assert from_otras == Decimal("0")
        assert remaining == Decimal("500")


def _sample_breakdown_full_full() -> HouseholdIncomeBreakdown:
    return HouseholdIncomeBreakdown(
        total=Decimal("2000"),
        caller_sources={"Sueldo": Decimal("1000"), "Bonus": Decimal("200")},
        caller_other_income=Decimal("0"),
        other_members=[
            OtherMemberContribution(
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                display_name="Cami",
                amount=Decimal("800"),
                mode="full",
            )
        ],
    )


class TestBuildHogarSankey:
    def test_emits_level_0_sources_for_caller(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "src_sueldo" in node_ids
        assert "src_bonus" in node_ids
        assert "member_00000000-0000-0000-0000-000000000001" in node_ids
        assert "ingresos_hogar" in node_ids

    def test_level_0_nodes_have_level_zero_and_kind_source(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        for node in block.nodes:
            if node.id.startswith("src_") or node.id.startswith("member_"):
                assert node.level == 0
                assert node.kind == "source"

    def test_ingresos_hogar_is_level_1_hub(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        hub = next(n for n in block.nodes if n.id == "ingresos_hogar")
        assert hub.level == 1
        assert hub.kind == "hub"
        assert hub.value == Decimal("2000")

    def test_level_2_allocation_nodes_are_level_two(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        allocation_ids = {
            "meta_ahorro",
            "gastos_fijos",
            "cuotas",
            "gasto_personal",
            "disponible_hogar",
        }
        for node in block.nodes:
            if node.id in allocation_ids:
                assert node.level == 2
                assert node.kind == "allocation"

    def test_flow_conservation_each_intermediate(self):
        """Every non-source / non-terminal node: inflow == outflow == value."""
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("400"),
            spendable_amount=Decimal("1000"),
            top_risk_totals=[("Supermercado", Decimal("300"))],
            other_spent=Decimal("100"),
            income_category_order=["Sueldo", "Bonus"],
        )

        inflows: dict[str, Decimal] = {}
        outflows: dict[str, Decimal] = {}
        for link in block.links:
            outflows[link.source] = outflows.get(link.source, Decimal("0")) + link.value
            inflows[link.target] = inflows.get(link.target, Decimal("0")) + link.value

        # Ingresos Hogar (level 1 hub) must have inflow == outflow == its value
        hub_inflow = inflows.get("ingresos_hogar", Decimal("0"))
        hub_outflow = outflows.get("ingresos_hogar", Decimal("0"))
        hub_node_value = next(n.value for n in block.nodes if n.id == "ingresos_hogar")
        assert hub_inflow == hub_node_value == hub_outflow

        # Disponible hogar (intermediate) must have inflow == outflow
        disp_inflow = inflows.get("disponible_hogar", Decimal("0"))
        disp_outflow = outflows.get("disponible_hogar", Decimal("0"))
        assert disp_inflow == disp_outflow

    def test_gasto_personal_hidden_when_zero(self):
        bd = _sample_breakdown_full_full()
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("300"),
            personal_allocation=Decimal("0"),  # setting unset
            spendable_amount=Decimal("1400"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "gasto_personal" not in node_ids

    def test_fixed_member_node_labeled_contribucion_fija(self):
        bd = HouseholdIncomeBreakdown(
            total=Decimal("1500"),
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            other_members=[
                OtherMemberContribution(
                    user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                    display_name="Cami",
                    amount=Decimal("500"),
                    mode="fixed",
                )
            ],
        )
        block = _build_hogar_sankey(
            breakdown=bd,
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            personal_allocation=Decimal("0"),
            spendable_amount=Decimal("1200"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        cami_node = next(
            n for n in block.nodes if n.id == "member_00000000-0000-0000-0000-000000000002"
        )
        assert "Contribución fija" in cami_node.label
        assert "Cami" in cami_node.label


class TestBuildPersonalSankey:
    def test_level_0_is_caller_sources_only_no_other_members(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000"), "Bonus": Decimal("200")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("900"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        node_ids = {n.id for n in block.nodes}
        # No member_ nodes — personal view doesn't aggregate other members
        assert not any(nid.startswith("member_") for nid in node_ids)
        assert "src_sueldo" in node_ids
        assert "src_bonus" in node_ids

    def test_level_1_hub_exists(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("700"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        hub = next(n for n in block.nodes if n.id == "ingresos_personales")
        assert hub.level == 1
        assert hub.kind == "hub"

    def test_level_2_has_three_allocation_nodes_no_gasto_personal(self):
        """Personal view has meta_ahorro_personal / gastos_fijos_personal /
        disponible_personal at level 2 — no gasto_personal node."""
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("0"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("700"),
            top_risk_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "gasto_personal" not in node_ids
        assert "meta_ahorro_personal" in node_ids
        assert "gastos_fijos_personal" in node_ids
        assert "disponible_personal" in node_ids
        # Allocation nodes should be level=2, kind=allocation
        for nid in ["meta_ahorro_personal", "gastos_fijos_personal", "disponible_personal"]:
            n = next(node for node in block.nodes if node.id == nid)
            assert n.level == 2
            assert n.kind == "allocation"

    def test_flow_conservation(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("50"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("650"),
            top_risk_totals=[("Supermercado", Decimal("250"))],
            other_spent=Decimal("100"),
            income_category_order=["Sueldo"],
        )
        inflows: dict[str, Decimal] = {}
        outflows: dict[str, Decimal] = {}
        for link in block.links:
            outflows[link.source] = outflows.get(link.source, Decimal("0")) + link.value
            inflows[link.target] = inflows.get(link.target, Decimal("0")) + link.value

        # ingresos_personales hub: in == out == its value
        hub_inflow = inflows.get("ingresos_personales", Decimal("0"))
        hub_outflow = outflows.get("ingresos_personales", Decimal("0"))
        hub_value = next(n.value for n in block.nodes if n.id == "ingresos_personales")
        assert hub_inflow == hub_value == hub_outflow

        # disponible_personal is intermediate, inflow == outflow
        assert inflows.get("disponible_personal", Decimal("0")) == outflows.get(
            "disponible_personal", Decimal("0")
        )
