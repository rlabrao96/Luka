---
source_file: "backend/modules/subscriptions/read.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L88"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Plaid_&_Subscriptions
---

# Sum of one user's recurring bills that are SHARED with the household.     Used b

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[get_user_shared_known_bills()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Plaid_&_Subscriptions