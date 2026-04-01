import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_get_review_cards_requires_auth(http_client):
    resp = await http_client.get("/merchant-review/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_review_status(http_client, override_auth, override_db):
    fake_job = {
        "job_id": "uuid-1",
        "status": "processing",
        "total_merchants": None,
        "reviewed_count": 0,
    }
    with patch(
        "modules.merchant_review.service.get_review_status",
        new_callable=AsyncMock,
        return_value=fake_job,
    ):
        resp = await http_client.get("/merchant-review/00000000-0000-0000-0000-000000000001/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_skip_review(http_client, override_auth, override_db):
    with patch(
        "modules.merchant_review.service.skip_review",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resp = await http_client.post("/merchant-review/00000000-0000-0000-0000-000000000001/skip")
        assert resp.status_code == 200
