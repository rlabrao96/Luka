---
source_file: "backend/modules/email/parser.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L129"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Detect credit card payment emails and return card description as merchant.

## Connections
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmail]] - `uses` [INFERRED]
- [[_parse_cc_payment()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline