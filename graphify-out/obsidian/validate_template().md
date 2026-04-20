---
source_file: "backend/modules/email/template_agent.py"
type: "code"
community: "Email Parser Pipeline"
location: "L126"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# validate_template()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Validate template vs LLM ground truth. 100% amount match, 95% merchant match req]] - `rationale_for` [EXTRACTED]
- [[run_template_agent()]] - `calls` [EXTRACTED]
- [[template_agent.py]] - `contains` [EXTRACTED]
- [[test_validate_template_fails_on_any_amount_mismatch()]] - `calls` [INFERRED]
- [[test_validate_template_fails_on_empty_results()]] - `calls` [INFERRED]
- [[test_validate_template_fails_on_low_merchant_accuracy()]] - `calls` [INFERRED]
- [[test_validate_template_fails_on_mismatched_list_lengths()]] - `calls` [INFERRED]
- [[test_validate_template_merchant_substring_match_counts()]] - `calls` [INFERRED]
- [[test_validate_template_passes_at_exactly_95_percent_merchant()]] - `calls` [INFERRED]
- [[test_validate_template_passes_with_perfect_accuracy()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline