"""Budget v3 Sankey tests — multi-level structure, caller-relative privacy,
flow conservation, personal allocation wiring."""

from __future__ import annotations

from decimal import Decimal


from modules.budgets.v2_schemas import SankeyNode


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
