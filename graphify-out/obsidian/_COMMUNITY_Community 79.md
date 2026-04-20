---
type: community
cohesion: 0.50
members: 4
---

# Community 79

**Cohesion:** 0.50 - moderately connected
**Members:** 4 nodes

## Members
- [[019_household_split_ratio.py]] - code - backend/alembic/versions/019_household_split_ratio.py
- [[Add split_ratio JSONB column to households.]] - rationale - backend/alembic/versions/019_household_split_ratio.py
- [[downgrade()_12]] - code - backend/alembic/versions/019_household_split_ratio.py
- [[upgrade()_12]] - code - backend/alembic/versions/019_household_split_ratio.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_79
SORT file.name ASC
```
