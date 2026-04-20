---
source_file: "backend/modules/email/filter.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L240"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Filter_&_Bank_Registry
---

# is_bank_sender()

## Connections
- [[Return True if the sender's domain matches a known bank.]] - `rationale_for` [EXTRACTED]
- [[_extract_domain()_1]] - `calls` [EXTRACTED]
- [[_match_bank_domain()]] - `calls` [EXTRACTED]
- [[filter.py]] - `contains` [EXTRACTED]
- [[test_bank_sender_exact_domain()]] - `calls` [INFERRED]
- [[test_bank_sender_fintech()]] - `calls` [INFERRED]
- [[test_bank_sender_rejects_empty()]] - `calls` [INFERRED]
- [[test_bank_sender_rejects_gmail()]] - `calls` [INFERRED]
- [[test_bank_sender_rejects_unknown()]] - `calls` [INFERRED]
- [[test_bank_sender_subdomain()]] - `calls` [INFERRED]
- [[test_bank_sender_with_display_name()]] - `calls` [INFERRED]
- [[test_is_bank_sender_no_domain()]] - `calls` [INFERRED]
- [[test_is_bank_sender_push_only_returns_false()]] - `calls` [INFERRED]
- [[test_is_bank_sender_redis_cache_hit_active()]] - `calls` [INFERRED]
- [[test_is_bank_sender_subdomain_db_lookup()]] - `calls` [INFERRED]
- [[test_is_bank_sender_unknown_domain_false()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Filter_&_Bank_Registry