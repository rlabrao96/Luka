---
source_file: "backend/modules/email/parser.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L102"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Parse amount, returning (amount_int, currency).      US format: $17.08 → (1708,

## Connections
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmail]] - `uses` [INFERRED]
- [[_parse_amount()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline