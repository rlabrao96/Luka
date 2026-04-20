---
source_file: "backend/jobs/tasks.py"
type: "rationale"
community: "Luka Connect & Merchant Review"
location: "L625"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# Triggered after new bank account — recompute subscriptions for one user.

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
- [[refresh_subscriptions_for_user()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review