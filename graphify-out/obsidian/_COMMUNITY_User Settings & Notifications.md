---
type: community
cohesion: 0.07
members: 53
---

# User Settings & Notifications

**Cohesion:** 0.07 - loosely connected
**Members:** 53 nodes

## Members
- [[Adding a category that already exists raises ValueError.]] - rationale - backend/tests/test_categories_service.py
- [[Adding when 19 already exist raises ValueError.]] - rationale - backend/tests/test_categories_service.py
- [[Build a mock db.execute() return that supports .scalars().all() or .scalar()]] - rationale - backend/tests/test_categories_service.py
- [[CategoryPreferencesResponse]] - code - backend/modules/settings/schemas.py
- [[CategoryUsageResponse]] - code - backend/modules/settings/schemas.py
- [[Deletes preference row and merchant selections without updating transactions.]] - rationale - backend/tests/test_categories_service.py
- [[Emptywhitespace name raises ValueError.]] - rationale - backend/tests/test_categories_service.py
- [[Expense categories appear before income in the returned list.]] - rationale - backend/tests/test_categories_service.py
- [[NotificationPreference]] - code - backend/modules/settings/models.py
- [[Returns count of TransactionSplit rows with matching category.]] - rationale - backend/tests/test_categories_service.py
- [[Submitted set that differs from existing raises ValueError.]] - rationale - backend/tests/test_categories_service.py
- [[Updates transactions + splits, deletes merchant selections, deletes preference.]] - rationale - backend/tests/test_categories_service.py
- [[User with no rows gets default 22 categories seeded.]] - rationale - backend/tests/test_categories_service.py
- [[UserCategoryPreference]] - code - backend/modules/settings/models.py
- [[Valid new category is inserted with is_custom=True.]] - rationale - backend/tests/test_categories_service.py
- [[Valid reorder updates sort_order on existing rows.]] - rationale - backend/tests/test_categories_service.py
- [[_execute_returning()]] - code - backend/tests/test_categories_service.py
- [[_make_pref()]] - code - backend/tests/test_categories_service.py
- [[_mock_db()]] - code - backend/tests/test_categories_service.py
- [[_pref_to_dict()]] - code - backend/modules/settings/service.py
- [[add_category()]] - code - backend/modules/settings/service.py
- [[add_category_preference()]] - code - backend/modules/settings/router.py
- [[delete_account()]] - code - backend/modules/auth/router.py
- [[delete_category()]] - code - backend/modules/settings/service.py
- [[delete_category_preference()]] - code - backend/modules/settings/router.py
- [[delete_user_account()]] - code - backend/modules/settings/service.py
- [[get_category_preferences()]] - code - backend/modules/settings/service.py
- [[get_category_preferences()_1]] - code - backend/modules/settings/router.py
- [[get_category_usage()]] - code - backend/modules/settings/service.py
- [[get_category_usage()_1]] - code - backend/modules/settings/router.py
- [[get_notification_preferences()]] - code - backend/modules/settings/service.py
- [[get_notification_preferences()_1]] - code - backend/modules/settings/router.py
- [[models.py]] - code - backend/modules/settings/models.py
- [[reclassify_to that doesn't exist in user's preferences raises ValueError.]] - rationale - backend/tests/test_categories_service.py
- [[reorder_categories()]] - code - backend/modules/settings/service.py
- [[reorder_category_preferences()]] - code - backend/modules/settings/router.py
- [[router.py]] - code - backend/modules/settings/router.py
- [[service.py]] - code - backend/modules/settings/service.py
- [[test_add_category_at_limit_raises()]] - code - backend/tests/test_categories_service.py
- [[test_add_category_duplicate_raises()]] - code - backend/tests/test_categories_service.py
- [[test_add_category_empty_name_raises()]] - code - backend/tests/test_categories_service.py
- [[test_add_category_happy_path()]] - code - backend/tests/test_categories_service.py
- [[test_categories_service.py]] - code - backend/tests/test_categories_service.py
- [[test_delete_category_invalid_reclassify_to_raises()]] - code - backend/tests/test_categories_service.py
- [[test_delete_category_no_reclassify()]] - code - backend/tests/test_categories_service.py
- [[test_delete_category_with_reclassify()]] - code - backend/tests/test_categories_service.py
- [[test_get_category_preferences_expense_before_income()]] - code - backend/tests/test_categories_service.py
- [[test_get_category_preferences_seeds_when_empty()]] - code - backend/tests/test_categories_service.py
- [[test_get_category_usage_returns_count()]] - code - backend/tests/test_categories_service.py
- [[test_reorder_categories_mismatch_raises()]] - code - backend/tests/test_categories_service.py
- [[test_reorder_categories_valid()]] - code - backend/tests/test_categories_service.py
- [[update_notification_preferences()]] - code - backend/modules/settings/service.py
- [[update_notification_preferences()_1]] - code - backend/modules/settings/router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/User_Settings_&_Notifications
SORT file.name ASC
```

## Connections to other communities
- 4 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 4 edges to [[_COMMUNITY_Pydantic Schemas]]
- 3 edges to [[_COMMUNITY_Merchants & WhatsApp]]
- 1 edge to [[_COMMUNITY_Backend Core & Infra]]

## Top bridge nodes
- [[UserCategoryPreference]] - degree 8, connects to 2 communities
- [[NotificationPreference]] - degree 4, connects to 1 community
- [[CategoryPreferencesResponse]] - degree 4, connects to 1 community
- [[CategoryUsageResponse]] - degree 3, connects to 1 community
- [[delete_account()]] - degree 2, connects to 1 community