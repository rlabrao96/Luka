---
source_file: "backend/jobs/tasks.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L836"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Run a Plaid transaction sync for one item.

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[FailedJob]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[PlaidItem]] - `uses` [INFERRED]
- [[ProcessedWebhook]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[WhatsAppSession]] - `uses` [INFERRED]
- [[run_plaid_sync_job()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review