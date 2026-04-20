---
type: community
cohesion: 0.50
members: 4
---

# Community 72

**Cohesion:** 0.50 - moderately connected
**Members:** 4 nodes

## Members
- [[017_remove_fintoc_add_bank_connect.py]] - code - backend/alembic/versions/017_remove_fintoc_add_bank_connect.py
- [[Remove Fintoc columns, add bank_credentials table and source_type.  Revision ID]] - rationale - backend/alembic/versions/017_remove_fintoc_add_bank_connect.py
- [[downgrade()_5]] - code - backend/alembic/versions/017_remove_fintoc_add_bank_connect.py
- [[upgrade()_5]] - code - backend/alembic/versions/017_remove_fintoc_add_bank_connect.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_72
SORT file.name ASC
```
