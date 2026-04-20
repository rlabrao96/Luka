---
source_file: "backend/modules/households/router.py"
type: "rationale"
community: "Pydantic Schemas"
location: "L112"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Pydantic_Schemas
---

# # IMPORTANT: create-and-invite must be defined BEFORE /{household_id}/... routes

## Connections
- [[CreateHouseholdRequest]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[HouseholdResponse]] - `uses` [INFERRED]
- [[InviteRequest]] - `uses` [INFERRED]
- [[MemberRoleRequest]] - `uses` [INFERRED]
- [[SettlementEnabledRequest]] - `uses` [INFERRED]
- [[SettlementResponse]] - `uses` [INFERRED]
- [[SplitRatioRequest]] - `uses` [INFERRED]
- [[SplitRatioResponse]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[router.py_9]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Pydantic_Schemas