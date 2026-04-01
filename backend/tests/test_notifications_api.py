import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_notifications_requires_auth(http_client: AsyncClient):
    resp = await http_client.get("/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_notifications_returns_list(http_client: AsyncClient, override_auth, override_db):
    with patch(
        "modules.notifications.service.get_user_notifications",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await http_client.get("/notifications")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_patch_notification_mark_read(http_client: AsyncClient, override_auth, override_db):
    fake_notif = {
        "id": "00000000-0000-0000-0000-000000000001",
        "type": "merchant_review",
        "title": "47 merchants ready",
        "status": "read",
        "payload": {},
        "created_at": "2026-04-01T00:00:00Z",
        "read_at": "2026-04-01T00:01:00Z",
    }
    with patch(
        "modules.notifications.service.update_notification",
        new_callable=AsyncMock,
        return_value=fake_notif,
    ):
        resp = await http_client.patch(
            "/notifications/00000000-0000-0000-0000-000000000001",
            json={"status": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"


@pytest.mark.asyncio
async def test_get_unread_count(http_client: AsyncClient, override_auth, override_db):
    with patch(
        "modules.notifications.service.get_unread_count",
        new_callable=AsyncMock,
        return_value=3,
    ):
        resp = await http_client.get("/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 3}
