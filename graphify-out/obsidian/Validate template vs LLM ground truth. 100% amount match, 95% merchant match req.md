---
source_file: "backend/modules/email/template_agent.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L127"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Validate template vs LLM ground truth. 100% amount match, 95% merchant match req

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[validate_template()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline