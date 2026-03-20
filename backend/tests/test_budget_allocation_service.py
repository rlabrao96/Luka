# backend/tests/test_budget_allocation_service.py
from modules.budgets.allocation_service import (
    compute_historical_suggestion,
    DEFAULT_ALLOCATION,
)


def test_default_allocation_sums_to_100():
    a = DEFAULT_ALLOCATION
    assert a["hogar_pct"] + a["ahorro_pct"] + a["personal_pct"] == 100


def test_historical_suggestion_rounds_to_nearest_5():
    # Simulate: over 3 months, 55% hogar, 35% personal, 10% ahorro
    suggestion = compute_historical_suggestion(
        monthly_data=[
            {"income": 1_000_000, "hogar_spent": 550_000, "personal_spent": 350_000},
            {"income": 1_200_000, "hogar_spent": 660_000, "personal_spent": 420_000},
            {"income": 900_000, "hogar_spent": 495_000, "personal_spent": 315_000},
        ]
    )
    assert suggestion is not None
    assert suggestion["hogar_pct"] + suggestion["ahorro_pct"] + suggestion["personal_pct"] == 100
    # All percentages are multiples of 5
    assert suggestion["hogar_pct"] % 5 == 0
    assert suggestion["ahorro_pct"] % 5 == 0
    assert suggestion["personal_pct"] % 5 == 0


def test_historical_suggestion_returns_none_when_no_income_data():
    suggestion = compute_historical_suggestion(monthly_data=[])
    assert suggestion is None


def test_historical_suggestion_excludes_zero_income_months():
    # 2 valid months + 1 with zero income
    suggestion = compute_historical_suggestion(
        monthly_data=[
            {"income": 1_000_000, "hogar_spent": 500_000, "personal_spent": 300_000},
            {"income": 0, "hogar_spent": 0, "personal_spent": 0},  # skip
            {"income": 800_000, "hogar_spent": 400_000, "personal_spent": 240_000},
        ]
    )
    assert suggestion is not None
