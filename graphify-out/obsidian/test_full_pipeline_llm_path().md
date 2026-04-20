---
source_file: "backend/tests/test_llm_parser_integration.py"
type: "code"
community: "Email Parser Pipeline"
location: "L33"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# test_full_pipeline_llm_path()

## Connections
- [[Full pipeline no template → LLM parses successfully → returns ParsedEmail with]] - `rationale_for` [EXTRACTED]
- [[ParsedEmail]] - `calls` [INFERRED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[patch()]] - `calls` [INFERRED]
- [[test_llm_parser_integration.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline