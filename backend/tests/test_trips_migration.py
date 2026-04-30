"""Verify migration 046 creates all eight trip tables with key columns."""

import pytest
from sqlalchemy import text

TRIP_TABLES = [
    "trips",
    "trip_attendees",
    "trip_expenses",
    "trip_expense_splits",
    "trip_settlements",
    "trip_suggestion_dismissals",
    "trip_settlement_dismissals",
    "trip_base_currency_changes",
]


@pytest.mark.asyncio
async def test_all_trip_tables_exist(db):
    for t in TRIP_TABLES:
        result = await db.execute(text("SELECT to_regclass(:n)").bindparams(n=f"public.{t}"))
        assert result.scalar() is not None, f"{t} missing"


@pytest.mark.asyncio
async def test_trip_expenses_has_version_column(db):
    result = await db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='trip_expenses' AND column_name='version'"
        )
    )
    assert result.scalar() == "version"


@pytest.mark.asyncio
async def test_trip_settlements_has_write_off_column(db):
    result = await db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='trip_settlements' AND column_name='write_off'"
        )
    )
    assert result.scalar() == "write_off"


@pytest.mark.asyncio
async def test_rls_enabled_on_trip_tables(db):
    for t in TRIP_TABLES:
        result = await db.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = :n").bindparams(n=t)
        )
        assert result.scalar() is True, f"RLS not enabled on {t}"


@pytest.mark.asyncio
async def test_is_trip_member_function_exists(db):
    result = await db.execute(text("SELECT proname FROM pg_proc WHERE proname = 'is_trip_member'"))
    assert result.scalar() == "is_trip_member"


@pytest.mark.asyncio
async def test_is_active_trip_member_function_exists(db):
    result = await db.execute(
        text("SELECT proname FROM pg_proc WHERE proname = 'is_active_trip_member'")
    )
    assert result.scalar() == "is_active_trip_member"


@pytest.mark.asyncio
async def test_mutual_exclusivity_triggers_exist(db):
    rows = (
        await db.execute(
            text(
                "SELECT tgname FROM pg_trigger "
                "WHERE tgname IN ('trg_reject_split_if_trip_linked', "
                "'trg_reject_trip_link_if_split_exists')"
            )
        )
    ).all()
    assert len(rows) == 2
