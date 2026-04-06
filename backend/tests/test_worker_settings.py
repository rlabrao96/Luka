"""Test that worker settings assign jobs and crons to the correct worker."""

from worker import FastWorkerSettings, SlowWorkerSettings


def _func_names(settings_cls):
    return {f.__name__ for f in settings_cls.functions}


def _cron_names(settings_cls):
    return {c.coroutine.__name__ for c in settings_cls.cron_jobs}


def test_fast_worker_functions():
    assert _func_names(FastWorkerSettings) == {
        "process_email",
        "send_invite_email",
    }


def test_slow_worker_functions():
    assert _func_names(SlowWorkerSettings) == {
        "run_connect_sync",
        "run_plaid_sync_job",
        "process_merchant_review",
        "run_template_agent",
    }


def test_fast_worker_cron_jobs():
    expected = {
        "renew_mail_watches",
        "purge_raw_emails",
        "purge_email_logs",
        "cleanup_processed_webhooks",
        "schedule_connect_syncs",
        "refresh_subscriptions_cache",
        "schedule_plaid_syncs",
    }
    assert _cron_names(FastWorkerSettings) == expected


def test_slow_worker_cron_jobs():
    assert _cron_names(SlowWorkerSettings) == {"run_reconciliation_job", "run_template_agent"}


def test_fast_worker_config():
    assert FastWorkerSettings.max_jobs == 20
    assert FastWorkerSettings.job_timeout == 60
    assert FastWorkerSettings.queue_name == "arq:queue"


def test_slow_worker_config():
    assert SlowWorkerSettings.max_jobs == 5
    assert SlowWorkerSettings.job_timeout == 600
    assert SlowWorkerSettings.queue_name == "arq:queue:slow"


def test_no_job_overlap():
    """No function should appear in both workers."""
    fast = _func_names(FastWorkerSettings)
    slow = _func_names(SlowWorkerSettings)
    assert fast & slow == set()


def test_no_cron_overlap():
    """No cron should appear in both workers."""
    fast = _cron_names(FastWorkerSettings)
    slow = _cron_names(SlowWorkerSettings)
    assert fast & slow == set()
