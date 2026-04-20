---
type: community
cohesion: 0.07
members: 44
---

# LLM Parser & Merchant Grouping

**Cohesion:** 0.07 - loosely connected
**Members:** 44 nodes

## Members
- [[Fix common LLM JSON issues trailing commas before  or }.]] - rationale - backend/modules/merchant_review/llm_grouping.py
- [[Group raw merchant names into canonical merchant proposals.     Batches into chu]] - rationale - backend/modules/merchant_review/llm_grouping.py
- [[If LLM fails, each name becomes its own group with title-cased name.]] - rationale - backend/modules/merchant_review/llm_grouping.py
- [[LLM-powered email parser with confidence-based model waterfall.]] - rationale - backend/modules/email/llm_parser.py
- [[System prompt for BR country must include bank name and BRL rule.]] - rationale - backend/tests/test_llm_parser.py
- [[System prompt for CL country must include CLP currency rule.]] - rationale - backend/tests/test_llm_parser.py
- [[Test that the grouping function correctly parses LLM JSON output.]] - rationale - backend/tests/test_llm_grouping.py
- [[Tests for the LLM email parser with confidence waterfall.]] - rationale - backend/tests/test_llm_parser.py
- [[WATERFALL_MODELS must be ordered cheapest to most expensive (thresholds descendi]] - rationale - backend/tests/test_llm_parser.py
- [[_build_system_prompt()]] - code - backend/modules/email/llm_parser.py
- [[_call_grouping_llm()]] - code - backend/modules/merchant_review/llm_grouping.py
- [[_extraction_to_parsed_email()]] - code - backend/modules/email/llm_parser.py
- [[_fallback_grouping()]] - code - backend/modules/merchant_review/llm_grouping.py
- [[_fix_json()]] - code - backend/modules/merchant_review/llm_grouping.py
- [[_get_client()_2]] - code - backend/modules/email/llm_parser.py
- [[_make_mock_response()]] - code - backend/tests/test_llm_parser.py
- [[_parse_llm_response handles JSON wrapped in markdown code fences.]] - rationale - backend/tests/test_llm_parser.py
- [[_parse_llm_response returns None for malformed  non-JSON text.]] - rationale - backend/tests/test_llm_parser.py
- [[_parse_llm_response returns None when required fields are absent.]] - rationale - backend/tests/test_llm_parser.py
- [[_parse_llm_response returns a dict for valid JSON with all required fields.]] - rationale - backend/tests/test_llm_parser.py
- [[_parse_llm_response()]] - code - backend/modules/email/llm_parser.py
- [[_strip_code_fences()_1]] - code - backend/modules/email/llm_parser.py
- [[group_raw_merchants()]] - code - backend/modules/merchant_review/llm_grouping.py
- [[llm_grouping.py]] - code - backend/modules/merchant_review/llm_grouping.py
- [[llm_parser.py]] - code - backend/modules/email/llm_parser.py
- [[parse_with_llm escalates to the next model when confidence is below threshold.]] - rationale - backend/tests/test_llm_parser.py
- [[parse_with_llm returns (None, 4, None) when all models raise exceptions.]] - rationale - backend/tests/test_llm_parser.py
- [[parse_with_llm returns a ParsedEmail on a high-confidence first-model response.]] - rationale - backend/tests/test_llm_parser.py
- [[parse_with_llm()]] - code - backend/modules/email/llm_parser.py
- [[test_build_system_prompt_br_context()]] - code - backend/tests/test_llm_parser.py
- [[test_build_system_prompt_cl_currency()]] - code - backend/tests/test_llm_parser.py
- [[test_group_merchants_handles_empty_input()]] - code - backend/tests/test_llm_grouping.py
- [[test_group_merchants_handles_llm_failure()]] - code - backend/tests/test_llm_grouping.py
- [[test_group_merchants_parses_llm_response()]] - code - backend/tests/test_llm_grouping.py
- [[test_llm_grouping.py]] - code - backend/tests/test_llm_grouping.py
- [[test_llm_parser.py]] - code - backend/tests/test_llm_parser.py
- [[test_parse_llm_response_malformed_json()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_llm_response_missing_required_fields()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_llm_response_strips_code_fences()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_llm_response_valid_json()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_with_llm_escalates_on_low_confidence()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_with_llm_returns_none_on_total_failure()]] - code - backend/tests/test_llm_parser.py
- [[test_parse_with_llm_success()]] - code - backend/tests/test_llm_parser.py
- [[test_waterfall_models_ordered()]] - code - backend/tests/test_llm_parser.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/LLM_Parser_&_Merchant_Grouping
SORT file.name ASC
```

## Connections to other communities
- 7 edges to [[_COMMUNITY_Backend Core & Infra]]
- 5 edges to [[_COMMUNITY_Email Parser Pipeline]]
- 3 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]

## Top bridge nodes
- [[_extraction_to_parsed_email()]] - degree 4, connects to 2 communities
- [[group_raw_merchants()]] - degree 10, connects to 1 community
- [[parse_with_llm()]] - degree 10, connects to 1 community
- [[test_parse_with_llm_success()]] - degree 5, connects to 1 community
- [[_call_grouping_llm()]] - degree 5, connects to 1 community