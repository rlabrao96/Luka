---
source_file: "backend/modules/bank_connect/mapper.py"
type: "code"
community: "Bank Connect Mapper"
location: "L18"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Bank_Connect_Mapper
---

# is_inter_account_transfer()

## Connections
- [[Return True if the movement description matches a known inter-account pattern.]] - `rationale_for` [EXTRACTED]
- [[map_movement_to_transaction()]] - `calls` [EXTRACTED]
- [[mapper.py]] - `contains` [EXTRACTED]
- [[test_is_inter_account_transfer_cc_payment()]] - `calls` [INFERRED]
- [[test_is_inter_account_transfer_own_account()]] - `calls` [INFERRED]
- [[test_is_inter_account_transfer_person_not_transfer()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Bank_Connect_Mapper