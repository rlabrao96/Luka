---
type: community
cohesion: 0.15
members: 29
---

# Currencies Module

**Cohesion:** 0.15 - loosely connected
**Members:** 29 nodes

## Members
- [[Add a currency to the user's active list. Returns new row.]] - rationale - backend/modules/currencies/service.py
- [[Remove a currency. Promotes next if it was primary. Raises if it's the last.]] - rationale - backend/modules/currencies/service.py
- [[Return user's active currencies sorted by sort_order. Auto-seeds if empty.]] - rationale - backend/modules/currencies/service.py
- [[Sync user_currencies to match new preferred_currency.      Does NOT commit — the]] - rationale - backend/modules/currencies/service.py
- [[UserCurrency]] - code - backend/modules/currencies/models.py
- [[_exec_returning()]] - code - backend/tests/test_currencies_service.py
- [[_make_db()]] - code - backend/tests/test_currencies_service.py
- [[_make_uc()]] - code - backend/tests/test_currencies_service.py
- [[add_currency()]] - code - backend/modules/currencies/service.py
- [[add_currency()_1]] - code - backend/modules/currencies/router.py
- [[delete_currency()]] - code - backend/modules/currencies/service.py
- [[delete_currency()_1]] - code - backend/modules/currencies/router.py
- [[get_currencies()]] - code - backend/modules/currencies/service.py
- [[get_currencies()_1]] - code - backend/modules/currencies/router.py
- [[models.py_2]] - code - backend/modules/currencies/models.py
- [[router.py_2]] - code - backend/modules/currencies/router.py
- [[service.py_2]] - code - backend/modules/currencies/service.py
- [[sync_preferred_currency()]] - code - backend/modules/currencies/service.py
- [[test_add_currency_duplicate_raises()]] - code - backend/tests/test_currencies_service.py
- [[test_add_currency_happy_path()]] - code - backend/tests/test_currencies_service.py
- [[test_add_currency_invalid_code_raises()]] - code - backend/tests/test_currencies_service.py
- [[test_currencies_service.py]] - code - backend/tests/test_currencies_service.py
- [[test_delete_currency_last_one_raises()]] - code - backend/tests/test_currencies_service.py
- [[test_delete_currency_non_primary()]] - code - backend/tests/test_currencies_service.py
- [[test_delete_currency_primary_promotes_lowest_sort_order()]] - code - backend/tests/test_currencies_service.py
- [[test_get_currencies_auto_seeds_from_preferred_currency()]] - code - backend/tests/test_currencies_service.py
- [[test_get_currencies_returns_existing_sorted()]] - code - backend/tests/test_currencies_service.py
- [[test_sync_preferred_currency_sets_existing_row_as_primary()]] - code - backend/tests/test_currencies_service.py
- [[update_profile()]] - code - backend/modules/auth/router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Currencies_Module
SORT file.name ASC
```

## Connections to other communities
- 6 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 2 edges to [[_COMMUNITY_Backend Core & Infra]]

## Top bridge nodes
- [[UserCurrency]] - degree 10, connects to 1 community
- [[Return user's active currencies sorted by sort_order. Auto-seeds if empty.]] - degree 3, connects to 1 community
- [[Add a currency to the user's active list. Returns new row.]] - degree 3, connects to 1 community
- [[Remove a currency. Promotes next if it was primary. Raises if it's the last.]] - degree 3, connects to 1 community
- [[Sync user_currencies to match new preferred_currency.      Does NOT commit — the]] - degree 3, connects to 1 community