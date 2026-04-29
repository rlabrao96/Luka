"""Tests for the post-Connect-sync reconciliation tick enqueue.

Mirrors the Plaid + email-ingest paths so LATAM users (Luka Connect) get
the same automatic per-household reconciliation US users now get. Tests
mock only the redis enqueue boundary — the goal is to assert that:

1. After a successful Connect callback, the helper is invoked once with
   the right household_id and the slow queue name.
2. If the redis enqueue itself fails, the sync still returns OK (failures
   here must NOT fail the sync — the 15-min cron is a safety net).
3. Hard-error callbacks (status="failed") do NOT enqueue.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.bank_connect import router as connect_router


@pytest.mark.asyncio
async def test_enqueue_reconciliation_tick_routes_to_slow_queue():
    """Helper must enqueue with _queue_name='arq:queue:slow'."""
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.aclose = AsyncMock()

    hh_id = uuid.uuid4()

    with patch("arq.create_pool", new=AsyncMock(return_value=mock_pool)):
        await connect_router._enqueue_reconciliation_tick(hh_id)

    mock_pool.enqueue_job.assert_awaited_once_with(
        "run_reconciliation_tick_for_household",
        str(hh_id),
        _queue_name="arq:queue:slow",
    )
    mock_pool.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_reconciliation_tick_swallows_redis_failure(caplog):
    """If redis is down, the helper must log and return — never raise."""
    hh_id = uuid.uuid4()

    with patch(
        "arq.create_pool",
        new=AsyncMock(side_effect=RuntimeError("redis exploded")),
    ):
        # Must not raise.
        await connect_router._enqueue_reconciliation_tick(hh_id)

    # And it should leave a warning behind so we can debug.
    warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        "run_reconciliation_tick_for_household" in m for m in warning_messages
    ), warning_messages


@pytest.mark.asyncio
async def test_enqueue_reconciliation_tick_swallows_enqueue_failure(caplog):
    """Failures inside enqueue_job() must also be swallowed."""
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock(side_effect=RuntimeError("queue full"))
    mock_pool.aclose = AsyncMock()

    hh_id = uuid.uuid4()

    with patch("arq.create_pool", new=AsyncMock(return_value=mock_pool)):
        await connect_router._enqueue_reconciliation_tick(hh_id)

    warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any(
        "run_reconciliation_tick_for_household" in m for m in warning_messages
    ), warning_messages


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_completed_callback_enqueues_reconciliation_tick(db, mock_user, mock_household):
    """End-to-end: a completed Connect callback enqueues the tick once with
    the credential owner's household_id."""
    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.router import handle_connect_callback, ConnectCallback

    job_id = uuid.uuid4()
    cred = BankCredential(
        user_id=mock_user.id,
        bank_code="bci",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
        current_job_id=job_id,
    )
    db.add(cred)
    await db.commit()

    body = ConnectCallback(
        jobId=str(job_id),
        status="completed",
        movements=[],
        allBalances=[],
        creditCards=[],
    )

    with (
        patch.object(
            connect_router, "_enqueue_reconciliation_tick", new=AsyncMock()
        ) as mock_enqueue,
        patch.object(connect_router, "ensure_accounts", new=AsyncMock(return_value={})),
        patch(
            "modules.subscriptions.service.invalidate_subscriptions_cache",
            new=AsyncMock(),
        ),
    ):
        result = await handle_connect_callback(body=body, db=db)

    assert result["status"] == "ok"
    mock_enqueue.assert_awaited_once_with(mock_household.id)


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_failed_callback_does_not_enqueue_reconciliation_tick(db, mock_user, mock_household):
    """Hard errors (status='failed') must NOT trigger reconciliation."""
    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.router import handle_connect_callback, ConnectCallback

    job_id = uuid.uuid4()
    cred = BankCredential(
        user_id=mock_user.id,
        bank_code="bci",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
        current_job_id=job_id,
    )
    db.add(cred)
    await db.commit()

    body = ConnectCallback(
        jobId=str(job_id),
        status="failed",
        error="login_failed",
    )

    with patch.object(
        connect_router, "_enqueue_reconciliation_tick", new=AsyncMock()
    ) as mock_enqueue:
        result = await handle_connect_callback(body=body, db=db)

    assert result["status"] == "ack"
    mock_enqueue.assert_not_awaited()
