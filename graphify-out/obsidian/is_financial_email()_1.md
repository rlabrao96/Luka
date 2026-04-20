---
source_file: "backend/modules/email/filter.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L259"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Filter_&_Bank_Registry
---

# is_financial_email()

## Connections
- [[Check if an email is likely a financial notification based on keyword matching.]] - `rationale_for` [EXTRACTED]
- [[filter.py]] - `contains` [EXTRACTED]
- [[main()_4]] - `calls` [INFERRED]
- [[main()_5]] - `calls` [INFERRED]
- [[main()_9]] - `calls` [INFERRED]
- [[test_case_insensitive()]] - `calls` [INFERRED]
- [[test_filter_accepts_financial_in_pipeline_context()]] - `calls` [INFERRED]
- [[test_filter_rejects_non_financial_in_pipeline_context()]] - `calls` [INFERRED]
- [[test_is_financial_email_english_keywords()]] - `calls` [INFERRED]
- [[test_is_financial_email_portuguese_keywords()]] - `calls` [INFERRED]
- [[test_is_financial_email_rejects_non_financial()]] - `calls` [INFERRED]
- [[test_is_financial_email_spanish_keywords()]] - `calls` [INFERRED]
- [[test_matches_atm_withdrawal()]] - `calls` [INFERRED]
- [[test_matches_credit_card_payment()]] - `calls` [INFERRED]
- [[test_matches_credit_card_purchase()]] - `calls` [INFERRED]
- [[test_matches_deposit()]] - `calls` [INFERRED]
- [[test_matches_keyword_in_sender_only()]] - `calls` [INFERRED]
- [[test_matches_pac_pat()]] - `calls` [INFERRED]
- [[test_matches_transfer_email()]] - `calls` [INFERRED]
- [[test_rejects_newsletter()]] - `calls` [INFERRED]
- [[test_rejects_personal_email()]] - `calls` [INFERRED]
- [[test_rejects_promotional_bank_email_without_keywords()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Filter_&_Bank_Registry