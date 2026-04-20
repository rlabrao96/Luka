---
source_file: "backend/tests/test_llm_parser_integration.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L34"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Full pipeline: no template → LLM parses successfully → returns ParsedEmail with

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_full_pipeline_llm_path()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline