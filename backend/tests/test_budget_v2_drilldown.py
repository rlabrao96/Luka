"""Sankey node drilldown coverage (M30) — the money-facing dispatch that had
no tests. Uses the seeded budget fixtures (scripts/seed_budget_test_fixtures)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.budgets.v2_schemas import DrilldownBlock
from modules.budgets.v2_service import get_node_drilldown
from modules.households.models import Household


async def _seeded(db):
    user = (await db.execute(select(User).where(User.email == "rafa-solo@luka.test"))).scalar_one()
    household = (
        await db.execute(select(Household).where(Household.name == "HOGAR SOLO"))
    ).scalar_one()
    return user, household


def _month() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


async def test_drilldown_category_node_returns_items(db):
    user, household = await _seeded(db)
    block = await get_node_drilldown(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_month(),
        currency="CLP",
        view="personal",
        node_id="spent_supermercado",
    )
    assert isinstance(block, DrilldownBlock)
    assert block.items, "seeded Supermercado txns should surface"
    for item in block.items:
        assert item.amount > 0


async def test_drilldown_spent_other_is_valid(db):
    user, household = await _seeded(db)
    block = await get_node_drilldown(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_month(),
        currency="CLP",
        view="personal",
        node_id="spent_other",
    )
    assert isinstance(block, DrilldownBlock)
    # Seed has exactly 7 categories → up to 2 fall outside the top-5.
    for item in block.items:
        assert item.amount > 0


async def test_drilldown_hub_nodes_return_empty(db):
    user, household = await _seeded(db)
    block = await get_node_drilldown(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_month(),
        currency="CLP",
        view="personal",
        node_id="ingresos_personales",
    )
    assert block.items == []


async def test_drilldown_unknown_node_returns_empty(db):
    user, household = await _seeded(db)
    block = await get_node_drilldown(
        db,
        household_id=household.id,
        user_id=user.id,
        month=_month(),
        currency="CLP",
        view="personal",
        node_id="totally_bogus_node",
    )
    assert block.items == []


async def test_drilldown_invalid_view_raises(db):
    user, household = await _seeded(db)
    with pytest.raises(ValueError):
        await get_node_drilldown(
            db,
            household_id=household.id,
            user_id=user.id,
            month=_month(),
            currency="CLP",
            view="nonsense",
            node_id="spent_other",
        )
