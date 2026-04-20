---
type: community
cohesion: 0.03
members: 121
---

# Plaid & Subscriptions

**Cohesion:** 0.03 - loosely connected
**Members:** 121 nodes

## Members
- [[.test_accepts_optional_split_type_personal()]] - code - backend/tests/test_subscription_reclassify.py
- [[.test_accepts_optional_split_type_shared()]] - code - backend/tests/test_subscription_reclassify.py
- [[.test_rejects_invalid_split_type()]] - code - backend/tests/test_subscription_reclassify.py
- [[.test_split_type_defaults_to_none()]] - code - backend/tests/test_subscription_reclassify.py
- [[5 months of Netflix txns; reclassify; verify only last 3 months'         transac]] - rationale - backend/tests/test_subscription_reclassify.py
- [[A subscription tagged split_type='personal' must NOT count toward         househ]] - rationale - backend/tests/test_subscription_reclassify.py
- [[Amounts within 20% are accepted; beyond 20% rejected.]] - rationale - backend/tests/test_subscriptions.py
- [[Apply enrichment from email tx to bank tx, re-link splits, delete email txs.]] - rationale - backend/modules/reconciliation/dedup.py
- [[Apply subscription_overrides on top of raw detected items.]] - rationale - backend/modules/subscriptions/service.py
- [[Check if Plaid transaction is an internal transfer (not person-to-person).]] - rationale - backend/modules/plaid/mapper.py
- [[Check if all amounts are within tolerance of the median.]] - rationale - backend/modules/subscriptions/service.py
- [[Check if transaction is a credit card bill payment.]] - rationale - backend/modules/plaid/mapper.py
- [[Compute SubscriptionsSummary per currency.]] - rationale - backend/modules/subscriptions/service.py
- [[Create or update a subscription override.]] - rationale - backend/modules/subscriptions/service.py
- [[Createupdate bank_accounts from Plaid accounts. Returns {plaid_account_id bank]] - rationale - backend/modules/plaid/sync.py
- [[Each detected subscription includes the currency from the latest transaction.]] - rationale - backend/tests/test_subscriptions.py
- [[Extract enrichment data from an email transaction.]] - rationale - backend/modules/reconciliation/dedup.py
- [[Extract person name from Zelle transaction descriptions.]] - rationale - backend/modules/plaid/mapper.py
- [[Find N email transactions from same merchant whose sum matches the bank amount.]] - rationale - backend/modules/reconciliation/dedup.py
- [[Find a single email transaction matching by merchant, date window, and amount to]] - rationale - backend/modules/reconciliation/dedup.py
- [[Find matching email transaction(s) using 3-tier priority.      Returns dict with]] - rationale - backend/modules/reconciliation/dedup.py
- [[Force recompute and return fresh data.]] - rationale - backend/modules/subscriptions/service.py
- [[Household-scoped and personal-scoped `known_bills` readers for the budget endpoi]] - rationale - backend/modules/subscriptions/read.py
- [[Jan 31 - Feb 28 (2026 is not a leap year).]] - rationale - backend/tests/test_subscriptions.py
- [[Map a Plaid transaction object to a Luka transaction dict.      Sign convention]] - rationale - backend/modules/plaid/mapper.py
- [[Merchant appearing in 2+ consecutive months is detected.]] - rationale - backend/tests/test_subscriptions.py
- [[Merchant appearing in non-consecutive months is NOT detected.]] - rationale - backend/tests/test_subscriptions.py
- [[PUT subscriptionsoverride with a split_type field routes the         request t]] - rationale - backend/tests/test_subscription_reclassify.py
- [[PUT subscriptionsoverride without split_type should still work         (legacy]] - rationale - backend/tests/test_subscription_reclassify.py
- [[Plaid transaction sync fetches transactions via cursor, creates accounts, maps]] - rationale - backend/modules/plaid/sync.py
- [[Project day-of-month to next calendar month, clamping to month end.]] - rationale - backend/modules/subscriptions/service.py
- [[Pure function given transaction rows, detect recurring patterns.]] - rationale - backend/modules/subscriptions/service.py
- [[Read from DB cache, compute on first access. Merge overrides at read time.]] - rationale - backend/modules/subscriptions/service.py
- [[Recent charges returns last 3 transactions sorted newest first.]] - rationale - backend/tests/test_subscriptions.py
- [[Reclassify a subscription's split_type and cascade the change to the     last `w]] - rationale - backend/modules/subscriptions/service.py
- [[Regression test for the Task 6 reimbursement asymmetry bug         a reimbursem]] - rationale - backend/tests/test_subscription_reclassify.py
- [[Returns length of longest consecutive run from the most recent month backwards.]] - rationale - backend/modules/subscriptions/service.py
- [[Run a full sync for a Plaid item. Returns stats dict.]] - rationale - backend/modules/plaid/sync.py
- [[Shared email dedup-and-enrich logic for both Plaid and luka-connect sync.  When]] - rationale - backend/modules/reconciliation/dedup.py
- [[SubscriptionOverrideRequest]] - code - backend/modules/subscriptions/schemas.py
- [[Sum of household SHARED recurring bills across every active member     in `curre]] - rationale - backend/modules/subscriptions/read.py
- [[Sum of one user's recurring bills that are PERSONAL (not shared with     the hou]] - rationale - backend/modules/subscriptions/read.py
- [[Sum of one user's recurring bills that are SHARED with the household.     Used b]] - rationale - backend/modules/subscriptions/read.py
- [[Sum recurring bills for one user in `currency` where the effective     split_typ]] - rationale - backend/modules/subscriptions/read.py
- [[Sum the monthly total of ALL detected recurring bills for one user in     `curre]] - rationale - backend/modules/subscriptions/read.py
- [[TestClassifyEndpoint]] - code - backend/tests/test_subscription_reclassify.py
- [[TestKnownBillsFiltering]] - code - backend/tests/test_subscription_reclassify.py
- [[TestOverrideWinsOverInferredSplitType]] - code - backend/tests/test_subscription_reclassify.py
- [[TestReclassifySubscriptionSplit]] - code - backend/tests/test_subscription_reclassify.py
- [[TestSubscriptionOverrideRequestSchema]] - code - backend/tests/test_subscription_reclassify.py
- [[TestUpsertOverrideSplitType]] - code - backend/tests/test_subscription_reclassify.py
- [[Tests for subscription split_type classification and cascade behavior.]] - rationale - backend/tests/test_subscription_reclassify.py
- [[TransactionSplit]] - code - backend/modules/transactions/models.py
- [[Txns with no existing transaction_splits row get one inserted.]] - rationale - backend/tests/test_subscription_reclassify.py
- [[When both an inferred split_type (from transaction_splits) and an         overri]] - rationale - backend/tests/test_subscription_reclassify.py
- [[When no override exists, the inferred split_type from         transaction_splits]] - rationale - backend/tests/test_subscription_reclassify.py
- [[__init__.py_11]] - code - backend/modules/subscriptions/__init__.py
- [[_are_consecutive()]] - code - backend/modules/subscriptions/service.py
- [[_compute_summary_by_currency()]] - code - backend/modules/subscriptions/service.py
- [[_extract_enrichment()]] - code - backend/modules/reconciliation/dedup.py
- [[_extract_zelle_person()]] - code - backend/modules/plaid/mapper.py
- [[_find_single_match()]] - code - backend/modules/reconciliation/dedup.py
- [[_find_sum_match()]] - code - backend/modules/reconciliation/dedup.py
- [[_get_seed_household_id()_2]] - code - backend/tests/test_subscription_reclassify.py
- [[_get_seed_user()_2]] - code - backend/tests/test_subscription_reclassify.py
- [[_is_cc_payment()]] - code - backend/modules/plaid/mapper.py
- [[_merge_overrides()]] - code - backend/modules/subscriptions/service.py
- [[_sum_user_bills_by_split_type()]] - code - backend/modules/subscriptions/read.py
- [[_within_tolerance()]] - code - backend/modules/subscriptions/service.py
- [[apply_match_and_delete_emails()]] - code - backend/modules/reconciliation/dedup.py
- [[dedup.py]] - code - backend/modules/reconciliation/dedup.py
- [[detect_from_rows()]] - code - backend/modules/subscriptions/service.py
- [[detected_subscriptions()]] - code - backend/modules/subscriptions/router.py
- [[ensure_plaid_accounts()]] - code - backend/modules/plaid/sync.py
- [[find_email_match()]] - code - backend/modules/reconciliation/dedup.py
- [[get_detected_subscriptions()]] - code - backend/modules/subscriptions/service.py
- [[get_household_known_bills()]] - code - backend/modules/subscriptions/read.py
- [[get_user_known_bills()]] - code - backend/modules/subscriptions/read.py
- [[get_user_personal_known_bills()]] - code - backend/modules/subscriptions/read.py
- [[get_user_shared_known_bills()]] - code - backend/modules/subscriptions/read.py
- [[is_plaid_transfer()]] - code - backend/modules/plaid/mapper.py
- [[map_account_kind()]] - code - backend/modules/plaid/mapper.py
- [[map_plaid_transaction()]] - code - backend/modules/plaid/mapper.py
- [[mapper.py_1]] - code - backend/modules/plaid/mapper.py
- [[predict_next_date()]] - code - backend/modules/subscriptions/service.py
- [[read.py]] - code - backend/modules/subscriptions/read.py
- [[reclassify_subscription_split()]] - code - backend/modules/subscriptions/service.py
- [[refresh_subscriptions()]] - code - backend/modules/subscriptions/service.py
- [[refresh_subscriptions()_1]] - code - backend/modules/subscriptions/router.py
- [[router.py_5]] - code - backend/modules/subscriptions/router.py
- [[run_plaid_sync()]] - code - backend/modules/plaid/sync.py
- [[service.py_3]] - code - backend/modules/subscriptions/service.py
- [[sync.py]] - code - backend/modules/plaid/sync.py
- [[test_cascade_inserts_missing_splits()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_cascade_invalidates_cache()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_cascade_persists_override_row()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_cascade_updates_last_3_months_only()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_detect_from_rows_amount_tolerance()]] - code - backend/tests/test_subscriptions.py
- [[test_detect_from_rows_finds_recurring()]] - code - backend/tests/test_subscriptions.py
- [[test_detect_from_rows_includes_currency()]] - code - backend/tests/test_subscriptions.py
- [[test_detect_from_rows_recent_charges()]] - code - backend/tests/test_subscriptions.py
- [[test_detect_from_rows_skips_non_consecutive()]] - code - backend/tests/test_subscriptions.py
- [[test_get_household_known_bills_sums_across_members()]] - code - backend/tests/test_subscriptions_read.py
- [[test_get_user_known_bills_returns_zero_on_missing_currency()]] - code - backend/tests/test_subscriptions_read.py
- [[test_household_known_bills_excludes_personal_subs()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_no_override_falls_back_to_inferred()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_override_split_type_wins_over_inferred()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_predict_next_date_month_end()]] - code - backend/tests/test_subscriptions.py
- [[test_predict_next_date_normal()]] - code - backend/tests/test_subscriptions.py
- [[test_put_override_with_split_type_cascades()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_put_override_without_split_type_uses_legacy_upsert_path()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_reimbursement_member_personal_bill_does_not_under_count_household()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_rejects_invalid_split_type()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_subscription_reclassify.py]] - code - backend/tests/test_subscription_reclassify.py
- [[test_subscriptions.py]] - code - backend/tests/test_subscriptions.py
- [[test_subscriptions_read.py]] - code - backend/tests/test_subscriptions_read.py
- [[test_upsert_persists_split_type()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_upsert_update_changes_split_type()]] - code - backend/tests/test_subscription_reclassify.py
- [[test_upsert_without_split_type_leaves_existing()]] - code - backend/tests/test_subscription_reclassify.py
- [[upsert_override()]] - code - backend/modules/subscriptions/service.py
- [[upsert_override()_1]] - code - backend/modules/subscriptions/router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Plaid_&_Subscriptions
SORT file.name ASC
```

## Connections to other communities
- 80 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 42 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 13 edges to [[_COMMUNITY_Backend Core & Infra]]
- 3 edges to [[_COMMUNITY_Pydantic Schemas]]
- 3 edges to [[_COMMUNITY_Budgets (v2 v3)]]
- 1 edge to [[_COMMUNITY_Transactions API]]
- 1 edge to [[_COMMUNITY_Merchants & WhatsApp]]

## Top bridge nodes
- [[TransactionSplit]] - degree 87, connects to 5 communities
- [[run_plaid_sync()]] - degree 12, connects to 3 communities
- [[service.py_3]] - degree 12, connects to 2 communities
- [[get_detected_subscriptions()]] - degree 12, connects to 2 communities
- [[detect_from_rows()]] - degree 11, connects to 2 communities