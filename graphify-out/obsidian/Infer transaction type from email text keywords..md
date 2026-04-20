---
source_file: "backend/modules/email/parser.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L219"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Infer transaction type from email text keywords.

## Connections
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmail]] - `uses` [INFERRED]
- [[_infer_transaction_type()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline