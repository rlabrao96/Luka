# Architecture

## System Overview

Luka is a monorepo with a FastAPI backend, Next.js frontend, and two ARQ worker processes. All components share a Supabase PostgreSQL database. Redis handles caching and job queues.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Next.js    │────▶│  FastAPI     │────▶│  PostgreSQL     │
│  (Vercel)   │     │  (Railway)   │     │  (Supabase)     │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │                      ▲
                    ┌──────▼───────┐               │
                    │    Redis     │               │
                    │  (Railway)   │               │
                    └──────┬───────┘               │
                           │                       │
              ┌────────────┼────────────┐          │
              ▼                         ▼          │
    ┌──────────────┐          ┌──────────────┐     │
    │ Fast Worker  │──────────│ Slow Worker  │─────┘
    │ (email, cron)│          │ (sync, LLM)  │
    └──────────────┘          └──────────────┘
              ▲                       ▲
              │                       │
    ┌─────────┴──┐          ┌────────┴───────┐
    │ Gmail/     │          │ Luka Connect   │
    │ Outlook    │          │ Plaid          │
    │ WhatsApp   │          │ Gemini LLM     │
    └────────────┘          └────────────────┘
```

## Core Components

### FastAPI Backend (`backend/main.py`)
- Entry point: `main:app`
- 16 routers registered (auth, households, invite, email, whatsapp, transactions, budgets, cuota, user_budget_settings, bank_accounts, settings, bank_connect, subscriptions, notifications, merchant_review, train, plaid)
- CacheHeaderMiddleware: `private, max-age=30` on GET endpoints
- CORS: configured from `settings.cors_origins` env var
- Health check: `GET /health`
- Talks to: PostgreSQL, Redis, Supabase Auth

### Fast Worker (`backend/worker.py:FastWorkerSettings`)
- Handles: email processing, invite emails, cron jobs
- Config: max_jobs=20, job_timeout=60s
- Queue: `arq:queue` (default)
- Cron jobs: mail watch renewal (3am), raw email purge (hourly), email log purge (2am), webhook cleanup (4am), bank connect syncs (6h), subscription cache (5:30am), Plaid syncs (3:30am)

Fast worker does NOT run reconciliation — the 15-min `reconciliation_tick` cron lives on the slow worker.

### Slow Worker (`backend/worker.py:SlowWorkerSettings`)
- Handles: bank syncs (Connect + Plaid), LLM merchant review, reconciliation, template agent
- Config: max_jobs=5, job_timeout=600s
- Queue: `arq:queue:slow`
- Functions: `run_connect_sync`, `run_plaid_sync_job`, `process_merchant_review`, `run_template_agent`, `reconciliation_tick`
- Cron: reconciliation job (6am daily), template agent (2am daily), `reconciliation_tick` every 15 min `{0,15,30,45}`
- Routing: jobs in `SLOW_JOBS` set in `backend/jobs/queue.py` -> slow queue

### Next.js Frontend (`frontend/app/`)
- Framework: Next.js 16 (App Router)
- State: Zustand 5 (persisted) + TanStack Query 5
- Route groups: `(auth)`, `(dashboard)`, `(public)`
- Auth: Supabase client-side SDK + middleware redirect
- Key components in `frontend/app/(dashboard)/components/`

## Data Model

### Core Tables

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `users` | User accounts, profile, encrypted OAuth tokens | -> household_members, transactions |
| `households` | Shared financial unit (individual/couple) | -> household_members, bank_accounts, budgets |
| `household_members` | User<->household junction (role: owner/member) | -> users, households |
| `household_invites` | Invitation tokens with expiry | -> households |
| `transactions` | Core financial records. Canonical status vocabulary: `pending \| settled \| orphan` (enforced by CHECK constraint; legacy `confirmed` removed). Columns include `transfer_pair_id`, `refund_pair_id` (both exclude row from totals), `card_last_four` (VARCHAR(4)), `orphaned_at` (TIMESTAMPTZ), `dismissed_by_user` (BOOLEAN). Indexed by `(household_id, transaction_date DESC)`, partial `(user_id) WHERE status='pending'`, partials on both pair_id columns, GIN trigram on `raw_merchant_name` (requires `pg_trgm`). | -> users, households, bank_accounts, merchants |
| `transaction_splits` | Per-tx split info (personal/partner/shared) | -> transactions |
| `bank_accounts` | Connected accounts with sync state | -> households, users |
| `merchants` | Raw merchant names -> canonical mapping | -> canonical_merchants |
| `canonical_merchants` | Verified merchant entities | <- merchants |
| `merchant_category_selections` | User category choices per merchant | -> merchants, users |
| `household_budgets` | Monthly budget per account | -> households, bank_accounts |
| `category_budgets` | Per-category monthly caps, per-currency (`currency` NOT NULL since migration 040). Unique on `(household_id, category, month, currency)` — a household can set a CLP cap AND a USD cap on the same category in the same month. | -> household_budgets |
| `household_budget_allocations` | Legacy 50/20/30 split % (hogar/ahorro/personal) | -> households |
| `user_budget_settings` | Per-user savings target, payday, personal allocation amount + currency | -> users |
| `cuota_purchases` | Installment purchases (cuotas) tracked across months | -> users, households |
| `subscription_overrides` | User overrides for detected subscriptions: status, category, next_charge_day, **split_type** (`personal`/`shared`) | -> users |
| `bank_credentials` | AES-256-GCM encrypted Luka Connect creds | -> users |
| `plaid_items` | Plaid connection state per user | -> users |
| `notifications` | In-app notifications | -> users |
| `notification_preferences` | WhatsApp toggle per user | -> users |
| `user_category_preferences` | Custom category ordering | -> users |
| `processed_webhooks` | Idempotency tracking | -- |
| `failed_jobs` | Failed job logging | -- |
| `merchant_review_jobs` | Async LLM review batches | -> users |

### Email Pipeline Tables (migration 030)

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `bank_registry` | 101 banks across 6 countries (CL, CO, MX, PE, BR, US). Domain lookup, country, active template reference | -> email_templates |
| `email_templates` | Declarative JSON extraction templates. Status: candidate/active/retired/failed. Stores template_code, accuracy, validation counts | <- bank_registry |
| `parsed_email_log` | Audit log for every parsed email. Tracks parser used (llm/template/regex), LLM model, waterfall depth, shadow validation results. RLS enabled | -> users |

### Key Relationships
- A user belongs to one household via `household_members`
- Transactions belong to a user + household + optional bank_account + optional merchant
- Bank accounts belong to a household, linked to a user
- Budget hierarchy: household -> household_budgets -> category_budgets
- Bank registry links to active email templates; parsed email log tracks which parser handled each email

### Per-category currency caps (migration 040)
Migration 040 added `category_budgets.currency` (NOT NULL, backfill `'CLP'`) and replaced the old unique constraint with `uq_category_budgets_household_cat_month_ccy` on `(household_id, category, month, currency)`. `v2_service._category_caps` now filters by the view's currency, so a USD cap is ignored by the CLP Sankey and vice versa. The "Configurar presupuesto" modal UI exposes a per-row currency select on every cap, with the full LATAM set validated both client-side and in the `CategoryBudgetItem` pydantic schema.

### Transaction consolidation (migration 039)
Migration 039 added `card_last_four`, `refund_pair_id`, `orphaned_at`, `dismissed_by_user` to `transactions`; migrated status vocabulary `pending|confirmed|settled` → `pending|settled|orphan` with a CHECK constraint; added hot-path indexes listed above; and enabled `pg_trgm` for the GIN trigram index on `raw_merchant_name`. It also linearized the previously-ambiguous `029` branch by renaming `029_user_currencies.py` → `029b_user_currencies.py` (chains after `029_category_budgets`), unblocking `alembic upgrade head`.

### Hot-path indexes (migration 038)
Partial btree indexes applied live on 2026-04-20 so the auth hot path stays O(1):
- `ix_household_members_user_active` on `household_members(user_id) WHERE left_at IS NULL` — hit by every `get_current_user` cache miss + `require_membership`
- `ix_household_members_household_active` on `household_members(household_id) WHERE left_at IS NULL` — hit by member listing + invite capacity checks
- `ix_household_invites_pending` on `household_invites(household_id, LOWER(invited_email)) WHERE accepted_at IS NULL` — covers the revoke-prior-pending query in `create_invite`

## Key Flows

### Email Transaction Flow (Three-Layer Parser)
1. Gmail/Outlook sends push notification -> `POST /webhooks/gmail` or `/webhooks/outlook`
2. Webhook handler ACKs immediately (<200ms), enqueues `process_email` to fast worker
3. Worker fetches email via Gmail API / Microsoft Graph (auto-refreshes OAuth tokens)
4. Bank registry lookup (Redis-cached): identify bank by sender domain -> get country, bank name, active template
5. Financial keyword filter: 50+ keywords in Spanish, English, Portuguese
6. **Layer 1 — Template:** If active template exists for this bank, execute declarative JSON extraction (CSS selectors + regex + fixed transforms). Zero LLM cost.
7. **Layer 2 — LLM Waterfall:** Confidence-based model escalation through 4 Gemini models:
   - gemini-3.1-flash-lite (threshold 0.9) -> gemini-2.5-flash (0.8) -> gemini-3-flash (0.7) -> gemini-2.5-pro (0.0)
   - Circuit breaker: 50% error rate over 20 requests -> 15min cooldown
   - Each model gets 2 attempts before escalating
8. **Layer 3 — Legacy Regex:** Banco de Chile format fallback with transaction type inference from subject/body keywords (person-to-person detection, CC payment detection, income keywords)
9. **Empty body guard:** Emails with no HTML/text body are skipped before parsing to prevent LLM hallucinations
10. Parsed email logged to `parsed_email_log` (parser used, model, waterfall depth, raw HTML for template training)
11. Dedup: Redis-based per-email (24h TTL) + cross-sender 5-minute window (sign-agnostic with abs() for expense amounts)
12. Merchant lookup: known -> instant category, new -> 3 LLM suggestions (Gemini)
13. Transaction saved with correct sign: expenses/transfers as negative, income as positive (unified convention across all sources)
14. WhatsApp: expenses/income get split type buttons; transfers get informational-only message (no split/category flow)

### Template Agent Flow (Daily 2am)
1. **Shadow validation:** For banks with active templates, sample 25% of recent template-parsed emails and re-parse with LLM. Any amount mismatch -> auto-retire template.
2. **Discovery:** Find banks with 20+ LLM-parsed emails but no active template.
3. **Generation:** Feed 10-20 sample emails + their LLM extractions to Gemini 2.5 Flash -> get declarative JSON template.
4. **Validation:** Execute template on all samples, compare vs LLM ground truth. Require 100% amount match, 95% merchant match.
5. **Promotion:** If passes validation, promote to active + link to bank_registry.

### WhatsApp Conversational Flow
1. User receives transaction alert — expenses/income get interactive split buttons, transfers get informational-only message ("Ajuste entre cuentas" — no action needed)
2. User picks split type (Personal/Hogar/Pareja) for non-transfer transactions
3. Category picker presented (inline keyboard)
4. User confirms -> transaction_split created, status updated
5. Manual expense: user sends natural language -> parsed into transaction

### Bank Sync Flow (Luka Connect)
1. User enters bank credentials -> encrypted (AES-256-GCM) -> stored in `bank_credentials`
2. `schedule_connect_syncs` cron (every 6h) enqueues `run_connect_sync` for each credential
3. Slow worker calls Luka Connect API -> scraper fetches transactions
4. Mapper deduplicates + maps to Luka transaction format -> saved to DB
5. Reconciliation job (6am daily) matches email and bank-sourced transactions

### Plaid Sync Flow
1. User connects via Plaid Link widget (production) -> public token exchanged for access token
2. `schedule_plaid_syncs` cron (3:30am daily) enqueues `run_plaid_sync_job`
3. Slow worker calls Plaid Sync API with cursor pagination
4. Smart mapper (`backend/modules/plaid/mapper.py`):
   - Extracts person names from Zelle descriptions ("Zelle payment to JOHN DOE Conf#..." → "John Doe")
   - Detects CC bill payments (Amex ACH, Chase, etc.) → only flags as "transfer" if the target card account exists in the system; otherwise treated as expense
   - Person-to-person payments (Zelle, Venmo, CashApp, PayPal) classified as expense/income, NOT transfer
   - Transaction type derived from Plaid amount sign before flip: positive = expense, negative = income
   - Amounts stored in cents (Plaid sends dollars × 100)
5. Pending (processing) Plaid transactions surfaced in frontend pending section with "bank" badge
6. Reconciliation: `find_email_match()` checks for matching pending email transactions and merges them
7. CC counterpart resolution (`_resolve_cc_counterpart`, `backend/modules/plaid/sync.py`): (a) last-4 match against `BankAccount.account_number`, (b) bank_name substring match in the corrected direction. Household accounts are loaded once per sync and reused across the loop. The modify branch now flows through `mapper.luka_amount_from_plaid(plaid_amount, currency)` — a sign-and-decimals-aware helper — which fixes a CLP 100× scaling bug. Plaid rows land with canonical `status='settled'`.

### Reconciliation Flow
Reconciliation runs in three places: inline during Plaid/Connect sync (immediate), via `run_reconciliation_job` cron (6am daily, catches stragglers), and via `reconciliation_tick` on the slow worker (every 15 min at `{0,15,30,45}`).

Dedup (`backend/modules/reconciliation/dedup.py`) requires currency equality, signed-amount equality, and `bank_account_id` parity, and skips the merchant filter for transfer-typed emails. `apply_match_and_delete_emails` is user-scoped and propagates `transaction_type='transfer'` (+ nulls category) when the email was transfer-typed. `find_plaid_match_for_email` provides the symmetric lookup used by the tick's rematch pass.

1. For each bank tx, `find_email_match()` uses 3-tier priority matching:
   - **Exact:** same merchant (ilike), +/-2 days, exact absolute amount
   - **Fuzzy:** +/-3 days, 30% amount tolerance (absolute)
   - **Sum match:** N email txs from same merchant whose amounts sum to bank tx (5% tolerance)
2. All comparisons use `abs(amount)` — all sources now store negative for expenses, positive for income. Currency and bank_account_id parity are enforced.
3. On match: copies merchant_id, category, transaction_type from email tx -> bank tx; re-links splits; deletes email tx
4. `detect_transfers()` finds same-amount opposite-sign pairs across accounts within +/-2 days, marks both as transfer. Guarded by `user_id` (no cross-member) and `currency` (no cross-currency) equality.
5. `detect_wallet_pairs()` (new 2026-04-22) pairs wallet-funding rows: sign is unconstrained (handles BofA→Venmo funding and Venmo→BofA cash-out symmetrically), window is ±5 days (wallet settlement is slower than bank-to-bank), gated on at least one leg being on a wallet account (Plaid `paypal` subtype → `account_kind='wallet'`, or `bank_name` containing `venmo`/`paypal`/`cashapp`) AND the bank-side merchant containing the short wallet token. The **bank leg** is re-typed to `transfer`; the wallet leg keeps its counterparty name as the canonical expense/income. Same `transfer_pair_id` semantics as regular transfers.
6. `detect_refunds()` finds same-account opposite-sign pairs within 90 days and writes `refund_pair_id` to both rows.

### Reconciliation Lifecycle (`reconciliation_tick`)
Every 15 minutes, for every household, the tick runs five passes in order:

1. **Rematch aging email pendings** against settled Plaid rows via `find_plaid_match_for_email` — handles the race where email arrived before the bank sync and dedup was skipped.
2. **Transfer detection** — `detect_transfers(lookback_days=7)`; opposite-sign only, ±2 days, own-account. `user_id` + `currency` equality enforced.
3. **Wallet-pair detection** — `detect_wallet_pairs(lookback_days=30)`; same- or opposite-sign, ±5 days, gated on a connected wallet account + bank-side merchant token match. Bank leg re-typed to `transfer`; wallet leg keeps counterparty name.
4. **Refund detection** — `detect_refunds(lookback_days=90)`; same-account opposite-sign pairs get a shared `refund_pair_id`.
5. **Aging pass** — email pendings older than 14 days that have had a Plaid sync since `created_at` get promoted to `status='orphan'` (surfaces in `unmatched_email` pending bucket).

An email row can also become an orphan via explicit user dismiss (`POST /transactions/{id}/dismiss`). Matched rows follow the legacy path: email row deleted, bank row enriched with email-sourced category/type. Transfer rows, refund pairs, and orphans are excluded from spend/income totals by `exclude_from_totals()` applied to all aggregation queries in `backend/modules/transactions/service.py`.

### Encryption
- **Fernet** (`backend/core/encryption.py`): symmetric encryption for OAuth provider tokens (Google, Microsoft)
- **AES-256-GCM** (`backend/modules/bank_connect/encryption.py`): bank credentials (RUT + password), 12-byte random nonce per field

## Authentication & Authorization

- **Provider:** Supabase Auth — Google OAuth is the live path; Microsoft/Azure OAuth is code-complete but hidden behind `NEXT_PUBLIC_ENABLE_MICROSOFT_LOGIN` until Outlook ingest ships end-to-end.
- **Token strategy:** JWT verified locally via PyJWT + JWKS. **ES256/RS256 asymmetric only** — legacy HS256 shared-secret path was removed after the Supabase JWT Signing Keys rotation. Accepting HS256 alongside asymmetric algs is classic algorithm-confusion and is now blocked outright in `_decode_token`.
- **JWT payload cache** (`core/security.py:_verify_token`): Redis-keyed by `sha256(token)[:16]` with TTL bounded by the token's own `exp` claim. Skips JWKS + ECDSA verification on repeat requests within the token's lifetime (~15-20ms saved per authenticated call).
- **User cache blob** (`user:v2:{email}`): holds the `User` row fields plus a `membership` sub-object (`household_id`, `contribution_mode`, `fixed_contribution_amount`, `fixed_contribution_currency`). Served directly by `GET /auth/me` on hit — zero DB queries per navigation. Invalidated by `invalidate_user_cache()` on profile updates, household accepts/removes, and contribution-mode changes.
- **Frontend middleware** (`frontend/middleware.ts`): `supabase.auth.getClaims()` for local JWKS-based JWT verification. Matcher excludes Next internals (`_next/data`, `_next/webpack`), the OAuth callback, service-worker files, manifest, maps, and static extensions so the verify cost doesn't multiply across RSC data fetches.
- **Session durability:** browser client configured with `flowType: "pkce"`, `persistSession: true`, `autoRefreshToken: true`. Supabase cookies rewritten with `Max-Age=1y` (via `withDurableCookie` in `app/lib/supabase/cookieOptions.ts`) so an installed iOS PWA survives across restarts instead of losing its session on iOS ITP cookie purges.
- **SessionGuard component:** 30-min browser inactivity timeout with visibility change detection; on PWA mode, mirrors the session into `localStorage` as a backup for ITP-induced cookie wipes and refreshes via `supabase.auth.refreshSession` on resume.
- **Household invite flow:** `POST /invite/{token}` (was GET; GET was CSRF-trivial). Atomic one-time claim via `UPDATE ... RETURNING` + row lock on the target household. Tokens are `secrets.token_urlsafe(32)` (not UUIDv4), bound to the invited email (case-insensitive), idempotent against re-send (new invite revokes any prior pending one), and the service raises typed `InviteError`s with stable codes the frontend branches on.
- **RLS:** Supabase Row Level Security on sensitive tables (including `parsed_email_log`); SECURITY DEFINER aggregate RPC for partner data (no raw partner rows exposed).
- **Provider token ownership check:** `POST /auth/store-provider-tokens` verifies the Google access token against Google's `tokeninfo` endpoint and rejects if `token.email != current_user.email` — prevents a compromised session from planting an attacker-controlled Gmail ingest source.
- **OAuth tokens at rest:** Google/Microsoft provider tokens encrypted with Fernet, stored in `users` table for API access (Gmail, Graph).

## Background Processing

### Worker Architecture
Two ARQ worker processes deployed as separate Railway services:

| Worker | Queue | Max Jobs | Timeout | Purpose |
|--------|-------|----------|---------|---------|
| Fast | `arq:queue` | 20 | 60s | Email processing, invite emails, cron scheduling |
| Slow | `arq:queue:slow` | 5 | 600s | Bank syncs, LLM review, reconciliation (daily + 15-min tick), template agent |

Routing logic in `backend/jobs/queue.py`: jobs listed in `SLOW_JOBS` set are enqueued to slow queue.

### Cron Jobs

| Job | Schedule | Worker | Purpose |
|-----|----------|--------|---------|
| `renew_mail_watches` | 3:00 AM daily | Fast | Refresh Gmail watch subscriptions (7-day expiry) |
| `purge_raw_emails` | Hourly | Fast | Clean old email data |
| `purge_email_logs` | 2:00 AM daily | Fast | Purge raw HTML from parsed_email_log after 7 days |
| `cleanup_processed_webhooks` | 4:00 AM daily | Fast | Remove webhook dedup records |
| `schedule_connect_syncs` | Every 6h | Fast | Enqueue Luka Connect sync jobs |
| `refresh_subscriptions_cache` | 5:30 AM daily | Fast | Pre-compute recurring transaction patterns |
| `schedule_plaid_syncs` | 3:30 AM daily | Fast | Enqueue Plaid sync jobs |
| `run_reconciliation_job` | 6:00 AM daily | Slow | Match email + bank transactions |
| `reconciliation_tick` | Every 15 min `{0,15,30,45}` | Slow | Per-household 5-pass tick: rematch aging emails → detect_transfers (7d, opposite-sign ±2d) → detect_wallet_pairs (30d, wallet-gated ±5d) → detect_refunds (90d) → orphan aging (>14d) |
| `run_template_agent` | 2:00 AM daily | Slow | Shadow validate active templates + generate new ones |

### Async Tasks

| Task | Queue | Description |
|------|-------|-------------|
| `process_email` | Fast | Fetch email -> bank registry lookup -> three-layer parse -> categorize -> save -> WhatsApp alert |
| `send_invite_email` | Fast | Format and send household invite via Resend/SMTP |
| `run_connect_sync` | Slow | Pull transactions from Luka Connect scraper |
| `run_plaid_sync_job` | Slow | Sync US bank via Plaid API |
| `process_merchant_review` | Slow | LLM-batch group unverified merchants |
| `run_template_agent` | Slow | Autonomous template lifecycle management |

## External Integrations

| Service | Purpose | Config |
|---------|---------|--------|
| **Google Cloud Pub/Sub** | Gmail push notifications (real-time email alerts) | `GCP_PROJECT_ID`, OIDC auth, topic: `luka-gmail-notifications` |
| **Gmail API** | Fetch email content, manage watch subscriptions | OAuth tokens stored encrypted in users table |
| **Microsoft Graph** | Outlook email fetch + webhook subscriptions | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` |
| **WhatsApp Cloud API** | Transaction alerts + conversational split flow | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN` |
| **Luka Connect** | Chilean bank scraping (Banco de Chile + 8 others) | Separate repo, `LUKA_CONNECT_URL` + `LUKA_CONNECT_API_KEY` |
| **Plaid** | US bank account connections + transaction sync | `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` |
| **Google Gemini** | LLM email parsing waterfall (4 models) + merchant categorization | `GEMINI_API_KEY` |
| **Resend** | Transactional emails (invites) — Railway blocks SMTP | API key in env |
| **Supabase** | PostgreSQL hosting + Auth provider + RLS | `SUPABASE_URL`, keys |

## Infrastructure & Deployment

**Backend (Railway)**
- Builder: Dockerfile (`backend/Dockerfile`) — Python 3.12-slim + uv
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Workers: `python -m arq worker.FastWorkerSettings` / `worker.SlowWorkerSettings`
- Three services: API server, fast worker, slow worker
- Production URL: `https://luka-production-eb87.up.railway.app`

**Frontend (Vercel)**
- Framework: Next.js (auto-detected)
- Production URL: `https://luka-lovat.vercel.app`

**Database (Supabase)**
- PostgreSQL 15 with connection pooling (PgBouncer)
- `statement_cache_size=0` for asyncpg compatibility
- Connection pool: `pool_size=5`, `max_overflow=10`, `pool_recycle=3600`

## API Endpoints

### Auth (`/auth`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/me` | Get current user profile (incl. household contribution_mode/fixed_amount/currency) |
| PATCH | `/auth/me` | Update profile (name, phone, currency); response includes contribution fields |
| DELETE | `/auth/me` | Delete account (cascade) |
| POST | `/auth/store-provider-tokens` | Store encrypted OAuth tokens |
| POST | `/auth/setup-email-watch` | Initialize Gmail Pub/Sub watch |
| POST | `/auth/send-whatsapp-pin` | Send verification PIN |
| POST | `/auth/verify-whatsapp-pin` | Verify PIN (5-attempt limit) |

### Transactions (`/transactions`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions/mine` | User's transactions (6-month window) |
| GET | `/transactions/monthly-summary` | Monthly totals |
| GET | `/transactions/shared` | Shared household transactions |
| GET | `/transactions/pending` | Pending/unreconciled transactions |
| PATCH | `/transactions/{id}/category` | Update category (trains merchant) |
| PATCH | `/transactions/{id}/split-type` | Change split type |
| DELETE | `/transactions/{id}` | Delete transaction |

#### Transactions — consolidation actions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions/{id}/match-candidates?window_days=7` | Up to 20 ranked bank-tx candidates for a pending email row (same currency/account/user scope) |
| POST | `/transactions/{id}/link` | Manual match: body `{bank_transaction_id}` — deletes the email row, propagates category/type to the bank row |
| POST | `/transactions/{id}/dismiss` | Mark a pending row as `status='orphan'` (user-dismissed, stamps `dismissed_by_user=true` + `orphaned_at`) |
| POST | `/transactions/bulk-action` | Body `{transaction_ids, action: "dismiss"\|"delete"}`; capped at 100 IDs per call |

All four endpoints enforce `user_id` scope in SQL. `TransactionResponse` exposes `created_at`, `orphaned_at`, `transfer_pair_id`, `refund_pair_id`, `source_type` for frontend grouping / age display.

### Households (`/households`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/households` | Create household |
| POST | `/households/{id}/invite` | Generate invite link |
| GET | `/invite/{token}` | Accept invitation |
| GET | `/households/{id}/summary` | Household overview |
| GET | `/households/{id}/partner-stats` | Partner contribution stats |
| GET | `/households/{id}/category-breakdown` | Spending by category |
| GET | `/households/{id}/settlement` | Settlement calculation |
| GET/PATCH | `/households/{id}/split-ratio` | View/update split ratio |

### Budgets (`/budgets`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/budgets/v2/{household_id}` | v3 multi-level Sankey response: caller-relative income breakdown, 4-level hogar / 3-level personal builders (personal Level 2 now carries `Gastos del hogar` = `caller_ratio × shared outflows`), forecast block, risk categories, runway, cuotas, savings target |
| GET | `/budgets/v2/{household_id}/drilldown?node_id&view&month&currency&limit` | Top-N transactions for a clicked Sankey node. Dispatch table in `v2_service.get_node_drilldown`: `src_<slug>` (personal) → caller's income txns in category; `spent_<slug>` / `spent_other` → top expense txns in / outside the top-5 (personal scope filters on `split_type='personal' OR NULL`, hogar on `split_type='shared'`); `gastos_hogar_personal` / `disponible_hogar` → top shared expense txns overall; `meta_ahorro*` → savings txns; hubs / synthetic / `spent_remaining` / `member_*` return an empty block with a reason. |
| GET/POST | `/budgets/monthly/{household_id}` | Legacy monthly budget CRUD |
| GET | `/budgets/personal/{household_id}` | Legacy personal budget view |
| GET/POST | `/budgets/allocation/{household_id}` | Legacy 50/20/30 allocation |
| GET | `/budgets/categories/{household_id}?currency=` | Per-category caps, optionally filtered to one currency. Without `currency` returns caps across every currency the household has set. |
| POST | `/budgets/categories/{household_id}` | Replace all caps for the month. Each `budgets[]` item carries its own `currency` (validated against the LATAM set). |
| GET/PATCH | `/budgets/settings` | User budget settings: savings_target_amount, savings_target_currency, payday_day_of_month, **personal_allocation_amount**, **personal_allocation_currency** |
| POST/GET/DELETE | `/cuotas` | Installment purchases (cuotas) CRUD |

### Bank Accounts (`/bank-accounts`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/bank-accounts` | List connected accounts |
| POST | `/bank-accounts` | Create account manually |
| PATCH | `/bank-accounts/{id}` | Update account details |
| DELETE | `/bank-accounts/{id}` | Delete (cascade: splits -> txns -> account) |

### Luka Connect (`/bank-connect`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/connect` | Store encrypted bank credentials |
| DELETE | `/disconnect` | Remove bank connection |
| POST | `/sync` | Trigger manual sync |
| GET | `/sync-status` | Check sync progress |
| GET | `/connections` | List active connections |
| POST | `/webhooks/luka-connect` | Receive sync completion webhook |

### Plaid (`/plaid`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/items` | List Plaid connections |
| POST | `/create-link-token` | Generate Plaid Link token |
| POST | `/exchange-token` | Exchange public token for access |
| DELETE | `/disconnect` | Remove Plaid connection |
| POST | `/sync` | Trigger manual Plaid sync |

### Subscriptions (`/subscriptions`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/subscriptions/detected` | Auto-detected recurring transactions (override-merged) |
| PUT | `/subscriptions/override` | Upsert override (status/category/next_charge_day/split_type). When `split_type` is set, routes through `reclassify_subscription_split` which cascades to the last 3 months of `transaction_splits` and invalidates the detection cache atomically. |
| POST | `/subscriptions/refresh` | Force recompute of the detection cache |

### Notifications (`/notifications`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications` | List notifications |
| GET | `/notifications/unread-count` | Unread count |
| PATCH | `/notifications/{id}` | Mark as read |
| DELETE | `/notifications/{id}` | Delete notification |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET/PATCH | `/notifications/preferences` | Notification preferences |
| GET/PUT/POST | `/categories/preferences` | Category ordering + visibility |
| GET | `/categories/preferences/{cat}/usage` | Category usage stats |
| POST | `/categories/preferences/{cat}/delete` | Delete custom category |

### Merchant Review (`/merchant-review`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{job_id}` | Get review job |
| GET | `/{job_id}/status` | Job progress |
| PATCH | `/{job_id}/merchants/{id}` | Update merchant mapping |
| POST | `/{job_id}/skip` | Skip review |
| DELETE | `/{job_id}` | Cancel review job |

### Merchant Training (`/train` — local dev only)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/train` | Training UI page |
| GET | `/train/merchants` | List unverified merchants |
| PATCH | `/train/merchants/{id}` | Update merchant |
| POST | `/train/merchants/{id}/merge` | Merge duplicates |
| DELETE | `/train/merchants/{id}` | Delete merchant |
| GET | `/train/stats` | Merchant DB stats |

### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/gmail` | Gmail Pub/Sub push endpoint |
| POST | `/webhooks/outlook` | Outlook webhook endpoint |
| GET/POST | `/webhooks/whatsapp` | WhatsApp verification + messages |

## Frontend Architecture

**Framework:** Next.js 16 with App Router

**Route Groups:**
- `(auth)` — Login, OAuth callback, onboarding (setup-household, connect-bank, verify-whatsapp), invite acceptance
- `(dashboard)` — Protected pages: home, transactions, budgets, household, subscriptions, notifications, settings
- `(public)` — Privacy policy, terms of service, data deletion (Meta compliance)

**State Management:**
- **Zustand 5** — lightweight client state: `{ householdId, userId, userFullName, onboardingDraft }`, persisted to localStorage
- **TanStack Query 5** — all API data, 30s staleTime, prefetched in `StoreInitializer`
- 8 dashboard queries prefetched on app load (no waterfall)

**Key Dashboard Components** (`frontend/app/(dashboard)/components/`):
- `TransactionCard` — merchant, amount, direction, bank, category tag, split badge
- `RecentTransactions` — date-grouped transaction list with inline category/split editing
- `CategoryDonut` — interactive Recharts pie chart with hover tooltips
- `SpendingChart` — 6-month area chart (personal vs shared)
- `PaceChart` — daily spend vs budget pace line (on_track green/red)
- `BalanceCard` — total checking balance across active accounts
- `BudgetBars` — horizontal progress bars color-coded by usage %
- `BudgetConfigModal` — Radix Dialog accordion mounted on `/budgets`. Five rows (Meta de ahorro · Gasto personal · Día de pago · Aporte al hogar · Topes por categoría) ported from the old `/settings` budget sections. Every currency selector defaults to the user's `preferred_currency` (full LATAM set) via the shared `currencies.ts` helper — no more hardcoded CLP. Per-row save mutations, 900ms auto-collapse with "Guardado ✓" chip, first-open `needsSetup` nudge, mobile bottom-sheet variant. Caps editor is empty-by-default with a top-5-spent picker derived from the `budget-v2` Sankey data; each cap row carries its own currency `<select>` (per migration 040), so a household can mix CLP and USD caps in the same month
- `BudgetSankey` — Recharts Sankey with `onNodeClick` / `activeNodeId` props. Drillable nodes get `cursor: pointer`, an invisible 8px hit halo (so clicks on thin rectangles and adjacent labels land), and a dark stroke when active. Hubs, synthetic deficit plug, `Aún disponible`, and `member_*` nodes are inert (matches the backend `skip` set in `get_node_drilldown`). Bottom margin + chart height sized to keep the "Gastos fijos pendientes" two-line below-label fully visible
- `BudgetDrilldownCard` — Renders the `/drilldown` response beneath each Sankey card. Skeleton while fetching, empty-state helper text before the first click ("Haz clic en cualquier categoría para ver las 5 transacciones más grandes."), inline list of merchant / date / bank / amount when populated. Separate state per view (`hogarNodeId` vs `personalNodeId` in `budgets/page.tsx`) so clicking on Hogar doesn't disturb Personal. Replaced the old `RunwayCard` slot
- `AllocationCard` — 50/20/30 allocation sliders with suggestion pills
- `MonthSelector` — dropdown (desktop) / bottom sheet (mobile)
- `PendingBlock` — pending/unreconciled transaction buckets with date display, source badges ("email"/"bank"), correct category type by amount sign, and transfer display ("Ajuste entre cuentas")
- `MerchantCard` — merchant review approval cards (currency-aware formatting, prefetch on hover)
- `SessionGuard` — PWA persistent sessions + 30-min inactivity timeout
- `StoreInitializer` — prefetches all dashboard data on mount

**React Query Hooks** (`frontend/app/lib/hooks/`):
- `useMyTransactions`, `useSharedTransactions`, `usePendingTransactions`, `useMonthlySpending`
- `useBudgetStatus`, `usePersonalBudget`, `useAllocation`, `useCategoryBudgets`
- `useHouseholdSummary`, `usePartnerStats`, `useCategoryBreakdown`, `useSettlement`, `useSplitRatio`
- `useNotifications`, `useUnreadCount` (30s polling)
- `useSyncStatus` (3s polling during active sync), `useBankConnections`
- `useMerchantReview`, `useReviewStatus`, `useOptimisticReview`
- `useSubscriptions`

**Key Patterns:**
- Dynamic Recharts imports (~200KB deferred via `next/dynamic`)
- Optimistic updates on category changes and notification preferences
- Bottom sheets on mobile for filters and category selection
- Mobile-first responsive: floating bottom nav on mobile, sidebar on desktop
- API client (`frontend/app/lib/api.ts`): 50+ methods covering all backend endpoints
- Prefetch on hover for merchant review cards

## Testing

**Backend:** 56 test files in `backend/tests/`, ~401 tests passing, covering all major modules. Reconciliation tests hit a real PostgreSQL instance via the savepoint-scoped `db` fixture — no DB mocks.
- Auth, transactions, budgets, households, email parsing, WhatsApp handler, merchant normalization
- Bank connect encryption/mapping, queue routing, worker settings, notifications, categories, subscriptions, reconciliation
- LLM parser, LLM parser integration, parser orchestrator, template executor, template agent, bank registry service
- **Budget v2/v3:** `test_budget_v2_endpoint.py` (10 tests), `test_budget_v3_sankey.py` (~28 tests covering the 4-level hogar builder, 3-level personal builder, `_pay_first_fit` routing, caller-relative privacy regression, and a parametrized flow-conservation matrix across 6 seed/view combos), `test_budget_forecast.py` (22 tests), `test_user_budget_settings.py` (9 tests), `test_contribution_modes.py` (12 tests)
- **Subscription classification:** `test_subscription_reclassify.py` (~20 tests covering the schema, upsert, 3-month cascade, override-wins, household/personal bill filters, and router endpoint integration)
- Config: `asyncio_mode = "auto"`, testpaths = `["tests"]`
- Run: `cd backend && pytest -v`

**Frontend:** No test infrastructure configured (no Jest/Vitest/Playwright)

**CI/CD:** No GitHub Actions pipeline. Deployment is manual via Railway (backend) and Vercel (frontend auto-deploy on push)

## Design Decisions

**Three-layer email parser:** Templates are cheapest (zero LLM cost), LLM waterfall handles unknown formats, regex catches legacy patterns. Template Agent autonomously upgrades banks from Layer 2 to Layer 1 as data accumulates.

**Confidence-based LLM waterfall:** Cheaper models try first; only escalate to expensive models when confidence is low. Each step has a threshold (0.9/0.8/0.7/0.0). This minimizes cost while maintaining accuracy.

**Circuit breaker on Gemini API:** If 50%+ of API calls fail in a 20-request window, skip LLM for 15 minutes and fall back to regex. Prevents cascade failures.

**DB-backed bank registry over hardcoded domains:** 101 banks across 6 countries need structured metadata (country, known subjects, active templates). Redis cache (24h TTL) keeps lookups fast.

**Two-tier worker queue:** Email webhooks must ACK in <200ms, but bank syncs can take 10+ minutes. Splitting into fast (max_jobs=20, 60s) and slow (max_jobs=5, 600s) workers prevents slow jobs from blocking webhook processing.

**No debt ledger:** Partner contributions are computed via aggregate queries on transactions, not maintained in a separate table. This avoids dual-write consistency issues and keeps the schema simpler.

**Global merchant DB:** Merchant categorizations are shared across all users to build a training dataset. Individual users can override categories via `merchant_category_selections`.

**PyJWT over Supabase SDK for auth:** Local JWT validation with JWKS avoids a network round-trip to Supabase on every request. Fallback chain (ES256 -> RS256 -> HS256) handles Supabase key rotation.

**Redis user cache:** `get_current_user()` caches user profiles for 5 minutes, avoiding repeated DB lookups on sequential API calls from the same user.

**Joint account auto-classification:** Bank accounts with `account_type = 'joint'` auto-classify all transactions as shared, skipping the WhatsApp split question.

**Luka Connect over Fintoc:** Fintoc was removed entirely and replaced with Luka Connect (standalone bank scraper). Luka Connect supports 9 Chilean banks via browser automation, stored as AES-256-GCM encrypted credentials.

**Unified amount sign convention:** All transaction sources (email, Plaid, bank connect) store expenses/transfers as negative amounts and income as positive. Email pipeline infers transaction_type from LLM/regex output and flips sign accordingly. This eliminates sign-mismatch bugs in reconciliation, frontend display, and dedup logic. A data migration converted existing email transactions to negative expense amounts.

**Transaction type classification (expense vs transfer vs income):** Person-to-person payments (Zelle, bank transfers to other people) are classified as expense or income, NOT transfer. "Transfer" is reserved for own-account moves: CC bill payments, checking-to-savings, ATM cash. This distinction drives the WhatsApp flow (transfers get informational-only messages) and frontend display (transfers show "Ajuste entre cuentas" instead of category/split controls).

**3-tier reconciliation:** Email transactions arrive first (real-time), bank transactions arrive later (scheduled sync). Reconciliation matches them with decreasing confidence: exact -> fuzzy -> sum-match. Email data enriches bank transactions (user-edited categories transfer over), then email duplicates are deleted.

**Per-user merchant overrides:** `merchant_category_selections` supports both global (shared dataset) and per-user category choices via nullable `user_id` FK. Users see their own overrides first, global selections second, LLM suggestions last.

**Subscription detection with explicit classification override:** Recurring expenses are detected from transaction patterns (2+ consecutive months, +/-20% amount tolerance), cached in `detected_subscriptions_cache`, and refreshed on demand. Each detected subscription's `split_type` defaults to the inferred value from the underlying `transaction_splits` row, but users can explicitly override via a click-to-flip pill on the subscriptions page. The override is stored on `subscription_overrides.split_type` and cascades atomically to the last 3 months of `transaction_splits` via `reclassify_subscription_split` — so the next time the detection runs, the new classification is already reflected in the underlying data. The household-bills aggregate filters by effective shared-only, with a symmetric `get_user_shared_known_bills` helper used in `_reimbursement_members_known_bills` so flow conservation holds when reimbursement-mode members have personal bills.

**v3 Sankey: caller-relative privacy by construction:** The household Sankey shows the viewer's own income categories broken out at Level 0, while other household members appear as exactly one aggregated node per member (`Ingresos {Name}` for full-mode members, `Contribución fija {Name}` for fixed-mode members). The privacy invariant — "fixed-mode members' real income is never read" — is enforced structurally in `contribution_service.income_breakdown_for_household_view`: the dispatch on `contribution_mode` happens before any non-caller transaction read, and the `fixed` branch reads only the `fixed_contribution_amount` from a single member-table SELECT result row, never querying the member's `transactions` table. This is verified end-to-end by `test_hogar_fixed_privacy_recursive_walk`, which seeds a synthetic forbidden value as a fixed-mode member's real income and walks every node and link in the response JSON to confirm the value never leaks.

**v3 Sankey: hub-based flow routing:** Both the 4-level hogar builder and the 3-level personal builder collapse all sources through a single `ingresos_hogar` / `ingresos_personales` hub node at Level 1. This makes flow conservation trivial (every source emits one link to the hub; the hub emits one link per allocation; every allocation either terminates or fans out to a single breakdown level). When income can't cover all allocations, a synthetic `Ingresos por cubrir` source enters at Level 0 alongside the real sources (renamed from `otras_fuentes`; `kind="deficit"`, amber), absorbed via the `_pay_first_fit` routing primitive. Verified across 6 seeded household + view combos by `TestFlowConservationAllSeeds`.

**Personal Sankey split-type scoping:** The personal view's MTD fetch, 3-month category stats, and 14-day burn queries all `outerjoin(TransactionSplit)` and filter on `split_type='personal' OR IS NULL`. Email-ingested transactions on non-joint accounts have no `transaction_splits` row at ingestion (`jobs/tasks.py` only writes a split for joint accounts), yet the frontend treats a NULL split as "personal" when rendering the tag. The NULL fallback keeps the backend in sync with that display rule — strictly filtering on `split_type='personal'` drops every email-ingested personal expense and undercounts the Personal Sankey by thousands. Household queries still inner-join on `split_type='shared'` (shared is opt-in by design, so a NULL split never means shared).

**Personal Sankey "Gastos del hogar" bucket:** In the Personal view, Level 2 carries an explicit `Gastos del hogar` allocation equal to `caller_ratio × (shared MTD spend + household unpaid shared bills)`. `caller_ratio` comes from `households.split_ratio[i]` mapped to the i-th active member in `joined_at ASC` order (matching `calculate_settlement`), with a 1/N equal-split fallback when the ratio is absent or shorter than the member list. The bucket routes through `spendable_ceiling` via the existing `personal_allocation` parameter — so `Disponible personal` = caller income − gastos_hogar − personal_bills − cuotas − savings_target. This stops the prior double-count where shared expenses appeared both in the Personal Level-3 category breakdown and implicitly inside `Disponible personal`.

**Clickable Sankey drilldown:** Every non-hub, non-synthetic node is a link — clicking opens `GET /budgets/v2/{household_id}/drilldown` and renders the top-5 transactions in the `BudgetDrilldownCard` below the chart. The single endpoint handles every node id pattern (source categories, spent categories, `spent_other`, shared pool, savings), and the skip list for inert nodes lives on both sides (backend `get_node_drilldown` + frontend `NON_DRILLABLE`) so the UI only surfaces cursor-pointer styling where a click will actually return data.

**Single document scroll:** The dashboard layout used to nest `h-screen overflow-hidden` on the root flex with `overflow-y-auto` on `<main>`, which produced two vertical scrollbars in some browsers (inner main + browser). The budget page stacked another `overflow-x-auto` on top of `BudgetSankey`'s own horizontal scroller. The layout now uses document-level scrolling with a `sticky top-0 h-screen` desktop sidebar, and the redundant wrappers are gone — one scrollbar, no input-target ambiguity.
