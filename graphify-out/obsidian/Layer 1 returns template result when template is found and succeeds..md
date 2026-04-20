---
source_file: "backend/tests/test_parser_orchestrator.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L31"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Layer 1: returns template result when template is found and succeeds.

## Connections
- [[ParsedEmail]] - `uses` [INFERRED]
- [[test_uses_template_when_available()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline