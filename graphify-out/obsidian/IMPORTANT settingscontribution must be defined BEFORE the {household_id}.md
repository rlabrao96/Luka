---
source_file: "backend/modules/households/router.py"
type: "rationale"
community: "Pydantic Schemas"
location: "L43"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Pydantic_Schemas
---

# # IMPORTANT: /settings/contribution must be defined BEFORE the /{household_id}

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