---
source_file: "backend/scripts/scan_tc_payments.py"
type: "code"
community: "Email Parser Pipeline"
location: "L31"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# main()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[_extract_body()]] - `calls` [EXTRACTED]
- [[_strip_html()]] - `calls` [INFERRED]
- [[decrypt_token()]] - `calls` [INFERRED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[scan_tc_payments.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline