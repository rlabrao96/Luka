---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L102"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Layer 1→2: when execute_template returns None, falls through to LLM.

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_template_failure_falls_through_to_llm()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline