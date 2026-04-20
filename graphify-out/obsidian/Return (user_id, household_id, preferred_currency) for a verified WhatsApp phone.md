---
source_file: "backend/modules/whatsapp/handler.py"
type: "rationale"
community: "DB, Accounts & Allocation"
location: "L308"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Return (user_id, household_id, preferred_currency) for a verified WhatsApp phone

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[WhatsAppSession]] - `uses` [INFERRED]
- [[_get_user_and_household_by_phone()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/DB,_Accounts_&_Allocation