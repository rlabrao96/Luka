"""Unit tests for the v1 heuristic forecast engine.

These tests lock in the math for `forecast.py` helpers used by
`modules.budgets.v2_service` to build the risk-category, runway, and
spendable-ceiling blocks. Tests use `Decimal` everywhere to match the
service-layer contract and to avoid float drift on monetary amounts.
"""

from decimal import Decimal

import pytest

from modules.budgets.forecast import (
    category_stats,
    overshoot_probability,
    pace_forecast,
    runway_days,
    select_risk_categories,
    spendable_ceiling,
)


# ---------------------------------------------------------------- category_stats


def test_category_stats_three_value_series():
    mean, std, n = category_stats([Decimal("100"), Decimal("200"), Decimal("300")])
    assert mean == Decimal("200")
    # population stdev of (100, 200, 300) ~ 81.649658
    assert abs(std - Decimal("81.65")) < Decimal("0.5")
    assert n == 3


def test_category_stats_single_value():
    mean, std, n = category_stats([Decimal("500")])
    assert mean == Decimal("500")
    assert std == Decimal("0")
    assert n == 1


def test_category_stats_empty():
    mean, std, n = category_stats([])
    assert mean == Decimal("0")
    assert std == Decimal("0")
    assert n == 0


# ------------------------------------------------------- select_risk_categories


def test_select_risk_categories_ranks_by_share_times_cv():
    # Restaurants: mean 200, std 100 -> CV=0.5; Groceries: mean 400, std 40 -> CV=0.1
    # share (of total mean): rest = 200/(200+400) = 1/3, gro = 2/3
    # rest score = (1/3)*0.5 = 0.166...; gro score = (2/3)*0.1 = 0.066...
    # rest should rank first.
    stats = {
        "Restaurantes": (Decimal("200"), Decimal("100"), 3),
        "Supermercado": (Decimal("400"), Decimal("40"), 3),
    }
    ranked = select_risk_categories(stats, top_n=5)
    assert len(ranked) == 2
    assert ranked[0][0] == "Restaurantes"
    assert ranked[1][0] == "Supermercado"


def test_select_risk_categories_top_n_limits_output():
    stats = {f"cat{i}": (Decimal(str(100 + i)), Decimal("50"), 3) for i in range(10)}
    ranked = select_risk_categories(stats, top_n=3)
    assert len(ranked) == 3


def test_select_risk_categories_skips_zero_mean():
    stats = {
        "zero": (Decimal("0"), Decimal("0"), 0),
        "real": (Decimal("100"), Decimal("50"), 3),
    }
    ranked = select_risk_categories(stats, top_n=5)
    assert [c for c, _ in ranked] == ["real"]


# -------------------------------------------------------------- pace_forecast


def test_pace_forecast_day_three_guard():
    """Day 1 should be treated as day 3 so a single-day total doesn't explode."""
    projected, std = pace_forecast(
        spent_so_far=Decimal("100"),
        current_day=1,
        days_in_month=30,
        historical_std=Decimal("50"),
    )
    # day-3 guard: effective_day=3, so 100 * 30 / 3 = 1000
    assert projected == Decimal("1000")
    # std scales proportionally
    assert std > Decimal("0")


def test_pace_forecast_midmonth_no_guard():
    projected, _ = pace_forecast(
        spent_so_far=Decimal("150000"),
        current_day=15,
        days_in_month=30,
        historical_std=Decimal("20000"),
    )
    # 150k * 30/15 = 300k
    assert projected == Decimal("300000")


def test_pace_forecast_end_of_month():
    projected, _ = pace_forecast(
        spent_so_far=Decimal("500000"),
        current_day=30,
        days_in_month=30,
        historical_std=Decimal("10000"),
    )
    assert projected == Decimal("500000")


# ----------------------------------------------------- overshoot_probability


def test_overshoot_probability_high():
    # projected way above cap → p near 1
    p = overshoot_probability(
        projected=Decimal("200000"), cap=Decimal("100000"), std=Decimal("20000")
    )
    assert p > Decimal("0.99")


def test_overshoot_probability_low():
    # projected way below cap → p near 0
    p = overshoot_probability(
        projected=Decimal("50000"), cap=Decimal("200000"), std=Decimal("20000")
    )
    assert p < Decimal("0.01")


def test_overshoot_probability_at_cap():
    # projected == cap → p ≈ 0.5
    p = overshoot_probability(
        projected=Decimal("100000"), cap=Decimal("100000"), std=Decimal("20000")
    )
    assert abs(p - Decimal("0.5")) < Decimal("0.01")


def test_overshoot_probability_zero_std_hard_threshold():
    # std==0 → step function
    assert overshoot_probability(
        projected=Decimal("110000"), cap=Decimal("100000"), std=Decimal("0")
    ) == Decimal("1")
    assert overshoot_probability(
        projected=Decimal("90000"), cap=Decimal("100000"), std=Decimal("0")
    ) == Decimal("0")


# ------------------------------------------------------------------ runway_days


def test_runway_days_basic():
    assert runway_days(Decimal("400000"), Decimal("50000")) == 8


def test_runway_days_zero_burn():
    # with zero burn, runway is effectively infinite — clamp to a large int
    assert runway_days(Decimal("100000"), Decimal("0")) >= 365


def test_runway_days_zero_remaining():
    assert runway_days(Decimal("0"), Decimal("50000")) == 0


# ------------------------------------------------------------ spendable_ceiling


def test_spendable_ceiling_basic():
    assert spendable_ceiling(
        income=Decimal("2000000"),
        known_bills=Decimal("500000"),
        cuotas_this_month=Decimal("100000"),
        savings_target=Decimal("300000"),
    ) == Decimal("1100000")


def test_spendable_ceiling_clamped_to_zero():
    # If commitments exceed income, ceiling should clamp to 0 (never negative).
    ceiling = spendable_ceiling(
        income=Decimal("1000000"),
        known_bills=Decimal("1500000"),
        cuotas_this_month=Decimal("100000"),
        savings_target=Decimal("0"),
    )
    assert ceiling == Decimal("0")


def test_spendable_ceiling_decimal_precision():
    ceiling = spendable_ceiling(
        income=Decimal("1234567.89"),
        known_bills=Decimal("100000.00"),
        cuotas_this_month=Decimal("50000.00"),
        savings_target=Decimal("200000.00"),
    )
    assert ceiling == Decimal("884567.89")


class TestSpendableCeilingPersonalAllocation:
    def test_personal_allocation_subtracts_from_spendable(self):
        result = spendable_ceiling(
            income=Decimal("1000"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
            personal_allocation=Decimal("150"),
        )
        # 1000 - 200 - 100 - 100 - 150 = 450
        assert result == Decimal("450")

    def test_personal_allocation_default_is_zero(self):
        """Omitting the kwarg preserves back-compat with v2 callers."""
        result = spendable_ceiling(
            income=Decimal("1000"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
        )
        # 1000 - 200 - 100 - 100 - 0 = 600 (same as v2)
        assert result == Decimal("600")

    def test_personal_allocation_overspent_clamps_to_zero(self):
        result = spendable_ceiling(
            income=Decimal("500"),
            known_bills=Decimal("200"),
            cuotas_this_month=Decimal("100"),
            savings_target=Decimal("100"),
            personal_allocation=Decimal("200"),
        )
        # 500 - 200 - 100 - 100 - 200 = -100 -> clamped to 0
        assert result == Decimal("0")


# make pytest happy if file is executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
