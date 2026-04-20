---
type: community
cohesion: 0.03
members: 118
---

# Email Parser Pipeline

**Cohesion:** 0.03 - loosely connected
**Members:** 118 nodes

## Members
- [[100% amount + 100% merchant match → passes.]] - rationale - backend/tests/test_template_agent.py
- [[A single amount mismatch causes validation to fail regardless of merchant accura]] - rationale - backend/tests/test_template_agent.py
- [[A single amount_match=False entry triggers retirement.]] - rationale - backend/tests/test_template_agent.py
- [[ANY amount mismatch in shadow validation triggers retirement.]] - rationale - backend/modules/email/template_agent.py
- [[Autonomous Template Agent — discovers, generates, validates, promotes, and retir]] - rationale - backend/modules/email/template_agent.py
- [[BankRegistry]] - code - backend/modules/email/models.py
- [[Detect credit card payment emails and return card description as merchant.]] - rationale - backend/modules/email/parser.py
- [[Email expense should store negative amount and transaction_type='expense'.]] - rationale - backend/tests/test_process_email_txtype.py
- [[Email income should store positive amount and transaction_type='income'.]] - rationale - backend/tests/test_process_email_txtype.py
- [[EmailTemplate]] - code - backend/modules/email/models.py
- [[Empty shadow results → no retirement (nothing to compare).]] - rationale - backend/tests/test_template_agent.py
- [[Empty template_results list returns False.]] - rationale - backend/tests/test_template_agent.py
- [[Even with 100% amount match, 95% merchant accuracy causes failure.]] - rationale - backend/tests/test_template_agent.py
- [[Exactly 95% merchant accuracy with 100% amounts should pass (1920).]] - rationale - backend/tests/test_template_agent.py
- [[Extract person name and direction from person-to-person payment emails.      Ret]] - rationale - backend/modules/email/parser.py
- [[Find banks with enough LLM-parsed emails but no active template.]] - rationale - backend/modules/email/template_agent.py
- [[Full pipeline LLM returns None → falls back to regex → still returns a ParsedEm]] - rationale - backend/tests/test_llm_parser_integration.py
- [[Full pipeline no template → LLM parses successfully → returns ParsedEmail with]] - rationale - backend/tests/test_llm_parser_integration.py
- [[Infer transaction type from email text keywords.]] - rationale - backend/modules/email/parser.py
- [[Integration tests for the three-layer parser pipeline.  Tests the interaction be]] - rationale - backend/tests/test_llm_parser_integration.py
- [[Layer 1 returns template result when template is found and succeeds.]] - rationale - backend/tests/test_parser_orchestrator.py
- [[Layer 1→2 when execute_template returns None, falls through to LLM.]] - rationale - backend/tests/test_parser_orchestrator.py
- [[Layer 2 falls through to LLM when no template_id in metadata.]] - rationale - backend/tests/test_parser_orchestrator.py
- [[Layer 3 falls through to regex when LLM returns None.]] - rationale - backend/tests/test_parser_orchestrator.py
- [[Main entry point — runs daily as ARQ cron job.]] - rationale - backend/modules/email/template_agent.py
- [[Missing amount_match key defaults to True (no mismatch assumed).]] - rationale - backend/tests/test_template_agent.py
- [[No retirement when every shadow result has amount_match=True.]] - rationale - backend/tests/test_template_agent.py
- [[One-off script fix BofA transactions created before USD parsing was added.  Run]] - rationale - backend/scripts/fix_bofa_transactions.py
- [[Parse a bank email alert (Chilean or US). Returns None if not a transaction emai]] - rationale - backend/modules/email/parser.py
- [[Parse amount, returning (amount_int, currency).      US format $17.08 → (1708,]] - rationale - backend/modules/email/parser.py
- [[ParsedEmail]] - code - backend/modules/email/base.py
- [[Scan for Banco de Chile TC payment and transfer emails specifically.]] - rationale - backend/scripts/scan_tc_payments.py
- [[Shadow validate active templates compare template vs LLM on a sample.]] - rationale - backend/modules/email/template_agent.py
- [[Strip HTML tags, stylescript blocks, and collapse whitespace.]] - rationale - backend/modules/email/parser.py
- [[Template merchant that is a substring of LLM merchant is counted as a match.]] - rationale - backend/tests/test_template_agent.py
- [[Tests for pure functions in the autonomous template agent.]] - rationale - backend/tests/test_template_agent.py
- [[Tests for the three-layer parser orchestrator in modules.email.parser.]] - rationale - backend/tests/test_parser_orchestrator.py
- [[Three-layer parser template → LLM waterfall → regex fallback.      Returns (Par]] - rationale - backend/modules/email/parser.py
- [[Unequal list lengths return False immediately.]] - rationale - backend/tests/test_template_agent.py
- [[Use LLM to generate a declarative extraction template from samples.]] - rationale - backend/modules/email/template_agent.py
- [[Validate template vs LLM ground truth. 100% amount match, 95% merchant match req]] - rationale - backend/modules/email/template_agent.py
- [[_extract_body()]] - code - backend/scripts/scan_tc_payments.py
- [[_get_active_template()]] - code - backend/modules/email/parser.py
- [[_get_client()_3]] - code - backend/modules/email/template_agent.py
- [[_infer_transaction_type()]] - code - backend/modules/email/parser.py
- [[_make_parsed_email()]] - code - backend/tests/test_parser_orchestrator.py
- [[_parse_amount()]] - code - backend/modules/email/parser.py
- [[_parse_cc_payment()]] - code - backend/modules/email/parser.py
- [[_parse_date()]] - code - backend/modules/email/parser.py
- [[_parse_merchant()]] - code - backend/modules/email/parser.py
- [[_parse_person_payment()]] - code - backend/modules/email/parser.py
- [[_strip_html()]] - code - backend/modules/email/parser.py
- [[discover_candidate_banks()]] - code - backend/modules/email/template_agent.py
- [[fix_bofa_transactions.py]] - code - backend/scripts/fix_bofa_transactions.py
- [[generate_template_json()]] - code - backend/modules/email/template_agent.py
- [[main()]] - code - backend/scripts/fix_bofa_transactions.py
- [[main()_2]] - code - backend/scripts/scan_tc_payments.py
- [[main()_9]] - code - backend/scripts/test_pipeline.py
- [[models.py_10]] - code - backend/modules/email/models.py
- [[parse_bank_email()]] - code - backend/modules/email/parser.py
- [[parse_bank_email_regex correctly parses the Banco de Chile sample without any mo]] - rationale - backend/tests/test_llm_parser_integration.py
- [[parse_bank_email_regex()]] - code - backend/modules/email/parser.py
- [[parser.py]] - code - backend/modules/email/parser.py
- [[promote_template()]] - code - backend/modules/email/template_agent.py
- [[retire_template()]] - code - backend/modules/email/template_agent.py
- [[run_shadow_validation()]] - code - backend/modules/email/template_agent.py
- [[run_template_agent()]] - code - backend/modules/email/template_agent.py
- [[scan_tc_payments.py]] - code - backend/scripts/scan_tc_payments.py
- [[should_retire_template()]] - code - backend/modules/email/template_agent.py
- [[template_agent.py]] - code - backend/modules/email/template_agent.py
- [[test_clp_currency_default()]] - code - backend/tests/test_email_parser.py
- [[test_email_parser.py]] - code - backend/tests/test_email_parser.py
- [[test_expense_email_stores_negative_amount_and_type()]] - code - backend/tests/test_process_email_txtype.py
- [[test_falls_through_to_llm_when_no_template()]] - code - backend/tests/test_parser_orchestrator.py
- [[test_falls_through_to_regex_when_llm_fails()]] - code - backend/tests/test_parser_orchestrator.py
- [[test_full_pipeline_llm_path()]] - code - backend/tests/test_llm_parser_integration.py
- [[test_full_pipeline_regex_fallback()]] - code - backend/tests/test_llm_parser_integration.py
- [[test_html_stripping()]] - code - backend/tests/test_email_parser.py
- [[test_income_email_stores_positive_amount()]] - code - backend/tests/test_process_email_txtype.py
- [[test_llm_parser_integration.py]] - code - backend/tests/test_llm_parser_integration.py
- [[test_parse_banco_chile_email()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bchile_compra()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bchile_compra_parking()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bchile_comprobante_pago()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bchile_transfer()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bci_email()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_cafe_at_sign()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_spotify()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_target()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_wine()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_zelle()]] - code - backend/tests/test_email_parser.py
- [[test_parse_bofa_zelle_small_amount()]] - code - backend/tests/test_email_parser.py
- [[test_parse_edwards_transfer_incoming()]] - code - backend/tests/test_email_parser.py
- [[test_parse_pnc_zelle_received()]] - code - backend/tests/test_email_parser.py
- [[test_parse_pnc_zelle_sent()]] - code - backend/tests/test_email_parser.py
- [[test_parse_santander_email()]] - code - backend/tests/test_email_parser.py
- [[test_parse_santander_transfer_outgoing()]] - code - backend/tests/test_email_parser.py
- [[test_parser_orchestrator.py]] - code - backend/tests/test_parser_orchestrator.py
- [[test_pipeline.py]] - code - backend/scripts/test_pipeline.py
- [[test_process_email_txtype.py]] - code - backend/tests/test_process_email_txtype.py
- [[test_purchase_has_expense_type()]] - code - backend/tests/test_email_parser.py
- [[test_regex_parser_standalone_banco_chile()]] - code - backend/tests/test_llm_parser_integration.py
- [[test_returns_none_for_non_transaction_email()]] - code - backend/tests/test_email_parser.py
- [[test_should_retire_template_returns_false_on_empty_results()]] - code - backend/tests/test_template_agent.py
- [[test_should_retire_template_returns_false_when_all_amounts_match()]] - code - backend/tests/test_template_agent.py
- [[test_should_retire_template_returns_true_on_any_amount_mismatch()]] - code - backend/tests/test_template_agent.py
- [[test_should_retire_template_treats_missing_amount_match_key_as_ok()]] - code - backend/tests/test_template_agent.py
- [[test_template_agent.py]] - code - backend/tests/test_template_agent.py
- [[test_template_failure_falls_through_to_llm()]] - code - backend/tests/test_parser_orchestrator.py
- [[test_uses_template_when_available()]] - code - backend/tests/test_parser_orchestrator.py
- [[test_validate_template_fails_on_any_amount_mismatch()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_fails_on_empty_results()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_fails_on_low_merchant_accuracy()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_fails_on_mismatched_list_lengths()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_merchant_substring_match_counts()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_passes_at_exactly_95_percent_merchant()]] - code - backend/tests/test_template_agent.py
- [[test_validate_template_passes_with_perfect_accuracy()]] - code - backend/tests/test_template_agent.py
- [[validate_template()]] - code - backend/modules/email/template_agent.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Email_Parser_Pipeline
SORT file.name ASC
```

## Connections to other communities
- 19 edges to [[_COMMUNITY_Backend Core & Infra]]
- 8 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 6 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 5 edges to [[_COMMUNITY_LLM Parser & Merchant Grouping]]
- 4 edges to [[_COMMUNITY_Email Template Executor]]
- 3 edges to [[_COMMUNITY_Merchants & WhatsApp]]
- 2 edges to [[_COMMUNITY_Email Filter & Bank Registry]]

## Top bridge nodes
- [[parse_bank_email()]] - degree 41, connects to 3 communities
- [[ParsedEmail]] - degree 26, connects to 3 communities
- [[BankRegistry]] - degree 11, connects to 2 communities
- [[main()_9]] - degree 8, connects to 2 communities
- [[run_shadow_validation()]] - degree 7, connects to 2 communities