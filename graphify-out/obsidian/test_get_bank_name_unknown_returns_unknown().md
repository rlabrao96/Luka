---
source_file: "backend/tests/test_bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L154"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# test_get_bank_name_unknown_returns_unknown()

## Connections
- [[Returns 'Unknown' when domain is not found.]] - `rationale_for` [EXTRACTED]
- [[get_bank_name()_1]] - `calls` [INFERRED]
- [[make_db_miss()]] - `calls` [EXTRACTED]
- [[make_redis_miss()]] - `calls` [EXTRACTED]
- [[test_bank_registry_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry