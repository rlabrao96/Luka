import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_get_me_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_user_when_authenticated(app, mock_user):
    from core.security import get_current_user

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["email"] == mock_user.email


@pytest.mark.asyncio
async def test_get_me_includes_contribution_fields_for_household_member(
    app, mock_user, mock_partner
):
    """Regression — /auth/me must expose contribution fields for the active membership.

    Previously the frontend ContributionSection defaulted to mode='full' on every mount
    because there was no way to read the current value. Adding the fields here closes
    that gap and lets the budget config modal hydrate the row correctly.
    """
    import uuid
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock
    from core.database import get_db
    from core.security import get_current_user

    hid = uuid.uuid4()

    async def override_get_current_user():
        return mock_user

    async def override_get_db():
        session = AsyncMock()
        result = MagicMock()
        result.first = MagicMock(return_value=(hid, "fixed", Decimal("800000"), "CLP"))
        session.execute = AsyncMock(return_value=result)
        yield session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["contribution_mode"] == "fixed"
    assert body["fixed_contribution_amount"] == "800000.00"
    assert body["fixed_contribution_currency"] == "CLP"
    assert body["household_id"] == str(hid)


@pytest.mark.asyncio
async def test_patch_me_preserves_contribution_fields(app, mock_user):
    """Regression — PATCH /auth/me must return the caller's contribution
    fields, not null-default them. Prevents the UI from silently overwriting
    a user's real contribution_mode on a simple profile edit."""
    import uuid
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock
    from core.database import get_db
    from core.security import get_current_user

    hid = uuid.uuid4()

    async def override_get_current_user():
        return mock_user

    async def override_get_db():
        session = AsyncMock()
        # First call: SELECT User for re-fetch
        user_result = MagicMock()
        user_result.scalar_one_or_none = MagicMock(return_value=mock_user)
        # Second call: SELECT HouseholdMember for contribution fields
        member_result = MagicMock()
        member_result.first = MagicMock(return_value=(hid, "fixed", Decimal("800000"), "CLP"))
        session.execute = AsyncMock(side_effect=[user_result, member_result])
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                "/auth/me",
                headers={"Authorization": "Bearer valid-token"},
                json={"full_name": "New Name"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["contribution_mode"] == "fixed"
    assert body["fixed_contribution_amount"] == "800000.00"
    assert body["fixed_contribution_currency"] == "CLP"
