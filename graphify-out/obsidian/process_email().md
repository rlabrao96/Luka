---
source_file: "backend/jobs/tasks.py"
type: "code"
community: "Backend Core & Infra"
location: "L155"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Backend_Core_&_Infra
---

# process_email()

## Connections
- [[.get_current_token()]] - `calls` [INFERRED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `rationale_for` [EXTRACTED]
- [[GET()]] - `calls` [INFERRED]
- [[ParsedEmailLog]] - `calls` [INFERRED]
- [[Transaction]] - `calls` [INFERRED]
- [[TransactionSplit]] - `calls` [INFERRED]
- [[WhatsAppSession]] - `calls` [INFERRED]
- [[_record_failed_job()]] - `calls` [EXTRACTED]
- [[_strip_html()]] - `calls` [INFERRED]
- [[decrypt_token()]] - `calls` [INFERRED]
- [[encrypt_token()]] - `calls` [INFERRED]
- [[fetch_new_emails()]] - `calls` [INFERRED]
- [[get_bank_metadata()]] - `calls` [INFERRED]
- [[get_email_provider()]] - `calls` [INFERRED]
- [[is_duplicate_transaction()]] - `calls` [INFERRED]
- [[lookup_merchant()]] - `calls` [INFERRED]
- [[parse_bank_email()]] - `calls` [INFERRED]
- [[save_msgid()]] - `calls` [INFERRED]
- [[save_session()]] - `calls` [INFERRED]
- [[send_expense_alert()]] - `calls` [INFERRED]
- [[send_transfer_alert()]] - `calls` [INFERRED]
- [[tasks.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Backend_Core_&_Infra