---
source_file: "backend/tests/test_bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L90"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Email_Filter_&_Bank_Registry
---

# test_is_bank_sender_redis_cache_hit_active()

## Connections
- [[Returns True for a known active domain when Redis returns cached data.]] - `rationale_for` [EXTRACTED]
- [[is_bank_sender()_1]] - `calls` [INFERRED]
- [[make_redis_hit()]] - `calls` [EXTRACTED]
- [[test_bank_registry_service.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Email_Filter_&_Bank_Registry