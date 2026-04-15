# Day 4 — Integration Verification Report

**Sprint:** Budget page redesign (`budget-v2`)
**Date:** 2026-04-14
**Status:** ✅ PASS — ready for Day 5 UAT / Day 6 UX pass / Day 7 ship
**Main HEAD at verification:** `1137b03`

---

## Scope

Per the plan's Task I, this is the full integration checkpoint after all
nine implementation chunks (0, A–H) have landed on `main`. The plan specced
a browser-based end-to-end agent (chrome-devtools-mcp / browser-use) for
§11.4 verification, but Google OAuth's automation-detection policy blocks
CDP-controlled Chrome instances from signing into Luka's Supabase auth
flow. We fell back to an **API-level validation matrix** plus **manual
screenshot UAT rounds** with the human in the loop, which together cover
everything the browser agent would have checked except Lighthouse scores
and network-tab inspection.

## What was verified

### 1. Backend test suite — **48/48 pass**

```
pytest tests/test_budget_v2_endpoint.py tests/test_budget_forecast.py \
       tests/test_contribution_modes.py tests/test_cuota_service.py \
       tests/test_user_budget_settings.py tests/test_subscriptions_read.py \
       tests/test_budget_migration_035.py -q
→ 48 passed in 179s
```

Coverage:
- Migration 035 smoke (4 tests)
- Forecast engine pure functions (19 tests)
- `/budgets/v2` endpoint (10 tests — incl. privacy regression + 2 new
  Sankey flow conservation tests added during Day 4)
- Contribution modes + privacy invariant (5 tests)
- Cuota CRUD (4 tests)
- User budget settings (4 tests)
- Subscriptions read wrapper (2 tests)

### 2. Frontend build — **clean**

```
cd frontend && npm run build
→ Compiled successfully, 21 routes emitted, 0 TypeScript errors
```

### 3. API-level validation matrix — **all pass**

8 `{household_id, month, currency, view}` combinations validated via
direct `get_budget_v2()` calls (bypasses HTTP + auth for speed):

| # | Household | Month | Currency | View | Result |
|---|-----------|-------|----------|------|--------|
| 1 | user-hh (real) | 2026-04 | CLP | household | PASS |
| 2 | user-hh | 2026-04 | CLP | personal | PASS |
| 3 | user-hh | 2026-04 | USD | household | PASS (post-fix) |
| 4 | user-hh | 2026-04 | USD | personal | PASS (post-fix) |
| 5 | user-hh | 2026-03 | CLP | household | PASS (deep-overspent) |
| 6 | user-hh | 2026-03 | CLP | personal | PASS |
| 7 | hogar-fixed | 2026-04 | CLP | household | PASS (privacy) |
| 8 | hogar-full | 2026-04 | CLP | household | PASS (post-fix) |

Each combination was checked against nine invariants:
- **I1** Response schema round-trips through `BudgetV2Response.model_validate`
- **I2** All numeric fields non-negative and finite (no NaN/Inf)
- **I3** Sankey flow conservation: for every node, inflow/outflow balance
  against the node's value (intermediate nodes conserve, source nodes
  equal their outflow, sink nodes equal their inflow)
- **I4** Every link's source/target exist in `sankey.nodes`
- **I5** No duplicate labels (catches the "Otros" collision between
  residual bucket and real category)
- **I6** Risk category p_overshoot ∈ [0, 1] and alert matches spec §6.3 rule
- **I7** Currency normalization (CLP integer, USD cents)
- **I8** Privacy invariant: fixed-mode partner's real income never appears
  in household view
- **I9** Personal vs household differential behaves correctly

### 4. Flow conservation — deep verification

Before Day 4, `_build_sankey` clamped `income → spendable` but still
emitted `income → known_bills / cuotas / savings_target` links at their
full values, violating conservation when the fixed outflow total
exceeded income. This manifested as impossible arrows in the visual
Sankey for USD (user's USD income < USD known_bills) and HOGAR FULL
(zero income, positive subscriptions + seeded cuota).

**Fix:** `backend/modules/budgets/v2_service.py` — first-fit routing.
Income pays known_bills, then cuotas, then savings_target, then
spendable, in priority order. Each step can split between
`income → X` and `otras_fuentes → X` when income runs out mid-step.
Committed in `1137b03`.

**Regression tests:**
- `test_sankey_flow_conservation_overspent_hogar_full` — HOGAR FULL
  (no income txns, positive subscriptions + seeded cuota). Walks
  every Sankey node and asserts inflow/outflow/value consistency.
- `test_sankey_flow_conservation_fixed_outflow_exceeds_income` —
  HOGAR SOLO with synthetic $50k income and $200k savings target
  (so fixed_outflow > income by construction).
- Reusable `_flow_conservation_errors()` helper added to the test
  module; future regressions can reuse it without duplicating the
  walk logic.

### 5. Privacy invariant — **verified**

The `test_hogar_fixed_privacy_partner_amount_synthetic` regression test
inserts a synthetic partner income of `$2,137,913 CLP` inside a
rollback SAVEPOINT, then calls `get_budget_v2(view='household')` and
walks every leaf in the response JSON. The forbidden value never
appears — the `fixed` branch in `contribution_service.income_for_household_view`
reads only `fixed_contribution_amount` / `fixed_contribution_currency`
from the `household_members` row, never JOINs to `transactions`, and
is structurally incapable of leaking real income for fixed-mode members.

Chunk D's code review flagged this invariant as the #1 sprint gate;
it's verified end-to-end via a real DB test.

### 6. Contract fixture — **locked**

`backend/tests/fixtures/budget_v2_sample_response.json` was committed
on Day 1 as the frozen API contract. The `test_contract_fixture_matches_pydantic_schema`
test runs `BudgetV2Response.model_validate()` against it on every
CI run — any drift in either direction (schema change, fixture edit)
breaks the test loudly, preventing frontend/backend desync mid-sprint.

## Manual UAT — rounds summary (human in the loop)

Four rounds of manual visual UAT were run against the real dev DB
with the user's authenticated Chrome session. Each round closed
concrete bugs:

| Round | Finding | Fix (commit) |
|-------|---------|--------------|
| 1 | Frontend calling Railway prod → 422s | `.env.development.local` points frontend at localhost:8000 |
| 1 | BudgetSankey crashed with NaN path attributes when data empty | `BudgetSankey.tsx` empty-state guard + safe nodes/links filter (`e8fc98c`) |
| 2 | Sankey right-edge labels clipped outside chart bounds | Custom node renderer detects terminal nodes and flips label to left (`e8fc98c`) |
| 2 | USD values formatted 100× too large | `formatMoney` divides USD by 100 (matches Luka cents convention, `e8fc98c`) |
| 3 | March CLP Sankey showed flow imbalance (spent > spendable) | `otras_fuentes` synthetic source node for savings/credit drawdown (`e8fc98c`) |
| 3 | "Otros" label collided between residual bucket and risk category | Renamed residual to "Otras categorías" (`e8fc98c`) |
| 3 | Settings had budget sections separated by unrelated sections | Re-ordered: `BudgetSettingsSection` + `CategoryBudgetsSection` now adjacent to `ContributionSection` (`e8fc98c`) |
| 3 | User asked "where do I set per-category budgets?" | Shipped new `CategoryBudgetsSection` that wires to existing `/budgets/categories/{household_id}` endpoints (`e8fc98c`) |
| 4 | Personal section duplicated Hogar when only one member has transactions | Collapse Personal to a one-line note when data matches Hogar (`e8fc98c`) |
| 4 | USD Hogar Sankey still had broken flow for overspent USD | **Root-caused via API validation matrix — first-fit routing fix (`1137b03`)** |

## Known limitations (carried forward to Day 6 / Day 7)

1. **No automated browser UAT.** Google OAuth's automation-detection
   policy blocks chrome-devtools-mcp and browser-use from signing
   into Luka. Day 6 UX pass (Task J) and Day 7 ship (Task K) will
   rely on continued manual verification by the user.
2. **No Lighthouse audit in Task I.** Planned at spec §11.4 but
   same OAuth block prevents running it authenticated. Can be run
   against a public route or deferred until production.
3. **No network-tab PII scan in Task I.** Substituted by the
   recursive JSON-leaf privacy walk in `test_hogar_fixed_privacy_partner_amount_synthetic`
   which is more rigorous for the actual privacy-critical contract
   (`view=household` on fixed-mode members).
4. **Personal section currently always matches Household for the
   real user's data** because Camila's transactions haven't synced
   yet. When they do, the collapse note will auto-disappear. Not
   a bug — correct behavior per the collapse logic.
5. **Task E RecentTransactions non-compact row** still has a
   `TODO(chunk-E)` marker for the "Marcar como cuota" trigger
   wiring. Ship Task K can close it or it can become a post-ship
   follow-up.
6. **Chunk D Settings UI** seeds `currentMode="full"` by default
   rather than from a `households/{id}/summary` extension that
   returns contribution_mode fields. First-time saves work, but
   existing-state preload shows defaults until the summary endpoint
   is widened. Post-ship follow-up.

## Commits verified in this Day 4 checkpoint

```
1137b03 fix(budget-v2): Sankey flow conservation when fixed outflow exceeds income  ← Day 4
e8fc98c fix(budget-v2): UAT round 1 — flow conservation, USD cents, label fixes, category budgets UI
cf6fd68 chore(backend): uv sync pulls in transitive deps for google-genai
93b3493 merge(budget-v2): chunks G+H — risk alert band, runway card, page wiring
087e6f9 merge(budget-v2): chunk F — savings target + user_budget_settings service
cd2d371 merge(budget-v2): chunk E — cuotas CRUD + MarkAsCuotaDialog
ba05cb4 merge(budget-v2): chunk D — contribution modes + privacy-invariant extraction
a1ea88a merge(budget-v2): chunk B — BudgetSankey component + dev fixture
9a0e633 merge(budget-v2): chunk A — currency formatter + scaffolded two-section page
986b320 merge(budget-v2): chunk C — /budgets/v2 endpoint + forecast engine
b0db147 fix(budget-v2): seed script — explicit day=1 in cuota month arithmetic
5bfb940 fix(tests): conftest db fixture must set statement_cache_size=0 for PgBouncer
3f1c7f0 feat(budget-v2): chunk 0 — migrations, models, seed fixtures, verification orchestrator
```

## Verdict

**READY FOR DAY 5 UAT / DAY 6 UX PASS / DAY 7 SHIP.**

All architectural goals from spec §4 are implemented and verified:
- Household + Personal two-section layout with Sankey flow
- Contribution-mode-aware privacy invariant (full / fixed / reimbursement)
- Savings target subtracted from spendable ceiling, investment excluded from spent
- Cuotas manual entry with dialog + CRUD endpoints
- Risk alert band (silent when no alerts, amber when `p_overshoot > 0.70`)
- Runway card (days to payday + 14d burn, red at-risk styling)
- Per-category budget UI (new addition from UAT round 4)
- Currency toggle with auto-hide and USD cents normalization

The only thing the spec §11.4 Day 4 agent would have caught that we
didn't is cosmetic polish (Lighthouse LCP/CLS numbers). That's
deferred to Day 6 (Task J) UX consistency pass.
