---
source_file: "backend/modules/whatsapp/handler.py"
type: "code"
community: "Merchants & WhatsApp"
location: "L139"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# parse_manual_expense()

## Connections
- [[Parse natural-language expense messages into (amount_int, merchant).      Accept]] - `rationale_for` [EXTRACTED]
- [[_detect_currency()]] - `calls` [EXTRACTED]
- [[_handle_manual_expense_trigger()]] - `calls` [EXTRACTED]
- [[_parse_amount()_1]] - `calls` [EXTRACTED]
- [[handler.py]] - `contains` [EXTRACTED]
- [[test_parse_manual_expense_chile_keyword_override()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_comma_thousands()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_dot_thousands()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_multi_word()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_override_from_usd()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_with_gasto()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_clp_without_keyword()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_dolares_keyword_override()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_empty_returns_none()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_expense_of_in()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_gaste_en()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_gasto_de_en()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_no_amount_returns_none()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_no_merchant_returns_none()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_pesos_keyword_override()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_spent_at()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_usd_decimal()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_usd_fractional()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_usd_override_from_clp()]] - `calls` [INFERRED]
- [[test_parse_manual_expense_usd_whole()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Merchants_&_WhatsApp