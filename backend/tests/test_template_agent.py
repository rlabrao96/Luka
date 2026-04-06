"""Tests for pure functions in the autonomous template agent."""

from modules.email.template_agent import validate_template, should_retire_template


# ---------------------------------------------------------------------------
# validate_template
# ---------------------------------------------------------------------------


def test_validate_template_passes_with_perfect_accuracy():
    """100% amount + 100% merchant match → passes."""
    template = [
        {"amount": 15990, "merchant": "LIDER EXPRESS"},
        {"amount": 5000, "merchant": "UBER"},
        {"amount": 120000, "merchant": "FALABELLA"},
    ]
    llm = [
        {"amount": 15990, "merchant": "LIDER EXPRESS"},
        {"amount": 5000, "merchant": "UBER"},
        {"amount": 120000, "merchant": "FALABELLA"},
    ]
    passed, accuracy = validate_template(template, llm)
    assert passed is True
    assert accuracy == 1.0


def test_validate_template_fails_on_any_amount_mismatch():
    """A single amount mismatch causes validation to fail regardless of merchant accuracy."""
    template = [
        {"amount": 15990, "merchant": "LIDER EXPRESS"},
        {"amount": 9999, "merchant": "UBER"},  # wrong amount
        {"amount": 120000, "merchant": "FALABELLA"},
    ]
    llm = [
        {"amount": 15990, "merchant": "LIDER EXPRESS"},
        {"amount": 5000, "merchant": "UBER"},
        {"amount": 120000, "merchant": "FALABELLA"},
    ]
    passed, accuracy = validate_template(template, llm)
    assert passed is False


def test_validate_template_fails_on_low_merchant_accuracy():
    """Even with 100% amount match, <95% merchant accuracy causes failure."""
    # Build 20 samples: amounts all match, but only 15/20 merchants match (75%)
    template = [
        {"amount": i * 1000, "merchant": "CORRECT" if i < 15 else "WRONG"} for i in range(1, 21)
    ]
    llm = [{"amount": i * 1000, "merchant": "CORRECT"} for i in range(1, 21)]
    passed, accuracy = validate_template(template, llm)
    assert passed is False


def test_validate_template_passes_at_exactly_95_percent_merchant():
    """Exactly 95% merchant accuracy with 100% amounts should pass (19/20)."""
    # 20 samples: 19 merchant matches, 1 mismatch = 95%
    template = [
        {"amount": i * 1000, "merchant": "CORRECT" if i < 20 else "WRONG"} for i in range(1, 21)
    ]
    llm = [{"amount": i * 1000, "merchant": "CORRECT"} for i in range(1, 21)]
    passed, accuracy = validate_template(template, llm)
    assert passed is True


def test_validate_template_fails_on_empty_results():
    """Empty template_results list returns False."""
    passed, accuracy = validate_template([], [])
    assert passed is False
    assert accuracy == 0.0


def test_validate_template_fails_on_mismatched_list_lengths():
    """Unequal list lengths return False immediately."""
    template = [{"amount": 1000, "merchant": "A"}]
    llm = [{"amount": 1000, "merchant": "A"}, {"amount": 2000, "merchant": "B"}]
    passed, accuracy = validate_template(template, llm)
    assert passed is False
    assert accuracy == 0.0


def test_validate_template_merchant_substring_match_counts():
    """Template merchant that is a substring of LLM merchant is counted as a match."""
    template = [{"amount": 5000, "merchant": "UBER"}]
    llm = [{"amount": 5000, "merchant": "UBER EATS"}]
    passed, accuracy = validate_template(template, llm)
    assert passed is True


# ---------------------------------------------------------------------------
# should_retire_template
# ---------------------------------------------------------------------------


def test_should_retire_template_returns_true_on_any_amount_mismatch():
    """A single amount_match=False entry triggers retirement."""
    results = [
        {"shadow_match": True, "amount_match": True},
        {"shadow_match": True, "amount_match": False},  # drift
        {"shadow_match": True, "amount_match": True},
    ]
    assert should_retire_template(results) is True


def test_should_retire_template_returns_false_when_all_amounts_match():
    """No retirement when every shadow result has amount_match=True."""
    results = [
        {"shadow_match": True, "amount_match": True},
        {"shadow_match": True, "amount_match": True},
        {"shadow_match": True, "amount_match": True},
    ]
    assert should_retire_template(results) is False


def test_should_retire_template_returns_false_on_empty_results():
    """Empty shadow results → no retirement (nothing to compare)."""
    assert should_retire_template([]) is False


def test_should_retire_template_treats_missing_amount_match_key_as_ok():
    """Missing amount_match key defaults to True (no mismatch assumed)."""
    results = [{"shadow_match": True}]  # no amount_match key
    assert should_retire_template(results) is False
