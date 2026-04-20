---
source_file: "backend/tests/test_bank_registry_service.py"
type: "rationale"
community: "Email Filter & Bank Registry"
location: "L250"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# Falls back to DB when Redis misses, then caches the result.

## Connections
- [[test_get_bank_metadata_db_fallback()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry