"""Luka Connect webhook auth posture (INCIDENT 2026-07-12 hardening).

- present-but-wrong token → 401 always
- missing token → 401 when the grace switch is off
- missing token → accepted (grace path) when the switch is on
- unknown/stale job → 200 ACK (no retry storm)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core.config import settings
from modules.bank_connect.service import callback_token


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    # callback_token returns "" (skip) when the key is empty — force a real key
    # so token verification is actually exercised.
    monkeypatch.setattr(settings, "luka_connect_api_key", "test-secret")


@pytest.fixture
def wired(app, db):
    """Override get_db with the savepoint-scoped session so these rapid
    webhook posts don't churn raw DB connections (flaky under load)."""
    from core.database import get_db

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    yield app
    app.dependency_overrides.clear()


async def _post(app, job_id, token=None):
    body = {"jobId": job_id, "status": "completed", "movements": []}
    url = "/bank-connect/webhooks/luka-connect"
    if token is not None:
        url += f"?token={token}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return await c.post(url, json=body)


async def test_wrong_token_always_401(wired):
    res = await _post(wired, str(uuid.uuid4()), token="deadbeef")
    assert res.status_code == 401


async def test_missing_token_rejected_when_strict(wired, monkeypatch):
    monkeypatch.setattr(settings, "luka_connect_allow_untokenized_callbacks", False)
    res = await _post(wired, str(uuid.uuid4()), token=None)
    assert res.status_code == 401


async def test_missing_token_reaches_job_lookup_when_grace_on(wired, monkeypatch):
    monkeypatch.setattr(settings, "luka_connect_allow_untokenized_callbacks", True)
    # Unknown job → 200 ACK (grace path passed auth, then stale-job handling).
    res = await _post(wired, str(uuid.uuid4()), token=None)
    assert res.status_code == 200


async def test_valid_token_unknown_job_is_acked(wired):
    job = str(uuid.uuid4())
    res = await _post(wired, job, token=callback_token(job))
    assert res.status_code == 200


async def test_malformed_job_id_400(wired, monkeypatch):
    monkeypatch.setattr(settings, "luka_connect_allow_untokenized_callbacks", True)
    res = await _post(wired, "not-a-uuid", token=None)
    assert res.status_code == 400
