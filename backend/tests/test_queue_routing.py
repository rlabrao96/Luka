"""Test that enqueue_job routes jobs to the correct queue."""

import pytest
from unittest.mock import AsyncMock, patch

from jobs.queue import SLOW_JOBS, enqueue_job


def test_slow_jobs_set_contains_expected_jobs():
    """SLOW_JOBS should contain exactly the heavy jobs."""
    assert SLOW_JOBS == {
        "run_connect_sync",
        "run_plaid_sync_job",
        "process_merchant_review",
        "run_reconciliation_job",
    }


def test_slow_jobs_does_not_contain_schedulers():
    """Schedulers are lightweight cron jobs — they must NOT be in SLOW_JOBS."""
    assert "schedule_connect_syncs" not in SLOW_JOBS
    assert "schedule_plaid_syncs" not in SLOW_JOBS


@pytest.mark.asyncio
async def test_enqueue_slow_job_routes_to_slow_queue():
    """Slow jobs should be enqueued with _queue_name='arq:queue:slow'."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("run_connect_sync", "cred-123")

    mock_pool.enqueue_job.assert_called_once_with(
        "run_connect_sync", "cred-123", _queue_name="arq:queue:slow"
    )


@pytest.mark.asyncio
async def test_enqueue_fast_job_routes_to_default_queue():
    """Fast jobs should be enqueued with _queue_name='arq:queue'."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("process_email", "gmail", email_address="user@test.com")

    mock_pool.enqueue_job.assert_called_once_with(
        "process_email", "gmail", email_address="user@test.com", _queue_name="arq:queue"
    )


@pytest.mark.asyncio
async def test_enqueue_unknown_job_routes_to_fast_queue():
    """Unknown job names default to the fast queue."""
    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()

    with patch("jobs.queue.create_pool", return_value=mock_pool):
        await enqueue_job("some_future_job", "arg1")

    mock_pool.enqueue_job.assert_called_once_with(
        "some_future_job", "arg1", _queue_name="arq:queue"
    )
