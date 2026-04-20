---
type: community
cohesion: 0.50
members: 4
---

# Community 86

**Cohesion:** 0.50 - moderately connected
**Members:** 4 nodes

## Members
- [[034_household_members_active_unique.py]] - code - backend/alembic/versions/034_household_members_active_unique.py
- [[Enforce at most one active household membership per user  Context A manual SQL]] - rationale - backend/alembic/versions/034_household_members_active_unique.py
- [[downgrade()_20]] - code - backend/alembic/versions/034_household_members_active_unique.py
- [[upgrade()_20]] - code - backend/alembic/versions/034_household_members_active_unique.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_86
SORT file.name ASC
```
