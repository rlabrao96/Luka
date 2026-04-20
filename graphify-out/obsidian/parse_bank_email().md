---
source_file: "backend/modules/email/parser.py"
type: "code"
community: "Email Parser Pipeline"
location: "L288"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# parse_bank_email()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Three-layer parser template → LLM waterfall → regex fallback.      Returns (Par]] - `rationale_for` [EXTRACTED]
- [[_get_active_template()]] - `calls` [EXTRACTED]
- [[execute_template()]] - `calls` [INFERRED]
- [[main()]] - `calls` [INFERRED]
- [[main()_1]] - `calls` [INFERRED]
- [[main()_2]] - `calls` [INFERRED]
- [[main()_4]] - `calls` [INFERRED]
- [[main()_5]] - `calls` [INFERRED]
- [[main()_9]] - `calls` [INFERRED]
- [[parse_bank_email_regex()]] - `calls` [EXTRACTED]
- [[parse_with_llm()]] - `calls` [INFERRED]
- [[parser.py]] - `contains` [EXTRACTED]
- [[process_email()]] - `calls` [INFERRED]
- [[test_clp_currency_default()]] - `calls` [INFERRED]
- [[test_falls_through_to_llm_when_no_template()]] - `calls` [INFERRED]
- [[test_falls_through_to_regex_when_llm_fails()]] - `calls` [INFERRED]
- [[test_full_pipeline_llm_path()]] - `calls` [INFERRED]
- [[test_full_pipeline_regex_fallback()]] - `calls` [INFERRED]
- [[test_html_stripping()]] - `calls` [INFERRED]
- [[test_parse_banco_chile_email()]] - `calls` [INFERRED]
- [[test_parse_bchile_compra()]] - `calls` [INFERRED]
- [[test_parse_bchile_compra_parking()]] - `calls` [INFERRED]
- [[test_parse_bchile_comprobante_pago()]] - `calls` [INFERRED]
- [[test_parse_bchile_transfer()]] - `calls` [INFERRED]
- [[test_parse_bci_email()]] - `calls` [INFERRED]
- [[test_parse_bofa_cafe_at_sign()]] - `calls` [INFERRED]
- [[test_parse_bofa_spotify()]] - `calls` [INFERRED]
- [[test_parse_bofa_target()]] - `calls` [INFERRED]
- [[test_parse_bofa_wine()]] - `calls` [INFERRED]
- [[test_parse_bofa_zelle()]] - `calls` [INFERRED]
- [[test_parse_bofa_zelle_small_amount()]] - `calls` [INFERRED]
- [[test_parse_edwards_transfer_incoming()]] - `calls` [INFERRED]
- [[test_parse_pnc_zelle_received()]] - `calls` [INFERRED]
- [[test_parse_pnc_zelle_sent()]] - `calls` [INFERRED]
- [[test_parse_santander_email()]] - `calls` [INFERRED]
- [[test_parse_santander_transfer_outgoing()]] - `calls` [INFERRED]
- [[test_purchase_has_expense_type()]] - `calls` [INFERRED]
- [[test_returns_none_for_non_transaction_email()]] - `calls` [INFERRED]
- [[test_template_failure_falls_through_to_llm()]] - `calls` [INFERRED]
- [[test_uses_template_when_available()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline