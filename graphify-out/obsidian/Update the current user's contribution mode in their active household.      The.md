---
source_file: "backend/modules/households/router.py"
type: "rationale"
community: "Pydantic Schemas"
location: "L71"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Pydantic_Schemas
---

# Update the current user's contribution mode in their active household.      The

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
- [[patch_contribution_settings()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Pydantic_Schemas