---
source_file: "backend/tests/test_bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L249"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# test_get_bank_metadata_db_fallback()

## Connections
- [[Falls back to DB when Redis misses, then caches the result.]] - `rationale_for` [EXTRACTED]
- [[get_bank_metadata()]] - `calls` [INFERRED]
- [[make_bank_entry()]] - `calls` [EXTRACTED]
- [[make_db_returning()]] - `calls` [EXTRACTED]
- [[make_redis_miss()]] - `calls` [EXTRACTED]
- [[test_bank_registry_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry