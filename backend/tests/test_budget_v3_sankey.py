"""Budget v3 Sankey tests — multi-level structure, caller-relative privacy,
flow conservation, personal allocation wiring."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.budgets.v2_schemas import SankeyNode
from modules.budgets.v2_service import (
    _build_hogar_sankey,
    _build_personal_sankey,
    _pay_first_fit,
    get_budget_v2,
)
from modules.households.models import Household
from modules.transactions.models import Transaction
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
            top_spent_totals=[],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo", "Bonus"],
        )
        # Level-2 nodes: "bill" kind reserved for fixed committed outflows
        # (gastos_fijos), rest carry the generic "allocation" kind.
        expected_kind = {
            "meta_ahorro": "allocation",
            "gastos_fijos": "bill",
            "cuotas": "allocation",
            "gasto_personal": "allocation",
            "disponible_hogar": "allocation",
        }
        for node in block.nodes:
            if node.id in expected_kind:
                assert node.level == 2
                assert node.kind == expected_kind[node.id]

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
            top_spent_totals=[("Supermercado", Decimal("300"))],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
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
            top_spent_totals=[],
            other_spent=Decimal("0"),
            income_category_order=["Sueldo"],
        )
        node_ids = {n.id for n in block.nodes}
        assert "gasto_personal" not in node_ids
        assert "meta_ahorro_personal" in node_ids
        assert "gastos_fijos_personal" in node_ids
        assert "disponible_personal" in node_ids
        # Level-2: "bill" for fixed committed outflows, "allocation" for the rest.
        expected_kind = {
            "meta_ahorro_personal": "allocation",
            "gastos_fijos_personal": "bill",
            "disponible_personal": "allocation",
        }
        for nid, want in expected_kind.items():
            n = next(node for node in block.nodes if node.id == nid)
            assert n.level == 2
            assert n.kind == want

    def test_flow_conservation(self):
        block = _build_personal_sankey(
            caller_sources={"Sueldo": Decimal("1000")},
            caller_other_income=Decimal("0"),
            known_bills=Decimal("100"),
            cuotas_this_month=Decimal("50"),
            savings_target=Decimal("200"),
            spendable_amount=Decimal("650"),
            top_spent_totals=[("Supermercado", Decimal("250"))],
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


# ---------------------------------------------------------------------------
# Integration helpers — DB-backed tests (require live seeded database)
# ---------------------------------------------------------------------------


def _current_month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


async def _user_by_email(db, email: str) -> User:
    res = await db.execute(select(User).where(User.email == email))
    u = res.scalar_one_or_none()
    assert u is not None, f"seed missing: {email}"
    return u


async def _household_by_name(db, name: str) -> Household:
    res = await db.execute(select(Household).where(Household.name == name))
    h = res.scalar_one_or_none()
    assert h is not None, f"seed missing household: {name}"
    return h


def _flow_conservation_errors(sankey) -> list[str]:
    """Return node-level flow conservation violations (tolerance ±1 for rounding)."""
    d = sankey.model_dump(mode="json")
    errors: list[str] = []
    inflow: dict[str, Decimal] = {}
    outflow: dict[str, Decimal] = {}
    for link in d["links"]:
        src, tgt, val = link["source"], link["target"], Decimal(str(link["value"]))
        outflow[src] = outflow.get(src, Decimal("0")) + val
        inflow[tgt] = inflow.get(tgt, Decimal("0")) + val
    for node in d["nodes"]:
        nid, value = node["id"], Decimal(str(node["value"]))
        node_in = inflow.get(nid, Decimal("0"))
        node_out = outflow.get(nid, Decimal("0"))
        is_source = node_out > Decimal("0") and node_in == Decimal("0")
        is_sink = node_in > Decimal("0") and node_out == Decimal("0")
        is_intermediate = node_in > Decimal("0") and node_out > Decimal("0")
        if is_source:
            if abs(node_out - value) > Decimal("1"):
                errors.append(f"{nid}: source outflow {node_out} != value {value}")
        elif is_sink:
            if abs(node_in - value) > Decimal("1"):
                errors.append(f"{nid}: sink inflow {node_in} != value {value}")
        elif is_intermediate:
            if abs(node_in - value) > Decimal("1"):
                errors.append(f"{nid}: intermediate inflow {node_in} != value {value}")
            if abs(node_out - value) > Decimal("1"):
                errors.append(f"{nid}: intermediate outflow {node_out} != value {value}")
    return errors


def _walk_json_values(obj):
    """Yield every leaf value in a nested dict/list structure."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_json_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json_values(v)
    else:
        yield obj


def _value_present_in_json(obj, forbidden: Decimal) -> bool:
    """Return True if forbidden appears as a numeric leaf (float comparison)."""
    forbidden_f = float(forbidden)
    for leaf in _walk_json_values(obj):
        if isinstance(leaf, (int, float, Decimal)):
            if float(leaf) == forbidden_f:
                return True
    return False


# ---------------------------------------------------------------------------
# TestCallerRelativeEndToEnd
# ---------------------------------------------------------------------------


class TestCallerRelativeEndToEnd:
    """End-to-end caller-relative tests against the live seeded DB."""

    @pytest.mark.asyncio
    async def test_caller_sees_own_sources_and_partner_as_aggregate(self, db):
        """Full+full household with synthetic income: rafa-full's household
        view should have their partner (partner-full) appear as exactly one
        member_ node at level 0. We seed real income for both so neither has
        zero contribution (zero-contribution members are correctly suppressed
        by the builder, so we must give them something to emit)."""
        rafa = await _user_by_email(db, "rafa-full@luka.test")
        partner = await _user_by_email(db, "partner-full@luka.test")
        household = await _household_by_name(db, "HOGAR FULL")

        # Seed income for both members so neither is zero-suppressed.
        for user, label in [(rafa, "Rafa Income"), (partner, "Partner Income")]:
            db.add(
                Transaction(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    household_id=household.id,
                    raw_merchant_name=label,
                    amount=Decimal("1000000"),
                    currency="CLP",
                    transaction_date=datetime(
                        _current_month().year,
                        _current_month().month,
                        5,
                        tzinfo=timezone.utc,
                    ),
                    category="Sueldo",
                    source="manual",
                    status="settled",
                    transaction_type="income",
                )
            )
        await db.flush()

        resp = await get_budget_v2(
            db,
            household_id=household.id,
            user_id=rafa.id,
            month=_current_month(),
            currency="CLP",
            view="household",
        )

        nodes = resp.sankey.nodes
        member_nodes = [n for n in nodes if n.id.startswith("member_")]
        # HOGAR FULL has 2 members; rafa's own sources are src_* nodes.
        # partner-full must appear as exactly one member_ aggregate node.
        assert len(member_nodes) == 1, (
            f"Expected exactly 1 member_ node (partner aggregate), got {len(member_nodes)}: "
            f"{[n.id for n in member_nodes]}"
        )
        partner_node = member_nodes[0]
        assert partner_node.level == 0
        assert partner_node.kind == "source"
        assert partner_node.member_id is not None
        assert partner_node.member_id == str(partner.id)

        # Caller's own income sources should be src_* nodes at level 0.
        src_nodes = [n for n in nodes if n.id.startswith("src_")]
        assert len(src_nodes) >= 1, "Caller should have at least one src_ node after income seeded"
        for sn in src_nodes:
            assert sn.level == 0
            assert sn.kind == "source"
            assert sn.member_id is None  # caller's own sources have no member_id

    @pytest.mark.asyncio
    async def test_fixed_member_node_value_equals_contribution_amount(self, db):
        """Mixed full+fixed household: in household view the fixed member
        (partner-fixed) must appear as one member_ node whose value equals
        their fixed_contribution_amount (800,000 CLP), not their real income."""
        rafa = await _user_by_email(db, "rafa-fixed@luka.test")
        household = await _household_by_name(db, "HOGAR FIXED")

        # Seed a synthetic real income for the fixed partner that is deliberately
        # different from their fixed_contribution_amount. The savepoint rolls it back.
        partner = await _user_by_email(db, "partner-fixed@luka.test")
        FORBIDDEN_REAL_INCOME = Decimal("3147913")
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=partner.id,
                household_id=household.id,
                raw_merchant_name="SYNTHETIC-PAYROLL-FIXED-V3",
                amount=FORBIDDEN_REAL_INCOME,
                currency="CLP",
                transaction_date=datetime(
                    _current_month().year,
                    _current_month().month,
                    15,
                    tzinfo=timezone.utc,
                ),
                category="Sueldo",
                source="manual",
                status="settled",
                transaction_type="income",
            )
        )
        await db.flush()

        resp = await get_budget_v2(
            db,
            household_id=household.id,
            user_id=rafa.id,
            month=_current_month(),
            currency="CLP",
            view="household",
        )

        # Serialize and walk: the forbidden real income must NOT appear anywhere.
        payload = resp.model_dump(mode="json")
        assert not _value_present_in_json(
            payload, FORBIDDEN_REAL_INCOME
        ), f"Fixed member's real income {FORBIDDEN_REAL_INCOME} leaked into the response"

        # The fixed member's node must exist with value == 800,000.
        fixed_member_nodes = [
            n
            for n in resp.sankey.nodes
            if n.id.startswith("member_") and n.member_id == str(partner.id)
        ]
        assert len(fixed_member_nodes) == 1, "Expected exactly 1 member_ node for the fixed partner"
        fixed_node = fixed_member_nodes[0]
        assert fixed_node.value == Decimal(
            "800000"
        ), f"Fixed node value {fixed_node.value} != 800000 (fixed_contribution_amount)"
        assert (
            "Contribución fija" in fixed_node.label
        ), f"Fixed node label missing 'Contribución fija': {fixed_node.label!r}"

    @pytest.mark.asyncio
    async def test_personal_view_has_no_member_nodes(self, db):
        """Personal view must never emit member_ aggregate nodes — those are
        household-only constructs. Even in HOGAR FIXED, rafa-fixed's personal
        view should only have src_* source nodes."""
        rafa = await _user_by_email(db, "rafa-fixed@luka.test")
        household = await _household_by_name(db, "HOGAR FIXED")

        resp = await get_budget_v2(
            db,
            household_id=household.id,
            user_id=rafa.id,
            month=_current_month(),
            currency="CLP",
            view="personal",
        )

        member_nodes = [n for n in resp.sankey.nodes if n.id.startswith("member_")]
        assert (
            member_nodes == []
        ), f"Personal view emitted unexpected member_ nodes: {[n.id for n in member_nodes]}"


# ---------------------------------------------------------------------------
# TestFlowConservationAllSeeds
# ---------------------------------------------------------------------------


class TestFlowConservationAllSeeds:
    """Flow conservation across all seeded households + view combinations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "household_name,seed_email,currency,view",
        [
            ("HOGAR FULL", "rafa-full@luka.test", "CLP", "household"),
            ("HOGAR FULL", "rafa-full@luka.test", "CLP", "personal"),
            ("HOGAR FIXED", "rafa-fixed@luka.test", "CLP", "household"),
            ("HOGAR FIXED", "rafa-fixed@luka.test", "CLP", "personal"),
            ("HOGAR REIMB", "rafa-reimb@luka.test", "CLP", "household"),
            ("HOGAR SOLO", "rafa-solo@luka.test", "CLP", "household"),
        ],
    )
    async def test_flow_conservation(self, db, household_name, seed_email, currency, view):
        """Every seeded household + currency + view: Sankey flow must be
        conservative (inflow == outflow == value for every non-trivial node)."""
        user = await _user_by_email(db, seed_email)
        household = await _household_by_name(db, household_name)

        resp = await get_budget_v2(
            db,
            household_id=household.id,
            user_id=user.id,
            month=_current_month(),
            currency=currency,
            view=view,
        )

        errors = _flow_conservation_errors(resp.sankey)
        assert (
            errors == []
        ), f"Flow conservation violated for {household_name}/{view}/{currency}: {errors}"
