---
source_file: "backend/modules/email/template_agent.py"
type: "code"
community: "Email Parser Pipeline"
location: "L189"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# run_shadow_validation()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Shadow validate active templates compare template vs LLM on a sample.]] - `rationale_for` [EXTRACTED]
- [[parse_with_llm()]] - `calls` [INFERRED]
- [[retire_template()]] - `calls` [EXTRACTED]
- [[run_template_agent()]] - `calls` [EXTRACTED]
- [[should_retire_template()]] - `calls` [EXTRACTED]
- [[template_agent.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline