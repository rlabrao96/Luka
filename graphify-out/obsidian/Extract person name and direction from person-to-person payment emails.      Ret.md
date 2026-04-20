---
source_file: "backend/modules/email/parser.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L152"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Extract person name and direction from person-to-person payment emails.      Ret

## Connections
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmail]] - `uses` [INFERRED]
- [[_parse_person_payment()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline