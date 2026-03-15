import pytest
import uuid
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from core.config import settings


@pytest.fixture
def app() -> FastAPI:
    from main import create_app

    return create_app()


@pytest.fixture
async def db():
    """
    Wraps each test in a SAVEPOINT and rolls back after.
    Tests never write permanent rows — suite is fully repeatable.
    Requires a real DATABASE_URL in .env — skip if not configured.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
    await engine.dispose()


@pytest.fixture
def mock_user():
    from modules.auth.models import User

    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=False,
    )


@pytest.fixture
def mock_partner():
    from modules.auth.models import User

    return User(
        id=uuid.uuid4(),
        email="cami@test.cl",
        full_name="Cami Test",
        email_provider="gmail",
        whatsapp_verified=False,
    )


@pytest.fixture
async def mock_household(db, mock_user, mock_partner):
    from modules.households.service import create_household
    from modules.households.models import Household, HouseholdMember  # noqa: F401

    h = await create_household(db, mock_user, "Test Hogar", "couple")
    db.add(HouseholdMember(household_id=h.id, user_id=mock_partner.id, role="member"))
    await db.commit()
    return h
