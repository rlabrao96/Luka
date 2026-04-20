---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L77"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Layer 3: falls through to regex when LLM returns None.

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_falls_through_to_regex_when_llm_fails()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline