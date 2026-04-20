---
source_file: "backend/modules/households/router.py"
type: "rationale"
community: "Pydantic Schemas"
location: "L181"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Pydantic_Schemas
---

# Partner clicks this link from their invite email to join the household.

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
- [[accept_invite()_1]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Pydantic_Schemas