---
source_file: "backend/modules/email/template_agent.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L152"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# ANY amount mismatch in shadow validation triggers retirement.

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[should_retire_template()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline