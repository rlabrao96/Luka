---
source_file: "backend/modules/email/llm_parser.py"
type: "code"
community: "LLM Parser & Merchant Grouping"
location: "L140"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/LLM_Parser_&_Merchant_Grouping
---

# parse_with_llm()

## Connections
- [[_build_system_prompt()]] - `calls` [EXTRACTED]
- [[_extraction_to_parsed_email()]] - `calls` [EXTRACTED]
- [[_get_client()_2]] - `calls` [EXTRACTED]
- [[_parse_llm_response()]] - `calls` [EXTRACTED]
- [[llm_parser.py]] - `contains` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[run_shadow_validation()]] - `calls` [INFERRED]
- [[test_parse_with_llm_escalates_on_low_confidence()]] - `calls` [INFERRED]
- [[test_parse_with_llm_returns_none_on_total_failure()]] - `calls` [INFERRED]
- [[test_parse_with_llm_success()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/LLM_Parser_&_Merchant_Grouping