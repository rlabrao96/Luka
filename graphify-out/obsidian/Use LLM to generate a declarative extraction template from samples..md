---
source_file: "backend/modules/email/template_agent.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L66"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Use LLM to generate a declarative extraction template from samples.

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[generate_template_json()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline