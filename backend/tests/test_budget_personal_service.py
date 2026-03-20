# backend/tests/test_budget_personal_service.py
import pytest
from modules.budgets.personal_service import (
    compute_personal_ceiling,
    build_personal_block,
    compute_pace,
)


def test_compute_pace_under_budget():
    pace = compute_pace(
        spendable_budget=1_000_000,
        daily_cumulative={1: 0, 2: 10000, 3: 25000, 4: 25000, 5: 50000},
        today_day=5,
        days_in_month=30,
    )
    assert pace["today_day"] == 5
    assert pace["days_in_month"] == 30
    assert pace["pace_at_today"] == pytest.approx(1_000_000 * 5 / 30, rel=0.01)
    assert pace["actual_at_today"] == 50000
    assert pace["delta"] < 0  # under budget
    assert pace["on_track"] is True


def test_compute_pace_over_budget():
    pace = compute_pace(
        spendable_budget=500_000,
        daily_cumulative={1: 100000, 2: 200000, 3: 350000},
        today_day=3,
        days_in_month=30,
    )
    assert pace["on_track"] is False
    assert pace["delta"] > 0


def test_compute_pace_zero_spendable_budget():
    pace = compute_pace(
        spendable_budget=0,
        daily_cumulative={},
        today_day=5,
        days_in_month=30,
    )
    assert pace["pace_at_today"] == 0
    assert pace["on_track"] is True


def test_personal_ceiling_uses_allocation_when_set():
    """When allocation exists, ceiling = income * personal_pct / 100."""
    result = compute_personal_ceiling(
        income=2_000_000,
        user_deposited=400_000,
        personal_pct=30.0,
        allocation_exists=True,
        mode="waterfall",
    )
    assert result == pytest.approx(600_000)


def test_personal_ceiling_uses_waterfall_when_no_allocation():
    """When no allocation, ceiling = income - user_deposited."""
    result = compute_personal_ceiling(
        income=2_000_000,
        user_deposited=400_000,
        personal_pct=30.0,
        allocation_exists=False,
        mode="waterfall",
    )
    assert result == pytest.approx(1_600_000)


def test_personal_ceiling_single_mode_uses_income_when_no_allocation():
    """Single mode, no allocation: ceiling = income."""
    result = compute_personal_ceiling(
        income=2_000_000,
        user_deposited=0,
        personal_pct=30.0,
        allocation_exists=False,
        mode="single",
    )
    assert result == pytest.approx(2_000_000)


def test_personal_ceiling_clamped_when_negative():
    block = build_personal_block(
        ceiling=-100_000,
        spent=200_000,
        breakdown_household=100_000,
        breakdown_personal=100_000,
    )
    assert block["ceiling_clamped"] is True
    assert block["available"] == -200_000
    assert block["percent_used"] is None


def test_personal_ceiling_percent_used_null_when_zero():
    block = build_personal_block(
        ceiling=0,
        spent=0,
        breakdown_household=0,
        breakdown_personal=0,
    )
    assert block["percent_used"] is None
