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
    # statement_cache_size=0 is required for Supabase PgBouncer (port 6543, transaction mode);
    # without it, repeated test runs collide on prepared statement names across pooled connections.
    engine = create_async_engine(
        settings.database_url,
        connect_args={"statement_cache_size": 0},
    )
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
        preferred_currency="CLP",
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
    app.dependency_overrides.pop(get_current_user, None)


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
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Trip factories
# ---------------------------------------------------------------------------
import uuid as _uuid  # noqa: E402
from datetime import date as _date  # noqa: E402


@pytest.fixture
def make_user(db):
    """Factory: persist a User with sensible defaults; override via kwargs."""

    async def _factory(**overrides):
        from modules.auth.models import User

        defaults = dict(
            id=_uuid.uuid4(),
            email=f"user_{_uuid.uuid4().hex[:8]}@test.cl",
            full_name="Test User",
            email_provider="gmail",
            whatsapp_verified=False,
            feature_trips_enabled=True,
        )
        defaults.update(overrides)
        user = User(**defaults)
        db.add(user)
        await db.flush()
        return user

    return _factory


@pytest.fixture
def make_trip(db, make_user):
    """Factory: persist a Trip with creator auto-added as Luka attendee.

    Returns the Trip instance with a `creator_attendee` attribute set
    on the returned object for convenience.
    """

    async def _factory(
        creator=None,
        name="Test Trip",
        base_currency="USD",
        start_date=None,
        end_date=None,
        **overrides,
    ):
        from modules.trips.models import Trip, TripAttendee

        if creator is None:
            creator = await make_user()
        if start_date is None:
            start_date = _date(2026, 5, 1)
        if end_date is None:
            end_date = _date(2026, 5, 7)
        trip = Trip(
            creator_user_id=creator.id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            base_currency=base_currency,
            **overrides,
        )
        db.add(trip)
        await db.flush()
        attendee = TripAttendee(
            trip_id=trip.id,
            user_id=creator.id,
            display_name=creator.full_name,
        )
        db.add(attendee)
        await db.flush()
        trip.creator_attendee = attendee  # convenience
        trip.creator_user = creator
        return trip

    return _factory


@pytest.fixture
def make_attendee(db):
    """Factory: add an attendee to a trip. Either Luka (user=) or external (display_name=)."""

    async def _factory(trip, user=None, display_name=None):
        from modules.trips.models import TripAttendee

        if user is None and display_name is None:
            raise ValueError("provide user or display_name")
        attendee = TripAttendee(
            trip_id=trip.id,
            user_id=user.id if user else None,
            display_name=display_name or user.full_name,
        )
        db.add(attendee)
        await db.flush()
        return attendee

    return _factory
