---
source_file: "backend/tests/test_llm_parser_integration.py"
type: "code"
community: "Email Parser Pipeline"
location: "L72"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# test_full_pipeline_regex_fallback()

## Connections
- [[Full pipeline LLM returns None → falls back to regex → still returns a ParsedEm]] - `rationale_for` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_llm_parser_integration.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline