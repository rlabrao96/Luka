---
source_file: "backend/modules/households/models.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L40"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# HouseholdInvite

## Connections
- [[Aggregate stats for all active members — no individual transaction rows.]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Monthly household spending by member. No privacy restriction — both members see]] - `uses` [INFERRED]
- [[Pool-based settlement for N members. Returns minimal list of transfers.]] - `uses` [INFERRED]
- [[Pure function groups SQL rows into category breakdown with percentages.]] - `uses` [INFERRED]
- [[Return active members with their roles.]] - `uses` [INFERRED]
- [[Return equal split ratio for n members summing to 100.]] - `uses` [INFERRED]
- [[Return non-accepted, non-expired invites.]] - `uses` [INFERRED]
- [[Returns per-category spending breakdown for shared transactions.]] - `uses` [INFERRED]
- [[Returns settlement suggestion for the household.]] - `uses` [INFERRED]
- [[Soft-delete a member from a household. Returns the new individual household id.]] - `uses` [INFERRED]
- [[create_invite()]] - `calls` [INFERRED]
- [[models.py_7]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation