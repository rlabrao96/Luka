"""Registration tests for the reconciliation_tick cron on the slow worker.

Verifies wiring only — the orchestrator's behavior is covered in
`test_reconciliation_tick.py`.
"""

from jobs.reconciliation_tick import reconciliation_tick_cron, run_reconciliation_tick
from worker import SlowWorkerSettings


def test_cron_registered_on_slow_worker_settings():
    """The reconciliation_tick cron must be registered on the slow worker."""
    cron_funcs = {c.coroutine.__name__ for c in SlowWorkerSettings.cron_jobs}
    assert "run_reconciliation_tick" in cron_funcs

    # And the exact cron object we export should be the one registered.
    assert reconciliation_tick_cron in SlowWorkerSettings.cron_jobs


def test_cron_schedule_every_15_minutes():
    """Cron must fire at minutes 0, 15, 30, 45."""
    assert reconciliation_tick_cron.minute == {0, 15, 30, 45}
    # Should not run eagerly on worker boot.
    assert reconciliation_tick_cron.run_at_startup is False
    # And the cron must wrap the wrapper task, not some other function.
    assert reconciliation_tick_cron.coroutine is run_reconciliation_tick
