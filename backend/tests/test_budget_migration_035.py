import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_035_adds_expected_columns(db):
    result = await db.execute(
        text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'household_members'
          AND column_name IN ('contribution_mode', 'fixed_contribution_amount', 'fixed_contribution_currency')
    """)
    )
    cols = {row[0] for row in result}
    assert cols == {"contribution_mode", "fixed_contribution_amount", "fixed_contribution_currency"}


@pytest.mark.asyncio
async def test_035_creates_user_budget_settings(db):
    result = await db.execute(text("SELECT to_regclass('public.user_budget_settings')"))
    assert result.scalar() == "user_budget_settings"


@pytest.mark.asyncio
async def test_035_creates_cuota_purchases(db):
    result = await db.execute(text("SELECT to_regclass('public.cuota_purchases')"))
    assert result.scalar() == "cuota_purchases"


@pytest.mark.asyncio
async def test_035_contribution_mode_default_is_full(db):
    result = await db.execute(
        text("""
        SELECT column_default FROM information_schema.columns
        WHERE table_name = 'household_members' AND column_name = 'contribution_mode'
    """)
    )
    default = result.scalar() or ""
    assert "full" in default
