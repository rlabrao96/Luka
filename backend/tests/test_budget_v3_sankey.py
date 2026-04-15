"""Budget v3 Sankey tests — multi-level structure, caller-relative privacy,
flow conservation, personal allocation wiring."""

from __future__ import annotations

from decimal import Decimal


from modules.budgets.v2_schemas import SankeyNode
from modules.budgets.v2_service import _pay_first_fit


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
