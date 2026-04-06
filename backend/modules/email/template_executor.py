"""Execute declarative JSON extraction templates — no dynamic code, only fixed transforms."""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup

from modules.email.base import ParsedEmail

logger = logging.getLogger(__name__)


# --- Fixed transform functions ---


def _transform_strip(value: str) -> str:
    return value.strip()


def _transform_clp_integer(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def _transform_cop_integer(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def _transform_usd_cents(value: str) -> int:
    cleaned = value.replace(",", "")
    return int(round(float(cleaned) * 100))


def _transform_mxn_cents(value: str) -> int:
    return _transform_usd_cents(value)


def _transform_brl_centavos(value: str) -> int:
    cleaned = value.replace(".", "").replace(",", ".")
    return int(round(float(cleaned) * 100))


def _transform_pen_centimos(value: str) -> int:
    return _transform_usd_cents(value)


def _transform_parse_date_ddmmyyyy_hhmm(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y %H:%M")


def _transform_parse_date_ddmmyyyy(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%d/%m/%Y")


def _transform_parse_date_mmddyy(value: str) -> datetime:
    return datetime.strptime(value.strip(), "%m/%d/%y")


def _transform_parse_date_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.strip())


def _transform_now(_: str) -> datetime:
    return datetime.utcnow()


TRANSFORMS: dict[str, callable] = {
    "strip": _transform_strip,
    "clp_integer": _transform_clp_integer,
    "cop_integer": _transform_cop_integer,
    "usd_cents": _transform_usd_cents,
    "mxn_cents": _transform_mxn_cents,
    "brl_centavos": _transform_brl_centavos,
    "pen_centimos": _transform_pen_centimos,
    "parse_date_ddmmyyyy_hhmm": _transform_parse_date_ddmmyyyy_hhmm,
    "parse_date_ddmmyyyy": _transform_parse_date_ddmmyyyy,
    "parse_date_mmddyy": _transform_parse_date_mmddyy,
    "parse_date_iso": _transform_parse_date_iso,
    "now": _transform_now,
}


def _extract_field(html_soup: BeautifulSoup, full_text: str, selector_cfg: dict) -> str | None:
    raw = None
    css = selector_cfg.get("css")
    if css:
        el = html_soup.select_one(css)
        if el:
            raw = el.get_text(strip=True)

    if raw is None and selector_cfg.get("regex"):
        match = re.search(selector_cfg["regex"], full_text)
        if match:
            raw = match.group(1) if match.groups() else match.group(0)

    if raw and selector_cfg.get("regex") and css:
        match = re.search(selector_cfg["regex"], raw)
        if match:
            raw = match.group(1) if match.groups() else match.group(0)

    return raw


def _detect_transaction_type(full_text: str, type_cfg: dict) -> str:
    text_lower = full_text.lower()
    for kw in type_cfg.get("keywords_transfer", []):
        if kw in text_lower:
            return "transfer"
    for kw in type_cfg.get("keywords_income", []):
        if kw in text_lower:
            return "income"
    for kw in type_cfg.get("keywords_expense", []):
        if kw in text_lower:
            return "expense"
    return "expense"


def execute_template(html: str, template: dict, *, full_text: str = "") -> ParsedEmail | None:
    try:
        selectors = template.get("selectors")
        if not selectors:
            return None

        soup = BeautifulSoup(html, "html.parser")
        if not full_text:
            full_text = soup.get_text()

        # Amount
        amount_cfg = selectors.get("amount", {})
        amount_raw = _extract_field(soup, full_text, amount_cfg)
        if not amount_raw:
            return None
        transform_name = amount_cfg.get("transform", "strip")
        if transform_name not in TRANSFORMS:
            return None
        amount = TRANSFORMS[transform_name](amount_raw)

        # Merchant
        merchant_cfg = selectors.get("merchant", {})
        merchant_raw = _extract_field(soup, full_text, merchant_cfg)
        merchant = (
            TRANSFORMS.get(merchant_cfg.get("transform", "strip"), _transform_strip)(merchant_raw)
            if merchant_raw
            else None
        )

        # Date
        date_cfg = selectors.get("date", {})
        date_raw = _extract_field(soup, full_text, date_cfg)
        date_transform = date_cfg.get("transform", "now")
        if date_raw and date_transform in TRANSFORMS:
            tx_date = TRANSFORMS[date_transform](date_raw)
        else:
            tx_date = datetime.utcnow()

        # Transaction type
        type_cfg = selectors.get("transaction_type", {})
        tx_type = _detect_transaction_type(full_text, type_cfg)

        return ParsedEmail(
            amount=int(amount),
            raw_merchant=merchant or "Unknown",
            transaction_date=tx_date,
            bank_name="",
            transaction_type=tx_type,
            currency=template.get("currency", "CLP"),
        )

    except Exception as e:
        logger.warning("Template execution failed: %s", e)
        return None
