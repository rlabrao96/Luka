# Next Steps

_Last updated: 2026-04-20_

## Recently Shipped

- **Auth modernization (2026-04-20)** — End-to-end pass on authentication + household invite flow driven by a full ultrareview. Closed a critical JWT **algorithm-confusion** vulnerability (HS256 accepted alongside ES256 on the JWKS path — forged tokens could impersonate any user) and removed the HS256 fallback entirely after Supabase Dashboard migration to asymmetric keys. Supabase JWT Signing Keys rotated (ES256, P-256) and legacy HS256 secret revoked. Supabase publishable/secret API keys (`sb_publishable_...`/`sb_secret_...`) live in Railway and Vercel; legacy anon/service_role JWTs disabled. `SUPABASE_JWT_SECRET` env var removed across all surfaces. Microsoft OAuth button hidden behind `NEXT_PUBLIC_ENABLE_MICROSOFT_LOGIN` flag (default off) until Outlook ingest ships end-to-end.

- **Household invite flow rewrite (2026-04-20)** — `POST /invite/{token}` with atomic one-time claim (conditional `UPDATE ... RETURNING`), `SELECT ... FOR UPDATE` row lock on the target household so the 5-member cap check + membership insert is race-free. `secrets.token_urlsafe(32)` tokens, case-insensitive email binding, automatic revocation of prior pending invites when a new one is sent. Owner-customized `split_ratio` (e.g., `[70, 30]`) is preserved on member join — only auto-equal defaults are rebalanced. Orphan data migration: when a user joins a group from an individual household, their `bank_accounts` and `transactions` move with them instead of stranding under the abandoned household_id. Typed `InviteError` with stable codes; frontend invite page branches on code instead of matching Spanish substrings.

- **PWA session durability fix (2026-04-20)** — Root cause of "iOS PWA forgets my session after a while": Supabase cookies were being set without `Max-Age` and wiped whenever the installed PWA fully closed. Fixed via `withDurableCookie` helper (`frontend/app/lib/supabase/cookieOptions.ts`) that applies `Max-Age=1y` in both the SSR server client and the Next.js middleware. Browser client now explicitly sets `flowType: "pkce"`, `persistSession: true`, `autoRefreshToken: true`. Middleware swapped from `getSession()` (unverified) to `getClaims()` (local JWKS verify).

- **Auth + invite perf pass (2026-04-20)** — (1) JWT payload Redis cache keyed by `sha256(token)[:16]` with TTL bounded by token `exp` (~15-20ms per request saved). (2) `get_current_user_attached` dependency: `db.merge(user, load=False)` attaches cached User to the session without SQL, removing the duplicate `SELECT user` every mutation endpoint was doing. (3) `GET /auth/me` now serves from the user cache blob (household_id + contribution fields stored inline) — zero DB queries on hit. Cache key bumped to `user:v2:{email}`; invalidation wired into `accept_invite`, `remove_member`, `patch_contribution_settings`, profile updates. (4) Middleware matcher tightened to skip `_next/data`, `_next/webpack`, the OAuth callback, service-worker / workbox files, manifest, maps, CSS/JS/font extensions — `getClaims()` used to run ~6-10× per page load. (5) `BudgetSankey` dynamic-imported (chart is ~40KB of d3); orphan `PaceChart.tsx` deleted. `@next/bundle-analyzer` wired behind `ANALYZE=true`.

- **OAuth callback parallelize + login UX polish (2026-04-20)** — Callback route runs `/auth/me` in parallel with `store-provider-tokens`; `setup-email-watch` fire-and-forget (backend idempotent on retry), cutting 2-5s of sequential backend calls off the critical path. Redirect-cookie validated as same-origin-relative to close open-redirect phishing. Login page reads `?error=…` into an `aria-live` alert with Spanish copy for `auth_failed`/`no_session`/`no_code`. OAuth buttons disable + `aria-busy` while pending. `document.cookie` write moved out of render body into `useEffect` (React 19 rules). `Secure` flag added on HTTPS.

- **Hot-path DB indexes migration 038 (2026-04-20)** — Three partial btree indexes on `household_members` and `household_invites` covering the auth hot path: `ix_household_members_user_active`, `ix_household_members_household_active`, `ix_household_invites_pending`. Applied directly via asyncpg against production (alembic chain has a pre-existing duplicate-029 conflict — see "Known Issues" below).

- **Budget config modal on /budgets** — A single accordion modal triggered by a gear button next to the currency toggle on `/budgets`, consolidating the 5 budget knobs (savings target, payday, personal allocation, contribution mode, per-category caps) that used to live scattered across `/settings`. The category-caps editor is redesigned: empty-by-default list of active caps + a `+ Agregar tope` picker that surfaces the top-5 spent categories from the current month's `budget-v2` Sankey data. Per-row save mutations with 900ms auto-collapse + "Guardado ✓" chip. Mobile becomes a bottom sheet. Spec: `docs/superpowers/specs/2026-04-15-budget-inline-config-design.md`.

- **Budget v3 Sankey redesign** — 4-level hogar Sankey (per-source income → `Ingresos Hogar` hub → 5 allocation nodes including `Gasto personal` → per-category breakdown) and 3-level personal Sankey with its own `Mis ingresos` hub. Caller-relative privacy: each viewer sees their own income categories broken out at Level 0, other members appear as one aggregated node per member. Privacy invariant enforced by construction in `contribution_service.income_breakdown_for_household_view`. Migrations 036 (`subscription_overrides.split_type`) + 037 (`user_budget_settings.personal_allocation_amount`).

- **Subscription classification toggle** — `Personal`/`Compartido` pill on each detected subscription in `/subscriptions`. Cascades atomically to the last 3 months of `transaction_splits` rows via `reclassify_subscription_split`, upserts the override on `subscription_overrides`, and invalidates the detection cache. Personal subscriptions correctly excluded from the household pot.

## In Progress

- **Template Agent production monitoring** — Template agent deployed (2am daily cron on slow worker). Monitoring first autonomous template generations and shadow validations. First LLM-parsed transactions confirmed live (BofA via gemini-2.5-flash, 0.98 confidence).
- **Plaid production rollout** — Plaid production credentials configured and deployed. BofA connected successfully, 290 transactions synced. Zelle person extraction and CC payment detection working. Pending (processing) transactions now visible in frontend. OAuth redirect URIs configured.

## Pending

### Auth/security follow-ups (from ultrareview — medium severity)

- **Rate-limit `/send-whatsapp-pin` and `/verify-whatsapp-pin`** — no throttle today; a compromised session can burn SMS credits and bypass the 5-strike lockout by re-triggering send (which resets the attempts counter). Cap send to ~3/10min per user, move attempts state to an independent key that survives resends, switch `random.randint` → `secrets.randbelow`.
- **Partner privacy: `get_contribution_summary` leaks real totals** for members on `fixed` / `reimbursement` contribution mode (`backend/modules/households/service.py:186-260`). MEMORY.md explicitly promises "no raw partner rows ever" — the service currently returns per-user totals regardless of `contribution_mode`. Honor mode at query time.
- **Sole-owner-can't-leave** — if you're the only owner of a group with other members, there's no way to leave without deleting your account. Add a "leave household" endpoint that auto-promotes the oldest remaining member before letting you out.
- **`phone_whatsapp` not unique across users** → ambiguous inbound WhatsApp webhook routing when two users verify the same number. Add a DB unique constraint + reject-on-conflict in `verify_whatsapp_pin`.
- **Partial-auth loop edge case** — `exchangeCodeForSession` with a non-null error but no session could leave a partial cookie state that loops. `signOut()` is now called on the `no_session` branch; verify no other branches can reach the partial state.
- **Open invite endpoint rate-limit** — no throttle on `/invite/{token}` today. UUID is unguessable but add a 20/min/IP limit anyway to close the amplification oracle risk.

### Auth/perf follow-ups (deferred from the perf pass)

- **`api.ts` bundle size (~67 KB)** — single-file re-export surface is large; splitting by domain module would let per-page bundles drop unused paths.
- **`settings/page.tsx` ~48 KB incl. `BankAccountsSection.tsx` ~26 KB** — candidate for section-level dynamic import.
- **Next 16 middleware → proxy rename** — deprecation warning surfaces on every build; not functionally urgent. Rename when touching the file next or when bumping to Next 17.

### Household UX follow-ups (from ultrareview — medium)

- **`CompartidoSection` loading + error + empty states** — briefly renders "Individual" on cold load even if the user is in a household; no error fallback if the fetch throws.
- **CompartidoSection Spanish + design polish** — `"Tu"` → `"Tú"`, drop the hardcoded `"Activo"` badge (drive from `member.status`), replace per-row `"Miembro"` label with role or drop entirely. Swap the hand-rolled card styling for shadcn `Card` to match the rest of settings.
- **Structured invite success toast** — `invite/[token]/page.tsx` currently redirects silently on success; a short "¡Te uniste al grupo!" toast closes the UX loop.

### Alembic hygiene

- **Duplicate `029` revision** — `029_category_budgets.py` and `029_user_currencies.py` both claim revision `029` with `down_revision="028"`, and `030` depends on `029`. Alembic rejects this as an ambiguous branch, so `alembic upgrade head` is currently unusable. DB is already past this point (tables from 029-037 all present; `alembic_version` is stale at `029`). Fix: rename one `029` to `029b` with `down_revision="029"`, `alembic stamp 037`, then `upgrade head` for future migrations.

### Budget v3 follow-ups (deferred from review notes — non-blocking)

These items were caught by code-quality reviewers during the Plan 1 + Plan 2 sprints and explicitly deferred to keep velocity. None block any current functionality.

- **Migration constraint naming inconsistency** (Plan 1 Task 1 review): `ck_subscription_overrides_split_type` (plural) vs the existing `ck_subscription_override_status` / `_day` (singular) on the same table. Cosmetic; consider a follow-up migration that renames the older two for consistency, or accept the new plural form as canonical.
- **Race condition in `reclassify_subscription_split` cascade** (Plan 1 Task 4 review): the per-tx UPDATE-then-INSERT loop can create duplicate `transaction_splits` rows if two requests race for a tx that has no existing split row. Schema doesn't enforce uniqueness on `transaction_splits.transaction_id`. Recommended fix: add a UNIQUE constraint migration on `transaction_splits.transaction_id` and convert the loop to `INSERT ... ON CONFLICT (transaction_id) DO UPDATE`. Also benefits 4 other insertion sites in the codebase.
- **Test fixture model registration gap** (Plan 1 Task 4 review): `noqa: F401` model imports are sprinkled across `test_subscription_reclassify.py`, `test_user_budget_settings.py`, `main.py`, `alembic/env.py`, and `tests/conftest.py` to register FK targets in SQLAlchemy metadata. The right fix is a central `backend/modules/__init__.py` (or similar) that imports all models once.
- **Test spacing in cascade tests** (Plan 1 Task 4 review): `test_subscription_reclassify.py::test_cascade_updates_last_3_months_only` uses `timedelta(days=31 * months_ago)` instead of `dateutil.relativedelta(months=N)`. Works correctly with an inline comment, but `relativedelta` would be more idiomatic.
- **Helper duplication across test files** (Plan 1 Task 5 review): `_get_seed_user`, `_get_seed_household_id`, `_user_by_email` are now defined in 4+ test files with slight naming variations. A shared `backend/tests/helpers/seed.py` would consolidate them.
- **v2 personal Sankey shared-bills double-count** (Plan 1 Task 6 review): `v2_service.py:553` calls `get_user_known_bills` (all bills) for the personal view of the legacy `_build_sankey` path. The v3 personal Sankey uses `get_user_personal_known_bills` instead, so the bug ages out as v3 adoption is confirmed; if the legacy path is removed, this can be deleted.
- **`get_budget_v2` size growth** (Plan 2 Task 9 review): grew significantly with the inline personal-view bucketing logic; could be extracted to a private helper if it gets more complex.
- **`update_personal_allocation` and `update_savings_target` parallel implementations** (Plan 2 Task 11 review): could share a single `update_user_budget_settings_field` helper.
- **Hogar Sankey allocation-node `if` blocks repetition** (Plan 2 Task 7 review): the 5 `if X > _ZERO: nodes.append(SankeyNode(...))` stanzas could be DRY'd via a list-of-tuples loop. Cosmetic.
- **Missing `otras_fuentes` synthetic-source unit test** (Plan 2 Task 7 review): `test_budget_v3_sankey.py` doesn't directly test the overspent-month `otras_fuentes` emission path. The logic is correct by inspection and integration-tested via the flow conservation matrix, but a focused unit test would harden coverage.

### Email Pipeline

- **WhatsApp message templates** — Need to create Meta-approved WhatsApp message templates (`verification_code`, `transaction_alert`) for 24-hour window bypass. Currently limited to 24h response window.
- **Income-aware WhatsApp flow** — LLM + split flow not yet income-aware for inflows. WhatsApp alerts fire for income transactions but the conversational flow assumes expenses.

### Outlook Integration

- **Microsoft Azure / Outlook push notifications** — Azure app registration needed. Requires: `Mail.Read` delegated permission, `offline_access` scope for refresh tokens, redirect URI, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `OUTLOOK_CLIENT_STATE`. Code exists (`OutlookProvider`) but credentials not configured. Login button currently hidden via `NEXT_PUBLIC_ENABLE_MICROSOFT_LOGIN=false` until ingest ships.

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

- **No browser-based UAT for authenticated flows** — Google OAuth's automation-detection blocks chrome-devtools-mcp + browser-use from signing into Luka. Auth changes are verified via TypeScript build + backend curl tests (401 paths, HS256 alg-confusion rejection) + user's own manual smoke. Pre-release tagging should still include a manual click-through by the maintainer.
- **WhatsApp Business API approval** — Currently using test/dev mode. For multi-user production use, Meta's official WhatsApp Business API approval process is needed.
- **No frontend test infrastructure** — No Jest, Vitest, or Playwright configured. Backend has 56 test files (~401 tests) but frontend has zero tests.
- **No CI/CD pipeline** — No GitHub Actions workflows. Backend tests are run manually (`pytest`). Deployment is manual via Railway/Vercel.
- **Personal view `disponible_personal` semantic limitation** — For a full-mode caller, the personal view's `disponible_personal` appears large because the Sankey doesn't subtract the caller's implicit household contribution. Documented in the v3 spec §9 as a known limitation; the clean fix would be either an `aporte_hogar` Level-1 outflow node or capping the personal view's income at `personal_allocation_amount` when set. Neither was shipped in v3 — see the spec for the rationale.
- **Alembic chain duplicate-029** (see "Alembic hygiene" under Pending) — not a runtime issue, but `alembic upgrade head` won't run until resolved. Any new migration (like 038) must be applied via raw DDL in the meantime.

## Infrastructure TODOs

- **Luka Connect env vars** — Verify `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL` are set on production Railway.
- **Supabase OAuth providers** — Google OAuth confirmed enabled. Azure provider should remain disabled in the Supabase Dashboard until the Outlook ingest flow is production-ready (login button is already hidden by env flag, but the provider can still be triggered by direct URL if enabled).

## Future Ideas

- Category budget alerts via WhatsApp (notify when spending approaches category limit)
- Template Agent dashboard — admin UI to view template status, accuracy, shadow validation results per bank
- Multi-currency budget support (currently assumes single currency per household)
- Bank registry admin API — CRUD endpoints for managing bank_registry entries
- Per-transaction `is_shared` override — a user might want to override a one-off transaction without touching the subscription rule (the v3 sprint considered this and explicitly deferred it; out of scope for v3)
