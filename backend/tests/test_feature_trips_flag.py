import uuid

import pytest
from sqlalchemy import select

from modules.auth.models import User


@pytest.mark.asyncio
async def test_feature_trips_enabled_defaults_false(db):
    """New users must have feature_trips_enabled = False by default.

    Inserts a minimal user without setting the flag, flushes so the server
    default is applied, then re-queries with expire_on_commit semantics to
    confirm the persisted value.
    """
    user = User(
        id=uuid.uuid4(),
        email=f"trips-flag-{uuid.uuid4()}@test.cl",
        full_name="Trips Flag Test",
        email_provider="gmail",
    )
    db.add(user)
    await db.flush()

    fetched = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
    assert fetched.feature_trips_enabled is False
