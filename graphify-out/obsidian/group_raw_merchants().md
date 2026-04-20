---
source_file: "backend/modules/merchant_review/llm_grouping.py"
type: "code"
community: "LLM Parser & Merchant Grouping"
location: "L76"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/LLM_Parser_&_Merchant_Grouping
---

# group_raw_merchants()

## Connections
- [[Group raw merchant names into canonical merchant proposals.     Batches into chu]] - `rationale_for` [EXTRACTED]
- [[_call_grouping_llm()]] - `calls` [EXTRACTED]
- [[_fallback_grouping()]] - `calls` [EXTRACTED]
- [[_seed_from_db()]] - `calls` [INFERRED]
- [[llm_grouping.py]] - `contains` [EXTRACTED]
- [[process_merchant_review()]] - `calls` [INFERRED]
- [[regroup()]] - `calls` [INFERRED]
- [[test_group_merchants_handles_empty_input()]] - `calls` [INFERRED]
- [[test_group_merchants_handles_llm_failure()]] - `calls` [INFERRED]
- [[test_group_merchants_parses_llm_response()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/LLM_Parser_&_Merchant_Grouping