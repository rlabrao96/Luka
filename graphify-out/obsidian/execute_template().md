---
source_file: "backend/modules/email/template_executor.py"
type: "code"
community: "Email Template Executor"
location: "L118"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Template_Executor
---

# execute_template()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[ParsedEmail]] - `calls` [INFERRED]
- [[_detect_transaction_type()]] - `calls` [EXTRACTED]
- [[_extract_field()]] - `calls` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[run_template_agent()]] - `calls` [INFERRED]
- [[template_executor.py]] - `contains` [EXTRACTED]
- [[test_date_fallback_to_utcnow_when_no_date_selector()]] - `calls` [INFERRED]
- [[test_full_extraction_from_html()]] - `calls` [INFERRED]
- [[test_returns_none_for_empty_template()]] - `calls` [INFERRED]
- [[test_returns_none_for_invalid_template()]] - `calls` [INFERRED]
- [[test_returns_none_when_amount_missing()]] - `calls` [INFERRED]
- [[test_transaction_type_transfer_keyword()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Template_Executor