"""Registration tests for the reconciliation tick on the slow worker.

The every-15-minute cron was removed in favor of event-driven enqueues
from email ingest and Plaid sync completion. The daily 6am safety-net
cron (`run_reconciliation_job`) remains.
"""

from jobs.reconciliation_tick import run_reconciliation_tick_for_household
from worker import SlowWorkerSettings


def test_per_household_tick_function_registered_on_slow_worker():
    """The per-household tick must be registered as a callable function."""
    func_names = {f.__name__ for f in SlowWorkerSettings.functions}
    assert "run_reconciliation_tick_for_household" in func_names
    assert run_reconciliation_tick_for_household in SlowWorkerSettings.functions


def test_no_15min_reconciliation_cron_registered():
    """The every-15-minute cron must no longer be on the slow worker."""
    cron_funcs = {c.coroutine.__name__ for c in SlowWorkerSettings.cron_jobs}
    assert "run_reconciliation_tick" not in cron_funcs


def test_daily_reconciliation_cron_still_registered():
    """The daily 6am safety-net cron is preserved."""
    cron_funcs = {c.coroutine.__name__ for c in SlowWorkerSettings.cron_jobs}
    assert "run_reconciliation_job" in cron_funcs
