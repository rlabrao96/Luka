---
source_file: "backend/modules/email/parser.py"
type: "code"
community: "Email Parser Pipeline"
location: "L229"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# parse_bank_email_regex()

## Connections
- [[Parse a bank email alert (Chilean or US). Returns None if not a transaction emai]] - `rationale_for` [EXTRACTED]
- [[ParsedEmail]] - `calls` [INFERRED]
- [[_infer_transaction_type()]] - `calls` [EXTRACTED]
- [[_parse_amount()]] - `calls` [EXTRACTED]
- [[_parse_cc_payment()]] - `calls` [EXTRACTED]
- [[_parse_date()]] - `calls` [EXTRACTED]
- [[_parse_merchant()]] - `calls` [EXTRACTED]
- [[_parse_person_payment()]] - `calls` [EXTRACTED]
- [[_strip_html()]] - `calls` [EXTRACTED]
- [[parse_bank_email()]] - `calls` [EXTRACTED]
- [[parser.py]] - `contains` [EXTRACTED]
- [[test_regex_parser_standalone_banco_chile()]] - `calls` [INFERRED]

#graphify/code #graphify/EXTRACTED #community/Email_Parser_Pipeline