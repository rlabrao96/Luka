---
source_file: "backend/tests/test_llm_parser_integration.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L73"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Full pipeline: LLM returns None → falls back to regex → still returns a ParsedEm

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_full_pipeline_regex_fallback()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline