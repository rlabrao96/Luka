---
type: community
cohesion: 0.07
members: 36
---

# Transactions API

**Cohesion:** 0.07 - loosely connected
**Members:** 36 nodes

## Members
- [[Can delete a pending email transaction.]] - rationale - backend/tests/test_delete_transaction.py
- [[Cannot delete a connect-sourced (scraped) transaction.]] - rationale - backend/tests/test_delete_transaction.py
- [[Email transaction with no prior connect sync → awaiting_reconciliation.]] - rationale - backend/tests/test_pending_transactions.py
- [[No matching transaction → not a duplicate.]] - rationale - backend/tests/test_cross_sender_dedup.py
- [[No pending transactions → all 3 lists empty.]] - rationale - backend/tests/test_pending_transactions.py
- [[Same amount + within 5 minutes of created_at → duplicate.]] - rationale - backend/tests/test_cross_sender_dedup.py
- [[Transaction not found returns not_found.]] - rationale - backend/tests/test_delete_transaction.py
- [[_default_since()]] - code - backend/modules/transactions/router.py
- [[_txn_to_dict()]] - code - backend/modules/transactions/service.py
- [[delete_transaction()]] - code - backend/modules/transactions/service.py
- [[delete_transaction()_1]] - code - backend/modules/transactions/router.py
- [[get_monthly_summary()]] - code - backend/modules/transactions/service.py
- [[get_my_transactions()]] - code - backend/modules/transactions/service.py
- [[get_pending_transactions()]] - code - backend/modules/transactions/service.py
- [[get_shared_transactions()]] - code - backend/modules/transactions/service.py
- [[is_duplicate_transaction()]] - code - backend/modules/transactions/service.py
- [[monthly_summary()]] - code - backend/modules/transactions/router.py
- [[my_transactions()]] - code - backend/modules/transactions/router.py
- [[pending_transactions()]] - code - backend/modules/transactions/router.py
- [[router.py_6]] - code - backend/modules/transactions/router.py
- [[service.py_5]] - code - backend/modules/transactions/service.py
- [[shared_transactions()]] - code - backend/modules/transactions/router.py
- [[test_cross_sender_dedup.py]] - code - backend/tests/test_cross_sender_dedup.py
- [[test_delete_pending_email_transaction()]] - code - backend/tests/test_delete_transaction.py
- [[test_delete_rejects_connect_transaction()]] - code - backend/tests/test_delete_transaction.py
- [[test_delete_returns_not_found()]] - code - backend/tests/test_delete_transaction.py
- [[test_delete_transaction.py]] - code - backend/tests/test_delete_transaction.py
- [[test_detects_duplicate_within_5_minutes()]] - code - backend/tests/test_cross_sender_dedup.py
- [[test_email_txn_before_sync_is_awaiting()]] - code - backend/tests/test_pending_transactions.py
- [[test_no_duplicate_when_none_found()]] - code - backend/tests/test_cross_sender_dedup.py
- [[test_pending_returns_empty_when_no_pending()]] - code - backend/tests/test_pending_transactions.py
- [[test_pending_transactions.py]] - code - backend/tests/test_pending_transactions.py
- [[update_category()]] - code - backend/modules/transactions/service.py
- [[update_category()_1]] - code - backend/modules/transactions/router.py
- [[update_split_type()]] - code - backend/modules/transactions/service.py
- [[update_split_type()_1]] - code - backend/modules/transactions/router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Transactions_API
SORT file.name ASC
```

## Connections to other communities
- 6 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 2 edges to [[_COMMUNITY_Backend Core & Infra]]
- 2 edges to [[_COMMUNITY_Auth & Allocation Services]]
- 1 edge to [[_COMMUNITY_Merchants & WhatsApp]]
- 1 edge to [[_COMMUNITY_Plaid & Subscriptions]]

## Top bridge nodes
- [[update_category()]] - degree 4, connects to 3 communities
- [[is_duplicate_transaction()]] - degree 5, connects to 2 communities
- [[update_split_type()]] - degree 3, connects to 2 communities
- [[get_pending_transactions()]] - degree 5, connects to 1 community
- [[shared_transactions()]] - degree 4, connects to 1 community