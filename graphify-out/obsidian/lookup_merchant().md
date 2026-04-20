---
source_file: "backend/modules/merchants/service.py"
type: "code"
community: "Merchants & WhatsApp"
location: "L17"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Merchants_&_WhatsApp
---

# lookup_merchant()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Look up merchant categories Redis L1 → DB L2 → LLM fallback.     Returns 1 cate]] - `rationale_for` [EXTRACTED]
- [[Merchant]] - `calls` [INFERRED]
- [[_seed_from_db()]] - `calls` [INFERRED]
- [[categorize_with_llm()]] - `calls` [INFERRED]
- [[main()_6]] - `calls` [INFERRED]
- [[main()_9]] - `calls` [INFERRED]
- [[normalize_merchant()]] - `calls` [INFERRED]
- [[process_email()]] - `calls` [INFERRED]
- [[process_merchant_review()]] - `calls` [INFERRED]
- [[send_test_transaction()]] - `calls` [INFERRED]
- [[service.py_4]] - `contains` [EXTRACTED]
- [[test_calls_llm_on_cache_and_db_miss()]] - `calls` [INFERRED]
- [[test_returns_cached_categories_on_redis_hit()]] - `calls` [INFERRED]
- [[test_returns_single_category_for_known_merchant()]] - `calls` [INFERRED]
- [[test_returns_single_llm_suggestion_for_merchant_without_selections()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Merchants_&_WhatsApp