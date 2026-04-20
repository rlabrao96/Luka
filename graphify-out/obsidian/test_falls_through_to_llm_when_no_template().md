---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "code"
community: "Email Parser Pipeline"
location: "L56"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# test_falls_through_to_llm_when_no_template()

## Connections
- [[Layer 2 falls through to LLM when no template_id in metadata.]] - `rationale_for` [EXTRACTED]
- [[_make_parsed_email()]] - `calls` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_parser_orchestrator.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline