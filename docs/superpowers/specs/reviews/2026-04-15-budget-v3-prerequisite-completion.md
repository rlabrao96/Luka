# Budget v3 Prerequisite — Plan 1 Completion Checkpoint

**Date:** 2026-04-15
**Plan:** docs/superpowers/plans/2026-04-15-budget-v3-subscription-classification-plan.md
**Status:** Complete and merged to main

## Final Test Counts

- Backend: 359 passed, 11 skipped, 3 warnings in 295.11s (0:04:55)
- Frontend: clean build, zero TypeScript errors

## Tasks Completed

- Task 1 (`625424e`) — Migration 036: subscription_overrides.split_type column + CHECK constraint
- Task 2 (`e99349b`) — SubscriptionOverrideRequest pydantic schema field
- Task 3 (`693e483`) — upsert_override extended to persist split_type
- Task 4 (`c41736c`) — reclassify_subscription_split service with 3-month cascade
- Task 5 (`11a6423`) — _merge_overrides applies override split_type
- Task 6 (`df049ac`) — read.py filters by effective split_type (get_household_known_bills, new get_user_personal_known_bills)
- Task 6.5 hot-fix (`a9b0c37`) — symmetric reimbursement subtraction (closes asymmetry introduced by Task 6's filter)
- Task 7 (`61f52c1`) — Router PUT /subscriptions/override routes split_type through reclassify
- Task 8 (`2ad43f9`, fix `959fa78`) — Frontend useSubscriptionOverride accepts split_type, optimistic update, budget-v2 invalidation
- Task 9 (`89a5647`, fix `4418e83`) — Subscriptions page Clasificación column with click-to-flip pill

## Merge Gate for Plan 2

The v3 Sankey redesign plan (`docs/superpowers/plans/2026-04-15-budget-v3-sankey-redesign-plan.md`) depends on:
- get_household_known_bills filtering by effective split_type='shared' (Task 6 + 6.5)
- get_user_personal_known_bills (Task 6) for the v3 personal Sankey
- Subscription classification toggle UI (Task 9) for users to clean up their data before the v3 ship

This prerequisite plan is now ready. Plan 2 may start.

## Known Follow-up Items (deferred from review notes)

These were caught by code-quality reviewers during the plan but explicitly deferred to keep velocity:

1. **Migration constraint naming inconsistency** (Task 1 review): `ck_subscription_overrides_split_type` (plural) vs the existing `ck_subscription_override_status` / `_day` (singular) on the same table. Cosmetic; consider a follow-up migration that renames the older two for consistency, or accept the new plural form as canonical going forward.

2. **Race condition on concurrent reclassify cascade** (Task 4 review): the per-tx UPDATE-then-INSERT loop can create duplicate `transaction_splits` rows if two requests race for a tx that has no existing split row. Schema doesn't enforce uniqueness on `transaction_splits.transaction_id`. Recommended fix: add a UNIQUE constraint migration on `transaction_splits.transaction_id` and convert the loop to `INSERT ... ON CONFLICT (transaction_id) DO UPDATE`. Also benefits 4 other insertion sites in the codebase.

3. **Test fixture model registration gap** (Task 4 review): 3 noqa F401 imports added to `test_subscription_reclassify.py` to register FK targets in SQLAlchemy metadata. Same pattern exists in `main.py`, `alembic/env.py`, and `tests/conftest.py:71`. The right fix is a central `backend/modules/__init__.py` (or similar) that imports all models once. Tech debt that's been accumulating.

4. **31-day test spacing in Task 4** uses day-arithmetic instead of `dateutil.relativedelta(months=N)`. Works correctly with an inline comment, but `relativedelta` would be more idiomatic. Trivial cleanup.

5. **Task 5 helper duplication**: `_get_seed_user` and `_get_seed_household_id` are now in 4+ test files with slight naming variations. A shared `backend/tests/helpers/seed.py` would consolidate them. Tracked in the Task 3 and Task 5 review notes.

6. **v2 personal Sankey double-counts shared bills** (Task 6 review, pre-existing bug): line 553 of v2_service.py calls `get_user_known_bills` (all bills) for the personal view. The v3 personal Sankey will use `get_user_personal_known_bills` instead, which fixes this — so the bug ages out when v3 ships. No standalone fix needed.

## Frontend UAT Limitation

Manual browser-based UAT is blocked by Google OAuth's automation-detection (chrome-devtools-mcp and browser-use can't sign into Luka). The pill UI was verified via:
- TypeScript build pass (`npm run build` clean after each task)
- Code-quality review of the rendering logic and state management
- Backend integration tests covering the full PUT /subscriptions/override → reclassify cascade → cache invalidation flow

This constraint is documented in the 2026-04-14 sprint Day-4 integration report and applies to the v3 work going forward.
