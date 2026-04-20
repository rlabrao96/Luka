---
source_file: "backend/tests/test_bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L272"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# test_is_bank_sender_subdomain_db_lookup()

## Connections
- [[Falls through to parent domain lookup for subdomains (e.g. noti.bancochile.cl).]] - `rationale_for` [EXTRACTED]
- [[is_bank_sender()_1]] - `calls` [INFERRED]
- [[make_bank_entry()]] - `calls` [EXTRACTED]
- [[make_redis_miss()]] - `calls` [EXTRACTED]
- [[test_bank_registry_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry