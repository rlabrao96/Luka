---
type: community
cohesion: 0.50
members: 4
---

# Community 96

**Cohesion:** 0.50 - moderately connected
**Members:** 4 nodes

## Members
- [[018_account_balances.py]] - code - backend/alembic/versions/018_account_balances.py
- [[Add account_name, balance columns, and last_synced_at to bank_accounts.]] - rationale - backend/alembic/versions/018_account_balances.py
- [[downgrade()_30]] - code - backend/alembic/versions/018_account_balances.py
- [[upgrade()_30]] - code - backend/alembic/versions/018_account_balances.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_96
SORT file.name ASC
```
