---
source_file: "backend/modules/bank_connect/service.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L116"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Luka_Connect_&_Merchant_Review
---

# Schedule next sync ~24h from now (jittered ±2h to avoid thundering herd).

## Connections
- [[BankCredential]] - `uses` [INFERRED]
- [[_random_next_sync()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Luka_Connect_&_Merchant_Review