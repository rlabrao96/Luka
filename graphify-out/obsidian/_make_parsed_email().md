---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "code"
community: "Email Parser Pipeline"
location: "L11"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# _make_parsed_email()

## Connections
- [[ParsedEmail]] - `calls` [INFERRED]
- [[test_falls_through_to_llm_when_no_template()]] - `calls` [EXTRACTED]
- [[test_falls_through_to_regex_when_llm_fails()]] - `calls` [EXTRACTED]
- [[test_parser_orchestrator.py]] - `contains` [EXTRACTED]
- [[test_template_failure_falls_through_to_llm()]] - `calls` [EXTRACTED]
- [[test_uses_template_when_available()]] - `calls` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline