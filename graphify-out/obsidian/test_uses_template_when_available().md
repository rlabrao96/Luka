---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "code"
community: "Email Parser Pipeline"
location: "L30"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# test_uses_template_when_available()

## Connections
- [[Layer 1 returns template result when template is found and succeeds.]] - `rationale_for` [EXTRACTED]
- [[_make_parsed_email()]] - `calls` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_parser_orchestrator.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline