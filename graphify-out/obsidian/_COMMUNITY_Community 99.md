---
type: community
cohesion: 0.50
members: 4
---

# Community 99

**Cohesion:** 0.50 - moderately connected
**Members:** 4 nodes

## Members
- [[020_transaction_source_bank_name.py]] - code - backend/alembic/versions/020_transaction_source_bank_name.py
- [[Add source_bank_name to transactions for email-inferred bank identification.]] - rationale - backend/alembic/versions/020_transaction_source_bank_name.py
- [[downgrade()_34]] - code - backend/alembic/versions/020_transaction_source_bank_name.py
- [[upgrade()_34]] - code - backend/alembic/versions/020_transaction_source_bank_name.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_99
SORT file.name ASC
```
