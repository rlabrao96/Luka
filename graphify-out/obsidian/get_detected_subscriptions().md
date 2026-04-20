---
source_file: "backend/modules/subscriptions/service.py"
type: "code"
community: "Plaid & Subscriptions"
location: "L127"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Plaid_&_Subscriptions
---

# get_detected_subscriptions()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Read from DB cache, compute on first access. Merge overrides at read time.]] - `rationale_for` [EXTRACTED]
- [[_compute_and_store()]] - `calls` [EXTRACTED]
- [[_compute_summary_by_currency()]] - `calls` [EXTRACTED]
- [[_merge_overrides()]] - `calls` [EXTRACTED]
- [[_sum_user_bills_by_split_type()]] - `calls` [INFERRED]
- [[detected_subscriptions()]] - `calls` [INFERRED]
- [[get_user_known_bills()]] - `calls` [INFERRED]
- [[refresh_subscriptions()]] - `calls` [EXTRACTED]
- [[service.py_3]] - `contains` [EXTRACTED]
- [[test_no_override_falls_back_to_inferred()]] - `calls` [INFERRED]
- [[test_override_split_type_wins_over_inferred()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Plaid_&_Subscriptions