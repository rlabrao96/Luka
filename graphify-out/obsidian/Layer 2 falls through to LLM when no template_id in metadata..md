---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L57"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Layer 2: falls through to LLM when no template_id in metadata.

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_falls_through_to_llm_when_no_template()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline