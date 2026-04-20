---
source_file: "backend/modules/email/template_agent.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L190"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Shadow validate active templates: compare template vs LLM on a sample.

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[run_shadow_validation()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline