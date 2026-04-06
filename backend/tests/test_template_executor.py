"""Tests for the declarative JSON template executor."""

from datetime import datetime


from modules.email.template_executor import (
    execute_template,
    _transform_clp_integer,
    _transform_usd_cents,
)

SAMPLE_HTML = """<html><body>
<table>
  <tr><td class="merchant">LIDER EXPRESS</td></tr>
  <tr><td class="amount">$15.990</td></tr>
  <tr><td class="date">05/04/2026 14:32</td></tr>
</table>
</body></html>"""


FULL_TEMPLATE = {
    "currency": "CLP",
    "selectors": {
        "amount": {
            "css": "td.amount",
            "regex": r"\$([\d.,]+)",
            "transform": "clp_integer",
        },
        "merchant": {
            "css": "td.merchant",
            "transform": "strip",
        },
        "date": {
            "css": "td.date",
            "transform": "parse_date_ddmmyyyy_hhmm",
        },
        "transaction_type": {
            "keywords_transfer": ["transferencia"],
            "keywords_income": ["abono"],
            "keywords_expense": ["compra"],
        },
    },
}


def test_full_extraction_from_html():
    """Full extraction: CSS selectors yield amount, merchant, date, and transaction type."""
    result = execute_template(SAMPLE_HTML, FULL_TEMPLATE)

    assert result is not None
    assert result.amount == 15990
    assert result.raw_merchant == "LIDER EXPRESS"
    assert result.transaction_date == datetime(2026, 4, 5, 14, 32)
    assert result.transaction_type == "expense"
    assert result.currency == "CLP"


def test_clp_integer_transform():
    """CLP integer transform: $1.250.000 → 1250000."""
    assert _transform_clp_integer("1.250.000") == 1250000
    assert _transform_clp_integer("$1.250.000".lstrip("$")) == 1250000
    assert _transform_clp_integer("15.990") == 15990


def test_usd_cents_transform():
    """USD cents transform: $17.08 → 1708."""
    assert _transform_usd_cents("17.08") == 1708
    assert _transform_usd_cents("1,234.56") == 123456
    assert _transform_usd_cents("0.99") == 99


def test_returns_none_when_amount_missing():
    """Returns None when amount selector finds nothing in the HTML."""
    html_no_amount = """<html><body>
    <table>
      <tr><td class="merchant">LIDER EXPRESS</td></tr>
      <tr><td class="date">05/04/2026 14:32</td></tr>
    </table>
    </body></html>"""

    result = execute_template(html_no_amount, FULL_TEMPLATE)
    assert result is None


def test_returns_none_for_empty_template():
    """Returns None when template has no selectors key."""
    result = execute_template(SAMPLE_HTML, {})
    assert result is None


def test_returns_none_for_invalid_template():
    """Returns None when template selectors key is None."""
    result = execute_template(SAMPLE_HTML, {"selectors": None})
    assert result is None


def test_transaction_type_transfer_keyword():
    """Detects transfer type via keywords_transfer."""
    html = """<html><body>
    <table>
      <tr><td class="merchant">BANCO CHILE</td></tr>
      <tr><td class="amount">$50.000</td></tr>
      <tr><td class="date">05/04/2026 10:00</td></tr>
    </table>
    <p>Transferencia realizada</p>
    </body></html>"""

    result = execute_template(html, FULL_TEMPLATE)
    assert result is not None
    assert result.transaction_type == "transfer"


def test_date_fallback_to_utcnow_when_no_date_selector():
    """Falls back to utcnow when no date CSS selector matches."""
    template_no_date = {
        "currency": "CLP",
        "selectors": {
            "amount": {
                "css": "td.amount",
                "regex": r"\$([\d.,]+)",
                "transform": "clp_integer",
            },
            "merchant": {
                "css": "td.merchant",
                "transform": "strip",
            },
        },
    }

    before = datetime.utcnow()
    result = execute_template(SAMPLE_HTML, template_no_date)
    after = datetime.utcnow()

    assert result is not None
    assert before <= result.transaction_date <= after
