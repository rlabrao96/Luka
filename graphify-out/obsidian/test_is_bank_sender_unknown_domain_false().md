---
source_file: "backend/tests/test_bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L102"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# test_is_bank_sender_unknown_domain_false()

## Connections
- [[Returns False when domain not found in Redis or DB.]] - `rationale_for` [EXTRACTED]
- [[is_bank_sender()_1]] - `calls` [INFERRED]
- [[make_db_miss()]] - `calls` [EXTRACTED]
- [[make_redis_miss()]] - `calls` [EXTRACTED]
- [[test_bank_registry_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry