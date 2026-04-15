# Next Steps

_Last updated: 2026-04-15_

## Recently Shipped

- **Budget v3 Sankey redesign** — Two-plan sprint (subscription classification prerequisite + v3 Sankey redesign). New 4-level hogar Sankey (per-source income → `Ingresos Hogar` hub → 5 allocation nodes including new `Gasto personal` → per-category breakdown) and 3-level personal Sankey with its own `Mis ingresos` hub. **Caller-relative privacy**: each viewer sees their own income categories broken out at Level 0 while other members appear as one aggregated node per member. Privacy invariant enforced by construction in `contribution_service.income_breakdown_for_household_view`. New `_build_hogar_sankey` / `_build_personal_sankey` builders share a `_pay_first_fit` routing primitive; legacy `_build_sankey` deleted. Frontend `BudgetSankey.tsx` rewritten with rank-based label placement reading new `level`/`kind`/`member_id` fields. New `personal_allocation_amount` user setting with input on `/settings`. Migrations 036 (`subscription_overrides.split_type`) and 037 (`user_budget_settings.personal_allocation_amount`). 401 backend tests pass; 28 new tests in `test_budget_v3_sankey.py` covering caller-relative privacy regression, recursive-walk forbidden-value detection, and parametrized flow conservation across all seeded households + currencies. Specs: `docs/superpowers/specs/2026-04-15-budget-v3-sankey-redesign-design.md`. Plans: `docs/superpowers/plans/2026-04-15-budget-v3-subscription-classification-plan.md` and `docs/superpowers/plans/2026-04-15-budget-v3-sankey-redesign-plan.md`. Completion checkpoints: `docs/superpowers/specs/reviews/2026-04-15-budget-v3-prerequisite-completion.md` and `docs/superpowers/specs/reviews/2026-04-15-budget-v3-completion.md`.

- **Subscription classification toggle (Plan 1 prerequisite)** — Users can now click a `Personal`/`Compartido` pill on each detected subscription in `/subscriptions` to explicitly classify it as personal or shared. The toggle cascades atomically to the last 3 months of underlying `transaction_splits` rows via `reclassify_subscription_split`, upserts the override on `subscription_overrides`, and invalidates the detection cache. The household-bills aggregate now filters by effective `split_type='shared'` so personal subscriptions are correctly excluded from the household pot. A symmetric `get_user_shared_known_bills` helper is used by `_reimbursement_members_known_bills` so flow conservation holds when reimbursement-mode members have personal bills.

- **Budget page redesign (budget-v2)** — The 1-week parallel sprint (2026-04-14) shipped the original `/budgets/v2` endpoint, contribution-mode-aware privacy (full / fija / sólo reembolso), cuotas manual entry, savings target + payday day configuration, per-category budget caps, silent-by-default risk alert band, runway card with days-to-payday, and overspent-month `otras_fuentes` visualization. **Superseded by the v3 Sankey redesign above** for the visualization layer, but the underlying data model (cuotas, user_budget_settings, contribution_mode dispatch) remains live.

## In Progress

- **Template Agent production monitoring** — Template agent deployed (2am daily cron on slow worker). Monitoring first autonomous template generations and shadow validations. First LLM-parsed transactions confirmed live (BofA via gemini-2.5-flash, 0.98 confidence).
- **Plaid production rollout** — Plaid production credentials configured and deployed. BofA connected successfully, 290 transactions synced. Zelle person extraction and CC payment detection working. Pending (processing) transactions now visible in frontend. OAuth redirect URIs configured.

## Pending

### Budget v3 follow-ups (deferred from review notes — non-blocking)

These items were caught by code-quality reviewers during the Plan 1 + Plan 2 sprints and explicitly deferred to keep velocity. None block any current functionality.

- **Migration constraint naming inconsistency** (Plan 1 Task 1 review): `ck_subscription_overrides_split_type` (plural) vs the existing `ck_subscription_override_status` / `_day` (singular) on the same table. Cosmetic; consider a follow-up migration that renames the older two for consistency, or accept the new plural form as canonical.
- **Race condition in `reclassify_subscription_split` cascade** (Plan 1 Task 4 review): the per-tx UPDATE-then-INSERT loop can create duplicate `transaction_splits` rows if two requests race for a tx that has no existing split row. Schema doesn't enforce uniqueness on `transaction_splits.transaction_id`. Recommended fix: add a UNIQUE constraint migration on `transaction_splits.transaction_id` and convert the loop to `INSERT ... ON CONFLICT (transaction_id) DO UPDATE`. Also benefits 4 other insertion sites in the codebase.
- **Test fixture model registration gap** (Plan 1 Task 4 review): `noqa: F401` model imports are sprinkled across `test_subscription_reclassify.py`, `test_user_budget_settings.py`, `main.py`, `alembic/env.py`, and `tests/conftest.py` to register FK targets in SQLAlchemy metadata. The right fix is a central `backend/modules/__init__.py` (or similar) that imports all models once.
- **Test spacing in cascade tests** (Plan 1 Task 4 review): `test_subscription_reclassify.py::test_cascade_updates_last_3_months_only` uses `timedelta(days=31 * months_ago)` instead of `dateutil.relativedelta(months=N)`. Works correctly with an inline comment, but `relativedelta` would be more idiomatic. Trivial cleanup.
- **Helper duplication across test files** (Plan 1 Task 5 review): `_get_seed_user`, `_get_seed_household_id`, `_user_by_email` are now defined in 4+ test files with slight naming variations. A shared `backend/tests/helpers/seed.py` would consolidate them.
- **v2 personal Sankey shared-bills double-count** (Plan 1 Task 6 review): `v2_service.py:553` calls `get_user_known_bills` (all bills) for the personal view of the legacy `_build_sankey` path. The v3 personal Sankey uses `get_user_personal_known_bills` instead, so the bug ages out as v3 adoption is confirmed; if the legacy path is removed, this can be deleted.
- **`get_budget_v2` size growth** (Plan 2 Task 9 review): the function grew significantly with the inline personal-view bucketing logic. Could be extracted to a private helper if the function gets more complex in the future.
- **`update_personal_allocation` and `update_savings_target` parallel implementations** (Plan 2 Task 11 review): could share a single `update_user_budget_settings_field` helper to remove the parallel-implementation tax — minor refactor.
- **Hogar Sankey allocation-node `if` blocks repetition** (Plan 2 Task 7 review): the 5 `if X > _ZERO: nodes.append(SankeyNode(...))` stanzas could be DRY'd via a list-of-tuples loop. Cosmetic.
- **Missing `otras_fuentes` synthetic-source unit test** (Plan 2 Task 7 review): `test_budget_v3_sankey.py` doesn't directly test the overspent-month `otras_fuentes` emission path. The logic is correct by inspection and integration-tested via the flow conservation matrix, but a focused unit test would harden coverage.

### Email Pipeline

- **WhatsApp message templates** — Need to create Meta-approved WhatsApp message templates (`verification_code`, `transaction_alert`) for 24-hour window bypass. Currently limited to 24h response window.
- **Income-aware WhatsApp flow** — LLM + split flow not yet income-aware for inflows. WhatsApp alerts fire for income transactions but the conversational flow assumes expenses.

### Outlook Integration

- **Microsoft Azure / Outlook push notifications** — Azure app registration needed. Requires: `Mail.Read` delegated permission, redirect URI, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `OUTLOOK_CLIENT_STATE`. Code exists (`OutlookProvider`) but credentials not configured.

### Merchant System

- **Merchant training curation** — Use `/train` UI to verify, merge, and fix merchant categories. Initial seed: 161 canonical merchants from 229 raw names. Ongoing quality improvement.

### LATAM Expansion

- **Collect real email samples** — Bank registry has 101 banks seeded but most lack real email samples for template generation. Priority: Chilean banks (Banco Falabella, BCI, Banco Estado, Banco Itau, Scotiabank), then Colombian and Mexican banks.
- **Template Agent tuning** — Adjust `TEMPLATE_AGENT_MIN_EMAILS` (currently 20) and `TEMPLATE_AGENT_RECENCY_DAYS` (14) based on real-world email volume per bank.

### Multi-Card Reconciliation

- **Cross-account transfer matching** — When a user connects a second card (e.g. Amex), existing CC payment transactions should auto-reclassify from "expense" to "transfer" and reconcile against the card-side entries.

### Phase 2 Forecast Engine (carried from budget-v2 sprint)

- **Phase 2 forecast engine** — Swap `forecast.py` heuristic internals for a Bayesian engine (same function signatures; contract is stable per the 2026-04-14 spec §6.2). Adds uncertainty bands to the risk alert band and better overshoot probabilities for low-history categories.
- **Redis caching for risk categories** — The 2026-04-14 spec §6.3 mentions `budget:risk:{user_id}:{YYYY-MM}` cache with month-long TTL. Deferred in sprint; `v2_service.py` has a `TODO(Phase 2)` marker at the risk-computation block.

## Known Issues

- **No browser-based UAT for the v3 Sankey** — Google OAuth's automation-detection blocks chrome-devtools-mcp + browser-use from signing into Luka. The v3 Sankey redesign was verified via TypeScript build + 401 backend tests + code-level audit. Manual click-through verification by the maintainer is recommended before any major release tagging.
- **WhatsApp Business API approval** — Currently using test/dev mode. For multi-user production use, Meta's official WhatsApp Business API approval process is needed.
- **No frontend test infrastructure** — No Jest, Vitest, or Playwright configured. Backend has 56 test files (~401 tests) but frontend has zero tests.
- **No CI/CD pipeline** — No GitHub Actions workflows. Backend tests are run manually (`pytest`). Deployment is manual via Railway/Vercel.
- **Personal view `disponible_personal` semantic limitation** — For a full-mode caller, the personal view's `disponible_personal` appears large because the Sankey doesn't subtract the caller's implicit household contribution. Documented in the v3 spec §9 as a known limitation; the clean fix would be either an `aporte_hogar` Level-1 outflow node or capping the personal view's income at `personal_allocation_amount` when set. Neither was shipped in v3 — see the spec for the rationale.

## Infrastructure TODOs

- **Luka Connect env vars** — Verify `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL` are set on production Railway.
- **Supabase OAuth providers** — Verify Google OAuth and Microsoft OAuth are enabled in Supabase Auth -> Providers.

## Future Ideas

- Category budget alerts via WhatsApp (notify when spending approaches category limit)
- Template Agent dashboard — admin UI to view template status, accuracy, shadow validation results per bank
- Multi-currency budget support (currently assumes single currency per household)
- Bank registry admin API — CRUD endpoints for managing bank_registry entries
- Per-transaction `is_shared` override — a user might want to override a one-off transaction without touching the subscription rule (the v3 sprint considered this and explicitly deferred it; out of scope for v3)
