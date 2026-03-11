import pytest
import base64
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_gmail_webhook_rejects_bad_token(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/gmail", json={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_gmail_webhook_accepts_valid_oidc_and_enqueues(app):
    payload = {"message": {"data": base64.b64encode(b"{}").decode(), "messageId": "msg-123"}}
    with (
        patch("modules.email.router.verify_google_oidc_token", return_value=True),
        patch("modules.email.router.enqueue_job", new_callable=AsyncMock) as mock_enqueue,
        patch("modules.email.router.AsyncSessionLocal") as mock_session_cls,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = mock_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            response = await c.post(
                "/webhooks/gmail",
                json=payload,
                headers={"Authorization": "Bearer valid-oidc-token"},
            )
    assert response.status_code == 200
    mock_enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_outlook_webhook_validation_handshake(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/outlook?validationToken=abc123XYZ")
    assert response.status_code == 200
    assert response.text == "abc123XYZ"


@pytest.mark.asyncio
async def test_outlook_webhook_rejects_bad_client_state(app):
    body = {"value": [{"clientState": "wrong-secret", "resourceData": {"id": "msg-1"}}]}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/webhooks/outlook", json=body)
    assert response.status_code == 403
