---
source_file: "backend/modules/email/template_agent.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L247"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# Main entry point — runs daily as ARQ cron job.

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[run_template_agent()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Parser_Pipeline