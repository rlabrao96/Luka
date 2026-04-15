# Budget v3 Sankey Redesign — Plan 2 Completion Checkpoint

**Date:** 2026-04-15
**Plan:** docs/superpowers/plans/2026-04-15-budget-v3-sankey-redesign-plan.md
**Status:** Complete and merged to main
**Builds on:** docs/superpowers/specs/reviews/2026-04-15-budget-v3-prerequisite-completion.md (Plan 1)

## Final Test Counts

- Backend: `401 passed, 11 skipped, 3 warnings in 410.83s (0:06:50)`
- Frontend: clean `npm run build`, zero TypeScript errors, 19 routes generated

## Tasks Completed

- Task 1 (`301819a`) — Migration 037: user_budget_settings.personal_allocation_amount + currency columns
- Task 2 (`5d571a2` + docstring fix `651c380`) — get_personal_allocation + get_household_personal_allocation helpers + ORM Mapped columns
- Task 3 (`368512e` + privacy test fix `44de218`) — HouseholdIncomeBreakdown dataclass + caller-relative income_breakdown_for_household_view
- Task 4 (`1319f52`) — spendable_ceiling extended with personal_allocation kwarg
- Task 5 (`213a798`) — Additive level/kind/member_id fields on SankeyNode
- Task 6 (`afc7329`) — Extracted _pay_first_fit module-level routing helper
- Task 7 (`6ca4a4e`) — _build_hogar_sankey 4-level builder
- Task 8 (`43518f1` + cleanup `5c64adb`) — _build_personal_sankey 3-level builder with hub
- Task 9 (`3641deb`) — Wired hogar/personal builders into get_budget_v2; deleted legacy _build_sankey
- Task 10 (`daf37f0`) — End-to-end privacy regression matrix + flow conservation across 6 seed/view combos
- Task 11 (`c6b1237` + fixes `cba520d`) — BudgetSettingsSection personal allocation input + backend write path
- Task 12 (`6b4b400` + hub label fix `f75458c`) — BudgetSankey rank-based label renderer with v2 fallback
- Task 13 (`fe15e3a`) — budgets/page.tsx container sizing for 4-level layout
- Task 14 (this commit) — Integration verification + completion checkpoint + fix: forward v3 node fields (level/kind/member_id) from api.ts + page.tsx to BudgetSankey renderer

## Spec Sections Delivered

- §2.1 Hogar 4-level structure: sources → ingresos_hogar hub → 5 allocation nodes → disponible breakdown ✓
- §2.2 Personal 3-level structure with hub: sources → ingresos_personales → 3 allocation nodes → disponible_personal breakdown ✓
- §2.3 Flow conservation invariant: enforced by the new builders + verified by TestFlowConservationAllSeeds matrix ✓
- §3.1 Migration 037 + ORM columns ✓
- §3.3 Additive SankeyNode fields (level, kind, member_id) ✓
- §4 Caller-relative privacy model + HouseholdIncomeBreakdown + recursive-walk regression ✓
- §5 Forecast engine extended with personal_allocation outflow ✓

## Code-Level UX Audit

**(i) Level 0 sources — caller's income categories ordered by sort_order:**
Confirmed. `get_budget_v2` queries `user_category_preferences WHERE category_type='income' ORDER BY sort_order` into `income_category_order`, and both `_build_hogar_sankey` and `_build_personal_sankey` iterate that list (not a dict) when emitting Level 0 source nodes, preserving the user-configured sort order exactly.

**(ii) `Gastos fijos` as a direct Level 2 child of `Ingresos Hogar`:**
Confirmed. In `_build_hogar_sankey`, `gastos_fijos` is appended at `level=2, kind="allocation"` and the link `ingresos_hogar → gastos_fijos` is emitted at the Level 1→2 stage. The Level 3 breakdown nodes only flow from `disponible_hogar`, so fixed bills are never mixed with discretionary spending.

**(iii) `Gasto personal` node appears only when `personal_allocation_amount > 0`:**
Confirmed. The node is guarded by `if personal_allocation > _ZERO:` and the `_emit` helper skips zero-value links, so neither a node nor a link is created when the caller has not configured a personal allocation amount.

**(iv) Per-member aggregated nodes render with display name in tooltips:**
Confirmed. Each `OtherMemberContribution` produces a node whose `label` is either `"Contribución fija {display_name}"` (fixed mode) or `"Ingresos {display_name}"` (full mode), set from `users.full_name` via the SQL join. The `BudgetSankey.tsx` tooltip formatter reads `payload?.label` to render this display name. The v3 fields (`level`, `kind`, `member_id`) were not being forwarded through `BudgetV2SankeyNode` (api.ts) or the `page.tsx` node map — this was caught during audit and fixed in this task: `api.ts` type extended and `page.tsx` map updated to pass through all three fields, activating the rank-based label renderer.

**(v) Privacy invariant — fixed member's real income never appears in JSON:**
Confirmed by code and test. `income_breakdown_for_household_view` gates the per-member loop on `contribution_mode` before any transaction read: the `fixed` branch only reads `fixed_contribution_amount`; it never calls `income_for_personal_view`. The recursive-walk regression test `test_hogar_fixed_privacy_recursive_walk` serializes the full `/budgets/v2` JSON and asserts the real income amount does not appear anywhere in the response, including nested strings.

**(vi) Flow conservation holds for all seeded households + currencies:**
Confirmed by `TestFlowConservationAllSeeds` parametrized matrix (6 combos: 4 households × household/personal view × CLP/USD filtered to combinations that have data). For every combo, the test asserts that the sum of source node values equals the sum of all outgoing links from each non-source node, and that hub inflow equals hub outflow. All 6 parametrized cases pass in the 401-test suite.

## Frontend UAT Limitation

Manual browser-based UAT remains blocked by Google OAuth's automation-detection (chrome-devtools-mcp + browser-use can't sign into Luka). The v3 Sankey was verified via:
- TypeScript build pass after every frontend task
- Code-level audit of the rendering logic, level dispatch, and tooltip changes
- Backend integration tests covering the full /budgets/v2 endpoint with all 4 seeded households + privacy invariants
- Fix applied in Task 14: `BudgetV2SankeyNode` type and `page.tsx` node map now forward `level`, `kind`, `member_id` so the v3 rank-based renderer is actually activated at runtime

## Known Follow-up Items (carried from Plan 1 + new from Plan 2)

These were caught during reviews but explicitly deferred to keep velocity:

### From Plan 1 (still open)
1. Migration constraint naming inconsistency on `subscription_overrides` (plural vs singular prefix on the same table) — cosmetic
2. Race condition in `reclassify_subscription_split` cascade (no UNIQUE constraint on `transaction_splits.transaction_id`) — needs a dedicated migration
3. Test fixture model registration via noqa F401 imports — would benefit from a central `modules/__init__.py` register-all
4. 31-day test spacing in cascade tests (use `relativedelta` instead) — trivial cleanup
5. Helper duplication across test files (`_get_seed_user`, `_get_seed_household_id`) — extract to `backend/tests/helpers/seed.py`
6. v2 personal Sankey shared-bills double-count — pre-existing bug; ages out when v3 personal view adoption is confirmed

### From Plan 2 (new)
7. **Plan 2 Task 7/8 review nits**: `inc_*` dead variables in builders were cleaned up at `5c64adb`; reviewer also flagged repetitive allocation-node `if` blocks (could be DRY'd via list-of-tuples loop) and a missing `otras_fuentes` synthetic-source test — both deferred as polish
8. **Plan 2 Task 9 review nit**: `get_budget_v2` grew significantly with the inline personal-view bucketing logic. Could be extracted to a private helper if the function gets more complex in the future
9. **Plan 2 Task 11 review nit**: `update_personal_allocation` and `update_savings_target` could share a single `update_user_budget_settings_field` helper to remove the parallel-implementation tax — minor refactor opportunity
10. **Task 14 audit fix**: `BudgetV2SankeyNode` in `api.ts` and the `page.tsx` node map were not forwarding the v3 fields (`level`, `kind`, `member_id`), causing the rank-based label renderer to silently fall back to the v2 heuristic for all nodes. Fixed in this task — but browser UAT is still needed to confirm the 4-level visual layout renders correctly end-to-end.

## Merge Gate

This is the FINAL plan in the budget-v3 redesign. After this completion checkpoint, no further dependencies. The frontend visual UAT remains a known limitation (documented above) and any visual issues found during normal use can be filed as bugs rather than blocking the redesign release.

## Related Documents

- Spec: `docs/superpowers/specs/2026-04-15-budget-v3-sankey-redesign-design.md`
- Plan 2: `docs/superpowers/plans/2026-04-15-budget-v3-sankey-redesign-plan.md`
- Plan 1 (prerequisite): `docs/superpowers/plans/2026-04-15-budget-v3-subscription-classification-plan.md`
- Plan 1 completion: `docs/superpowers/specs/reviews/2026-04-15-budget-v3-prerequisite-completion.md`
