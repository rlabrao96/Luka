---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "code"
community: "Email Parser Pipeline"
location: "L101"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# test_template_failure_falls_through_to_llm()

## Connections
- [[Layer 1→2 when execute_template returns None, falls through to LLM.]] - `rationale_for` [EXTRACTED]
- [[_make_parsed_email()]] - `calls` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_parser_orchestrator.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline