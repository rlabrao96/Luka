import pytest
import uuid
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
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


@pytest.fixture
async def http_client(app):
    """AsyncClient wired to the FastAPI app with ASGI transport."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def mock_current_user(mock_user):
    """Returns the mock_user. Used to override get_current_user dependency."""
    return mock_user


@pytest.fixture
def override_auth(app, mock_current_user):
    """Override get_current_user so routes think a user is authenticated."""
    from core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session():
    """Async mock of an SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def override_db(app, mock_db_session):
    """Override get_db so routes use the mock session."""
    from core.database import get_db

    async def _mock_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _mock_db
    yield mock_db_session
    app.dependency_overrides.clear()
