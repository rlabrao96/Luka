"""Leave-household: sole owner auto-promotes the oldest remaining member."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.households.service import leave_household
from sqlalchemy import select


async def _user(db, name):
    u = User(
        id=uuid.uuid4(),
        email=f"{name}-{uuid.uuid4().hex[:6]}@luka.test",
        full_name=name,
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(u)
    await db.flush()
    return u


async def _group(db, owner, members):
    h = Household(id=uuid.uuid4(), name="Grp", type="group")
    db.add(h)
    await db.flush()
    now = datetime.now(timezone.utc)
    db.add(HouseholdMember(household_id=h.id, user_id=owner.id, role="owner", joined_at=now - timedelta(days=10)))
    for i, m in enumerate(members):
        db.add(HouseholdMember(household_id=h.id, user_id=m.id, role="member", joined_at=now - timedelta(days=5 - i)))
    await db.flush()
    return h


async def _active(db, hid, uid):
    return (
        await db.execute(
            select(HouseholdMember).where(
                HouseholdMember.household_id == hid,
                HouseholdMember.user_id == uid,
                HouseholdMember.left_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def test_sole_owner_leaves_and_promotes_oldest_member(db):
    owner = await _user(db, "Owner")
    b = await _user(db, "Beto")   # joined first among members
    c = await _user(db, "Cami")
    h = await _group(db, owner, [b, c])

    new_hid = await leave_household(db, h.id, owner.id)

    # Owner is out and now in their own individual household.
    assert await _active(db, h.id, owner.id) is None
    new_h = (await db.execute(select(Household).where(Household.id == new_hid))).scalar_one()
    assert new_h.type == "individual"

    # Beto (oldest remaining) was promoted to owner; group still has an owner.
    beto = await _active(db, h.id, b.id)
    assert beto.role == "owner"
    cami = await _active(db, h.id, c.id)
    assert cami.role == "member"


async def test_non_sole_owner_leaves_without_promotion(db):
    owner = await _user(db, "Owner")
    co = await _user(db, "CoOwner")
    h = await _group(db, owner, [co])
    # Make co an owner too.
    m = await _active(db, h.id, co.id)
    m.role = "owner"
    await db.flush()

    await leave_household(db, h.id, owner.id)
    assert await _active(db, h.id, owner.id) is None
    # Co-owner unchanged, still owner.
    assert (await _active(db, h.id, co.id)).role == "owner"


async def test_only_member_cannot_leave(db):
    owner = await _user(db, "Solo")
    h = Household(id=uuid.uuid4(), name="G", type="group")
    db.add(h)
    await db.flush()
    db.add(HouseholdMember(household_id=h.id, user_id=owner.id, role="owner"))
    await db.flush()

    import pytest

    with pytest.raises(ValueError):
        await leave_household(db, h.id, owner.id)
