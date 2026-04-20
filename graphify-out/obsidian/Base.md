---
source_file: "backend/core/database.py"
type: "code"
community: "DB, Accounts & Allocation"
location: "L20"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/DB,_Accounts_&_Allocation
---

# Base

## Connections
- [[BankAccount]] - `uses` [INFERRED]
- [[BankCredential]] - `uses` [INFERRED]
- [[BankRegistry]] - `uses` [INFERRED]
- [[CanonicalMerchant]] - `uses` [INFERRED]
- [[CategoryBudget]] - `uses` [INFERRED]
- [[CuotaPurchase]] - `uses` [INFERRED]
- [[DeclarativeBase]] - `inherits` [EXTRACTED]
- [[EmailTemplate]] - `uses` [INFERRED]
- [[FailedJob]] - `uses` [INFERRED]
- [[Household]] - `uses` [INFERRED]
- [[HouseholdBudget]] - `uses` [INFERRED]
- [[HouseholdBudgetAllocation]] - `uses` [INFERRED]
- [[HouseholdInvite]] - `uses` [INFERRED]
- [[HouseholdMember]] - `uses` [INFERRED]
- [[Merchant]] - `uses` [INFERRED]
- [[MerchantCategorySelection]] - `uses` [INFERRED]
- [[MerchantReviewJob]] - `uses` [INFERRED]
- [[Notification]] - `uses` [INFERRED]
- [[NotificationPreference]] - `uses` [INFERRED]
- [[ParsedEmailLog]] - `uses` [INFERRED]
- [[PlaidItem]] - `uses` [INFERRED]
- [[ProcessedWebhook]] - `uses` [INFERRED]
- [[Transaction]] - `uses` [INFERRED]
- [[TransactionSplit]] - `uses` [INFERRED]
- [[User]] - `uses` [INFERRED]
- [[UserBudgetSettings]] - `uses` [INFERRED]
- [[UserCategoryPreference]] - `uses` [INFERRED]
- [[UserCurrency]] - `uses` [INFERRED]
- [[database.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/DB,_Accounts_&_Allocation