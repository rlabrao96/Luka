---
source_file: "backend/modules/email/template_agent.py"
type: "code"
community: "Email Parser Pipeline"
location: "L151"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# should_retire_template()

## Connections
- [[ANY amount mismatch in shadow validation triggers retirement.]] - `rationale_for` [EXTRACTED]
- [[GET()]] - `calls` [INFERRED]
- [[run_shadow_validation()]] - `calls` [EXTRACTED]
- [[template_agent.py]] - `contains` [EXTRACTED]
- [[test_should_retire_template_returns_false_on_empty_results()]] - `calls` [INFERRED]
- [[test_should_retire_template_returns_false_when_all_amounts_match()]] - `calls` [INFERRED]
- [[test_should_retire_template_returns_true_on_any_amount_mismatch()]] - `calls` [INFERRED]
- [[test_should_retire_template_treats_missing_amount_match_key_as_ok()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline