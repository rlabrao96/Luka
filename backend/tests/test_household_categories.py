"""Real-DB tests for household partner-categories surface.

Mirrors the live-Supabase pattern used elsewhere in the suite (e.g.
test_household_privacy, test_budgets_api): tests are skip-marked because
they require a configured DATABASE_URL and a real Postgres. The conftest
`db` fixture wraps each test in a SAVEPOINT and rolls back, so writes
never persist. NEVER mocks the DB.
"""

import uuid
import pytest

from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.settings.models import UserCategoryPreference
from modules.settings.service import (
    adopt_household_category,
    get_household_partner_categories,
)


# pytestmark removed — DB available


async def _mk_user(db, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        full_name=email.split("@")[0],
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(u)
    await db.flush()
    return u


async def _mk_household(db, *members: User) -> Household:
    h = Household(name="Casa Test", type="couple")
    db.add(h)
    await db.flush()
    for i, m in enumerate(members):
        db.add(
            HouseholdMember(
                household_id=h.id,
                user_id=m.id,
                role="owner" if i == 0 else "member",
            )
        )
    await db.flush()
    return h


async def _mk_pref(db, user_id, category, ctype, sort_order=0, is_custom=True):
    p = UserCategoryPreference(
        user_id=user_id,
        category=category,
        category_type=ctype,
        sort_order=sort_order,
        is_custom=is_custom,
    )
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_lists_partner_prefs_not_in_caller(db):
    me = await _mk_user(db, "me@test.cl")
    partner = await _mk_user(db, "p@test.cl")
    await _mk_household(db, me, partner)

    await _mk_pref(db, me.id, "Alimentación", "expense")
    await _mk_pref(db, partner.id, "Alimentación", "expense")  # mine, excluded
    await _mk_pref(db, partner.id, "Mascotas", "expense")  # surfaced

    out = await get_household_partner_categories(db, me.id)
    cats = {(r["category"], r["category_type"]) for r in out}
    assert ("Mascotas", "expense") in cats
    assert ("Alimentación", "expense") not in cats


@pytest.mark.asyncio
async def test_excludes_callers_own_prefs(db):
    me = await _mk_user(db, "me@test.cl")
    partner = await _mk_user(db, "p@test.cl")
    await _mk_household(db, me, partner)

    await _mk_pref(db, me.id, "Deporte", "expense")
    await _mk_pref(db, partner.id, "Deporte", "expense")

    out = await get_household_partner_categories(db, me.id)
    assert all(r["category"] != "Deporte" for r in out)


@pytest.mark.asyncio
async def test_aggregates_from_multiple_partners(db):
    me = await _mk_user(db, "me@test.cl")
    p1 = await _mk_user(db, "p1@test.cl")
    p2 = await _mk_user(db, "p2@test.cl")
    await _mk_household(db, me, p1, p2)

    await _mk_pref(db, p1.id, "Mascotas", "expense")
    await _mk_pref(db, p2.id, "Mascotas", "expense")

    out = await get_household_partner_categories(db, me.id)
    row = next(r for r in out if r["category"] == "Mascotas")
    assert row["count"] == 2
    assert set(row["member_ids"]) == {p1.id, p2.id}


@pytest.mark.asyncio
async def test_solo_household_returns_empty(db):
    me = await _mk_user(db, "me@test.cl")
    await _mk_household(db, me)
    await _mk_pref(db, me.id, "Alimentación", "expense")

    out = await get_household_partner_categories(db, me.id)
    assert out == []


@pytest.mark.asyncio
async def test_cross_household_isolation(db):
    me = await _mk_user(db, "me@test.cl")
    partner_a = await _mk_user(db, "pa@test.cl")
    stranger = await _mk_user(db, "stranger@test.cl")
    await _mk_household(db, me, partner_a)
    # Stranger lives in a totally different household.
    await _mk_household(db, stranger)

    await _mk_pref(db, partner_a.id, "Mascotas", "expense")
    await _mk_pref(db, stranger.id, "Yates", "expense")

    out = await get_household_partner_categories(db, me.id)
    cats = {r["category"] for r in out}
    assert "Mascotas" in cats
    assert "Yates" not in cats


@pytest.mark.asyncio
async def test_adopt_happy_path(db):
    me = await _mk_user(db, "me@test.cl")
    partner = await _mk_user(db, "p@test.cl")
    await _mk_household(db, me, partner)
    await _mk_pref(db, me.id, "Alimentación", "expense", sort_order=0)
    await _mk_pref(db, me.id, "Salud", "expense", sort_order=1)
    await _mk_pref(db, partner.id, "Mascotas", "expense")
    await db.commit()

    result = await adopt_household_category(db, me.id, "Mascotas", "expense")
    assert result["already_present"] is False
    assert result["category"] == "Mascotas"
    assert result["sort_order"] == 2  # max(0,1)+1


@pytest.mark.asyncio
async def test_adopt_idempotent(db):
    me = await _mk_user(db, "me@test.cl")
    partner = await _mk_user(db, "p@test.cl")
    await _mk_household(db, me, partner)
    await _mk_pref(db, partner.id, "Mascotas", "expense")
    await db.commit()

    first = await adopt_household_category(db, me.id, "Mascotas", "expense")
    assert first["already_present"] is False
    second = await adopt_household_category(db, me.id, "Mascotas", "expense")
    assert second["already_present"] is True

    from sqlalchemy import select, func

    count_result = await db.execute(
        select(func.count()).where(
            UserCategoryPreference.user_id == me.id,
            UserCategoryPreference.category == "Mascotas",
            UserCategoryPreference.category_type == "expense",
        )
    )
    assert count_result.scalar() == 1


@pytest.mark.asyncio
async def test_adopt_rejects_unknown_category(db):
    me = await _mk_user(db, "me@test.cl")
    partner = await _mk_user(db, "p@test.cl")
    await _mk_household(db, me, partner)
    await _mk_pref(db, partner.id, "Mascotas", "expense")
    await db.commit()

    with pytest.raises(ValueError):
        await adopt_household_category(db, me.id, "Yates", "expense")
