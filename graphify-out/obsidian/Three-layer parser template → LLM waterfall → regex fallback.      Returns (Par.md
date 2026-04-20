---
source_file: "backend/modules/email/parser.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L295"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Three-layer parser: template → LLM waterfall → regex fallback.      Returns (Par

## Connections
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmail]] - `uses` [INFERRED]
- [[parse_bank_email()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline