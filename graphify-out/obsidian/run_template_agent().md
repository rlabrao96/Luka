---
source_file: "backend/modules/email/template_agent.py"
type: "code"
community: "Email Parser Pipeline"
location: "L246"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# run_template_agent()

## Connections
- [[EmailTemplate]] - `calls` [INFERRED]
- [[Main entry point — runs daily as ARQ cron job.]] - `rationale_for` [EXTRACTED]
- [[discover_candidate_banks()]] - `calls` [EXTRACTED]
- [[execute_template()]] - `calls` [INFERRED]
- [[generate_template_json()]] - `calls` [EXTRACTED]
- [[promote_template()]] - `calls` [EXTRACTED]
- [[run_shadow_validation()]] - `calls` [EXTRACTED]
- [[template_agent.py]] - `contains` [EXTRACTED]
- [[validate_template()]] - `calls` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline