---
source_file: "backend/modules/email/bank_registry_service.py"
type: "rationale"
community: "Email Filter & Bank Registry"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Email_Filter_&_Bank_Registry
---

# DB-backed bank registry with Redis cache — replaces hardcoded BANK_SENDER_DOMAIN

## Connections
- [[BankRegistry]] - `uses` [INFERRED]
- [[bank_registry_service.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Email_Filter_&_Bank_Registry