---
source_file: "backend/modules/subscriptions/read.py"
type: "rationale"
community: "Plaid & Subscriptions"
location: "L78"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Plaid_&_Subscriptions
---

# Sum of one user's recurring bills that are PERSONAL (not shared with     the hou

## Connections
- [[HouseholdMember]] - `uses` [INFERRED]
- [[get_user_personal_known_bills()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Plaid_&_Subscriptions