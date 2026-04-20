---
type: community
cohesion: 0.06
members: 75
---

# Pydantic Schemas

**Cohesion:** 0.06 - loosely connected
**Members:** 75 nodes

## Members
- [[IMPORTANT settingscontribution must be defined BEFORE the {household_id}]] - rationale - backend/modules/households/router.py
- [[IMPORTANT create-and-invite must be defined BEFORE {household_id}... routes]] - rationale - backend/modules/households/router.py
- [[AddCurrencyBody]] - code - backend/modules/currencies/schemas.py
- [[AllocationBlock]] - code - backend/modules/budgets/schemas.py
- [[AllocationResponse]] - code - backend/modules/budgets/schemas.py
- [[AllocationSuggestion]] - code - backend/modules/budgets/schemas.py
- [[AllocationSuggestions]] - code - backend/modules/budgets/schemas.py
- [[BaseModel]] - code
- [[BreakdownBlock]] - code - backend/modules/budgets/schemas.py
- [[BudgetStatusResponse]] - code - backend/modules/budgets/schemas.py
- [[CategoryAddRequest]] - code - backend/modules/settings/schemas.py
- [[CategoryBreakdownRow]] - code - backend/modules/households/schemas.py
- [[CategoryBudgetItem]] - code - backend/modules/budgets/schemas.py
- [[CategoryBudgetResponse]] - code - backend/modules/budgets/schemas.py
- [[CategoryDeleteRequest]] - code - backend/modules/settings/schemas.py
- [[CategoryPreferenceItem]] - code - backend/modules/settings/schemas.py
- [[CategoryReorderItem]] - code - backend/modules/settings/schemas.py
- [[CategoryReorderRequest]] - code - backend/modules/settings/schemas.py
- [[CategoryUpdateRequest]] - code - backend/modules/transactions/schemas.py
- [[ContributionUpdateRequest]] - code - backend/modules/households/router.py
- [[ContributionUpdateResponse]] - code - backend/modules/households/router.py
- [[CreateHouseholdRequest]] - code - backend/modules/households/schemas.py
- [[HouseholdBlock]] - code - backend/modules/budgets/schemas.py
- [[HouseholdResponse]] - code - backend/modules/households/schemas.py
- [[HouseholdSummaryResponse]] - code - backend/modules/households/schemas.py
- [[InviteRequest]] - code - backend/modules/households/schemas.py
- [[MemberRoleRequest]] - code - backend/modules/households/schemas.py
- [[MemberTotal]] - code - backend/modules/households/schemas.py
- [[MerchantApproval]] - code - backend/modules/merchant_review/schemas.py
- [[NotificationPreferencesResponse]] - code - backend/modules/settings/schemas.py
- [[NotificationPreferencesUpdate]] - code - backend/modules/settings/schemas.py
- [[NotificationResponse]] - code - backend/modules/notifications/schemas.py
- [[NotificationUpdate]] - code - backend/modules/notifications/schemas.py
- [[PaceBlock]] - code - backend/modules/budgets/schemas.py
- [[PacePoint]] - code - backend/modules/budgets/schemas.py
- [[Partner clicks this link from their invite email to join the household.]] - rationale - backend/modules/households/router.py
- [[PendingTransactionsResponse]] - code - backend/modules/transactions/schemas.py
- [[PersonalBlock]] - code - backend/modules/budgets/schemas.py
- [[PersonalBudgetResponse]] - code - backend/modules/budgets/schemas.py
- [[RecentCharge]] - code - backend/modules/subscriptions/schemas.py
- [[RecurringExpenseItem]] - code - backend/modules/subscriptions/schemas.py
- [[ReviewCardResponse]] - code - backend/modules/merchant_review/schemas.py
- [[ReviewStatusResponse]] - code - backend/modules/merchant_review/schemas.py
- [[ReviewTransactionInfo]] - code - backend/modules/merchant_review/schemas.py
- [[SendWhatsAppPinRequest]] - code - backend/modules/auth/schemas.py
- [[SetAllocationRequest]] - code - backend/modules/budgets/schemas.py
- [[SetBudgetRequest]] - code - backend/modules/budgets/schemas.py
- [[SetCategoryBudgetRequest]] - code - backend/modules/budgets/schemas.py
- [[SettlementEnabledRequest]] - code - backend/modules/households/schemas.py
- [[SettlementResponse]] - code - backend/modules/households/schemas.py
- [[SettlementTransfer]] - code - backend/modules/households/schemas.py
- [[SplitRatioRequest]] - code - backend/modules/households/schemas.py
- [[SplitRatioResponse]] - code - backend/modules/households/schemas.py
- [[SplitTypeUpdateRequest]] - code - backend/modules/transactions/schemas.py
- [[StoreProviderTokensRequest]] - code - backend/modules/auth/schemas.py
- [[SubscriptionsResponse]] - code - backend/modules/subscriptions/schemas.py
- [[SubscriptionsSummary]] - code - backend/modules/subscriptions/schemas.py
- [[TransactionResponse]] - code - backend/modules/transactions/schemas.py
- [[UnreadCountResponse]] - code - backend/modules/notifications/schemas.py
- [[Update the current user's contribution mode in their active household.      The]] - rationale - backend/modules/households/router.py
- [[UpdateProfileRequest]] - code - backend/modules/auth/schemas.py
- [[UserCurrencyOut]] - code - backend/modules/currencies/schemas.py
- [[WhatsAppVerifyRequest]] - code - backend/modules/auth/schemas.py
- [[_serialize_fixed_contribution_amount()]] - code - backend/modules/auth/schemas.py
- [[check_sum()]] - code - backend/modules/budgets/schemas.py
- [[patch_contribution_settings()]] - code - backend/modules/households/router.py
- [[schemas.py]] - code - backend/modules/settings/schemas.py
- [[schemas.py_1]] - code - backend/modules/merchant_review/schemas.py
- [[schemas.py_2]] - code - backend/modules/currencies/schemas.py
- [[schemas.py_3]] - code - backend/modules/auth/schemas.py
- [[schemas.py_4]] - code - backend/modules/subscriptions/schemas.py
- [[schemas.py_5]] - code - backend/modules/transactions/schemas.py
- [[schemas.py_6]] - code - backend/modules/budgets/schemas.py
- [[schemas.py_7]] - code - backend/modules/households/schemas.py
- [[schemas.py_8]] - code - backend/modules/notifications/schemas.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Pydantic_Schemas
SORT file.name ASC
```

## Connections to other communities
- 30 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 7 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 6 edges to [[_COMMUNITY_Auth & Allocation Services]]
- 4 edges to [[_COMMUNITY_User Settings & Notifications]]
- 3 edges to [[_COMMUNITY_Plaid & Subscriptions]]
- 3 edges to [[_COMMUNITY_Cuotas (Installments)]]
- 2 edges to [[_COMMUNITY_Backend Core & Infra]]
- 2 edges to [[_COMMUNITY_User Budget Settings]]
- 1 edge to [[_COMMUNITY_Household Contributions]]

## Top bridge nodes
- [[BaseModel]] - degree 86, connects to 7 communities
- [[ContributionUpdateResponse]] - degree 14, connects to 2 communities
- [[ContributionUpdateRequest]] - degree 13, connects to 2 communities
- [[Partner clicks this link from their invite email to join the household.]] - degree 12, connects to 2 communities
- [[IMPORTANT settingscontribution must be defined BEFORE the {household_id}]] - degree 12, connects to 2 communities