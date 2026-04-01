# Luka — Project State Document
**Date:** 2026-04-01 (session 13 — end)
**Status:** **Merchant cleaning & review pipeline.** New canonical_merchants + notifications + merchant_review_jobs tables (migration 022). LLM grouping via Gemini (batched, 50/call). Two-phase pipeline: Phase 1 groups raw names → canonical merchants, Phase 2 categorizes. Notifications API (list, unread count, mark read). Merchant review API (cards, approve, skip). ARQ job triggers from bank connect webhook. Frontend: notification badge in sidebar/bottom nav, notifications page, processing banner, Tinder-style review cards. Transaction display_name via canonical merchant join. CLI: train_merchants.py (seed, review, merge, stats, regroup). Local training web UI at /train (card grid, edit, merge, delete, approve). 22 commits.

---

## What Is Luka

Chilean personal finance SaaS for individuals and couples. Captures bank transactions via email push notifications, categorizes via LLM, lets users act via WhatsApp, and visualizes on a responsive web dashboard.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) + ARQ (async jobs) + Redis |
| Database | Supabase (PostgreSQL 15) + SQLAlchemy async 2.0 + Alembic |
| Auth | Supabase Auth — Google OAuth (Gmail) + Microsoft OAuth (Outlook) |
| Frontend | Next.js 16 (App Router) + Tailwind CSS 4 + shadcn/ui + Recharts |
| Client state | Zustand 5 (persisted to localStorage) |
| Server state | TanStack Query 5 (30s staleTime) |
| Hosting | Railway (backend) + Vercel (frontend) |

---

## Repository Layout

```
/
├── backend/
│   ├── main.py                     ← FastAPI app factory + all routers
│   ├── worker.py                   ← ARQ WorkerSettings (cron + on-demand jobs)
│   ├── pyproject.toml
│   ├── core/
│   │   ├── config.py               ← Pydantic Settings (all env vars)
│   │   ├── database.py             ← async engine + AsyncSessionLocal
│   │   ├── security.py            ← PyJWT JWKS validation (ES256/RS256/HS256), get_current_user()
│   │   └── cache.py               ← Redis cache helpers (get/set/delete with TTL)
│   ├── modules/
│   │   ├── auth/                   ← User model + GET/PATCH/DELETE /auth/me
│   │   ├── households/             ← Household, Member, Invite, BankAccount, Budget models
│   │   │                             POST /, POST /{id}/invite, GET /{id}/summary, GET /{id}/partner-stats
│   │   │                             GET /{id}/category-breakdown, GET /{id}/settlement, GET/PATCH /{id}/split-ratio
│   │   ├── subscriptions/          ← Recurring expense detection (computed view, no DB tables)
│   │   │                             GET /subscriptions/detected
│   │   ├── transactions/           ← Transaction, TransactionSplit, ProcessedWebhook, FailedJob models
│   │   │                             GET /transactions/mine, GET /transactions/shared
│   │   ├── merchants/              ← Merchant, MerchantCategorySelection models
│   │   │                             lookup_merchant() → DB cache → LLM fallback
│   │   ├── merchant_review/        ← CanonicalMerchant, MerchantReviewJob models
│   │   │                             LLM grouping (batched), review service, review API
│   │   │                             Training web UI at /train (local dev tool)
│   │   ├── notifications/          ← Notification model, CRUD service + router
│   │   │                             GET/PATCH /notifications, GET /notifications/unread-count
│   │   ├── email/                  ← EmailProvider abstraction (Gmail + Outlook)
│   │   │                             POST /webhooks/gmail, POST /webhooks/outlook
│   │   ├── whatsapp/               ← WhatsApp Cloud API sender + session state + webhook handler
│   │   │                             GET/POST /webhooks/whatsapp
│   │   ├── budgets/                ← Budget service + personal_service + allocation_service
│   │   │                             GET/POST /budgets/monthly/{household_id}
│   │   │                             GET /budgets/personal/{household_id}
│   │   │                             GET/POST /budgets/allocation/{household_id}
│   │   └── bank_connect/           ← Luka Connect integration (replaces Fintoc)
│   │       ├── encryption.py       ← AES-256-GCM encrypt/decrypt
│   │       ├── models.py           ← BankCredential model
│   │       ├── service.py          ← store/delete/decrypt creds, trigger sync
│   │       ├── mapper.py           ← movement → transaction mapping + dedup
│   │       ├── scheduler.py        ← get_due_syncs query
│   │       └── router.py           ← connect/disconnect/sync/status/webhook
│   ├── jobs/
│   │   ├── queue.py                ← ARQ enqueue helpers
│   │   └── tasks.py                ← 7 async tasks (see ARQ Jobs below)
│   ├── modules/
│   │   └── bank_accounts/              ← BankAccount CRUD
│   │       └── router.py               ← GET/POST/PATCH/DELETE /bank-accounts
│   ├── alembic/
│   │   └── versions/
│   │       ├── 001_initial_schema.py     ← All 12 tables
│   │       ├── 002_rls_policies.py       ← RLS + get_partner_stats() SECURITY DEFINER
│   │       ├── 003_fintoc_bank_account_fields.py ← fintoc_link_id, fintoc_account_id
│   │       ├── 004_account_type_constraint.py    ← CHECK constraint on account_type
│   │       └── 005_bank_account_import_status.py ← import_status column on bank_accounts
│   └── tests/                      ← 20 test files (70 passing, 7 skipped/integration)
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx              ← Root: Geist fonts + <Providers>
│   │   ├── page.tsx                ← Re-exports (dashboard)/page
│   │   ├── providers.tsx           ← TanStack QueryClientProvider (staleTime=30s)
│   │   ├── globals.css             ← Tailwind + luka-* design tokens
│   │   ├── auth/callback/route.ts  ← Supabase OAuth callback
│   │   ├── lib/
│   │   │   ├── api.ts              ← apiFetch<T> + all 8 API methods + TypeScript interfaces
│   │   │   ├── store.ts            ← Zustand: householdId, userId, userFullName, reset()
│   │   │   ├── hooks/
│   │   │   │   │   ├── useTransactions.ts      ← useMyTransactions, useSharedTransactions, useMonthlySpending
│   │   │   │   ├── useHousehold.ts         ← useHouseholdSummary, usePartnerStats, useCategoryBreakdown, useSettlement, useSplitRatio, useUpdateSplitRatio
│   │   │   │   ├── useSubscriptions.ts     ← useSubscriptions
│   │   │   │   ├── useNotifications.ts     ← useNotifications, useUnreadCount, useUpdateNotification
│   │   │   │   ├── useMerchantReview.ts    ← useMerchantReview, useReviewStatus, useApproveMerchant, useSkipReview
│   │   │   │   └── useBudget.ts            ← useBudgetStatus, useSetBudget, usePersonalBudget, useAllocation, useSaveAllocation
│   │   │   └── supabase/
│   │   │       ├── client.ts       ← Supabase browser client
│   │   │       └── server.ts       ← Supabase SSR client
│   │   ├── middleware.ts           ← Protects all routes, redirects to /login if no session
│   │   ├── (auth)/                 ← Route group (no URL prefix)
│   │   │   ├── login/page.tsx      ← Google + Microsoft OAuth buttons
│   │   │   ├── invite/[token]/page.tsx ← Accept household invite link
│   │   │   └── onboarding/
│   │   │       ├── setup-household/page.tsx
│   │   │       ├── connect-email/page.tsx
│   │   │       ├── connect-bank/page.tsx
│   │   │       └── verify-whatsapp/page.tsx
│   │   ├── (public)/              ← Public routes (no auth required)
│   │   │   ├── layout.tsx         ← Base layout for legal docs
│   │   │   ├── privacy/page.tsx   ← Privacy Policy (Chile Law 19.628)
│   │   │   ├── terms/page.tsx     ← Terms of Service
│   │   │   └── data-deletion/page.tsx ← Instructions for data removal
│   │   └── (dashboard)/            ← Route group (no URL prefix)
│   │       ├── layout.tsx          ← Sidebar (lg) + BottomNav (mobile) + <main>
│   │       ├── page.tsx            ← /  — Home: KPIs + SpendingChart + CategoryDonut + RecentTransactions
│   │       ├── transactions/
│   │       │   ├── page.tsx              ← /transactions — tabs (mine/shared) + search + ProcessingBanner
│   │       │   └── review/[jobId]/page.tsx ← Tinder-style merchant review cards
│   │       ├── notifications/page.tsx ← /notifications — review/dismiss actions
│   │       ├── household/             ← /household — hero card + category breakdown + settlement
│   │       │   ├── page.tsx
│   │       │   └── SplitRatioModal.tsx
│   │       ├── subscriptions/page.tsx ← /subscriptions — KPI cards + timeline + price alerts
│   │       ├── budgets/page.tsx       ← /budgets — pace chart, allocation editor, waterfall cards
│   │       ├── settings/
│   │       │   ├── page.tsx              ← /settings — profile, bank accounts, hogar, notifications, categories, privacy, delete
│   │       │   └── components/           ← ProfileSection, TransactionsConfigSection, BankAccountsSection, HogarSection, NotificationsSection, CategoriesSection, PrivacySection, DeleteAccountSection
│   │       └── components/
│   │           ├── Sidebar.tsx         ← Desktop nav (hidden on mobile)
│   │           ├── BottomNav.tsx       ← Mobile bottom tabs (hidden on lg+)
│   │           ├── KpiCard.tsx         ← Metric card with trend coloring
│   │           ├── SpendingChart.tsx   ← Recharts AreaChart (personal/shared)
│   │           ├── CategoryDonut.tsx   ← Recharts PieChart donut
│   │           ├── RecentTransactions.tsx ← Transaction list with split badges
│   │           ├── PaceChart.tsx              ← Recharts LineChart: actual spending vs pace line
│   │           ├── AllocationCard.tsx         ← Dual sliders (Hogar/Ahorro), Personal read-only, suggestion pills
│   │           ├── WaterfallCards.tsx         ← Household + Personal budget cards with progress bars
│   │           ├── StoreInitializer.tsx       ← Calls GET /auth/me on mount, populates Zustand
│   │           └── SessionGuard.tsx            ← PWA: persistent session + token refresh; Browser: 30min inactivity timeout
│   ├── components/ui/              ← shadcn/ui: badge, button, card, input, tabs, table, separator, avatar, bottom-sheet
│   └── lib/utils.ts                ← cn() Tailwind class merger
│
└── docs/superpowers/
    ├── specs/2026-03-10-finanzas-personales-design.md  ← Full system design
    ├── plans/2026-03-10-luka-plan-1-foundation.md      ← ✅ Complete
    ├── plans/2026-03-10-luka-plan-2-transaction-pipeline.md ← ✅ Complete
    ├── plans/2026-03-10-luka-plan-3-household-logic.md ← ✅ Complete
    ├── plans/2026-03-10-luka-plan-4-frontend-dashboard.md  ← ✅ Complete
    └── 2026-03-16-luka-project-state.md               ← This document
```

---

## Database Schema (15 tables)

```sql
users              — id, email, full_name, phone_whatsapp, whatsapp_verified, preferred_currency,
                     email_provider, mail_watch_subscription_id (Outlook), mail_watch_expiry,
                     google_access_token_enc, google_refresh_token_enc

households         — id, name, type ('individual'|'couple'), split_ratio (JSONB, default [50,50])

household_members  — id, household_id, user_id, role ('owner'|'member')

household_invites  — id, household_id, invited_by, invited_email,
                     token, expires_at, accepted_at

bank_accounts      — id, household_id, user_id, bank_name, account_type
                     ('personal'|'joint'), email_sender_pattern,
                     account_kind, account_number, currency, is_active

bank_credentials   — id, user_id, bank_code, encrypted_rut, encrypted_password,
                     encryption_iv, next_sync_at, last_sync_at, last_sync_status,
                     current_job_id  (RLS: user_id = auth.uid())

household_budgets  — id, household_id, bank_account_id, month (DATE),
                     budgeted (Numeric), source

merchants          — id, raw_name (UNIQUE), normalized_name,
                     llm_suggested_categories (JSON), total_selections,
                     canonical_merchant_id (FK canonical_merchants, nullable)

canonical_merchants — id, display_name (UNIQUE), default_category, logo_url,
                     is_verified, review_job_id (FK merchant_review_jobs)

notifications      — id, user_id (FK users), type, title, payload (JSONB),
                     status ('unread'|'read'|'dismissed'|'actioned'), read_at

merchant_review_jobs — id, user_id (FK users), bank_credential_id (FK bank_credentials),
                     status ('processing'|'ready'|'completed'|'skipped'|'failed'),
                     total_merchants, reviewed_count, notification_id (FK notifications)

merchant_category_selections — id, merchant_id, category, count, last_used_at

transactions       — id, user_id, household_id, bank_account_id, merchant_id,
                     amount, currency, transaction_date, category,
                     status ('pending'|'settled'), source, source_type ('email'|'connect'|'manual'),
                     transaction_type ('expense'|'income'|'transfer'),
                     transfer_to_account_id (FK bank_accounts, nullable),
                     source_bank_name (inferred from email sender domain),
                     raw_email_text (purged after 24h)

household_budget_allocations — id, household_id, month (DATE UNIQUE per household),
                     hogar_pct, ahorro_pct, personal_pct, created_at

transaction_splits — id, transaction_id, split_type ('personal'|'partner'|'shared'),
                     category, decided_by_user_id, whatsapp_message_id, decided_at

notification_preferences — user_id (PK, FK users), whatsapp_enabled

user_category_preferences — id, user_id, category, sort_order, hidden
                     UNIQUE(user_id, category)

processed_webhooks — message_id (PK), processed_at  ← idempotency

failed_jobs        — id, job_name, payload (JSON), error_message, attempt_count
```

**RLS policies (migration 002):**
- `own_transactions`: SELECT where `user_id = auth.uid()`
- `shared_transactions`: SELECT for household members on shared splits
- `get_partner_stats(household_id, viewer_id, month)`: SECURITY DEFINER — returns only `{total_spent, by_category[]}`, never raw partner rows

---

## API Endpoints

```
GET  /health                                → {"status":"ok","app":"luka"}

GET  /auth/me                               → current user (includes phone_whatsapp)
PATCH /auth/me                              → update profile (full_name, phone_whatsapp, preferred_currency)
DELETE /auth/me                             → delete account (requires X-Confirm-Delete: ELIMINAR)
POST /auth/store-provider-tokens           → store encrypted Google OAuth tokens
POST /auth/setup-email-watch              → activate Gmail Pub/Sub watch for current user
POST /auth/send-whatsapp-pin              → send 6-digit PIN to phone via WhatsApp
POST /auth/verify-whatsapp-pin            → verify PIN, set whatsapp_verified=True

GET  /notifications/preferences            → get notification preferences (auto-creates default)
PATCH /notifications/preferences           → update notification preferences (whatsapp_enabled)
GET  /categories/preferences               → get category sort/hide preferences
PUT  /categories/preferences               → replace all category preferences

POST /households/                           → create household
POST /households/{id}/invite               → invite partner by email
GET  /households/{id}/summary              → member contributions (own data only)
GET  /households/{id}/partner-stats        → partner aggregate via SECURITY DEFINER RPC

GET  /transactions/mine?since=YYYY-MM-DD   → current user's transactions (default: 6 months, no row cap)
GET  /transactions/shared?household_id=X&since=YYYY-MM-DD → shared household transactions
GET  /transactions/monthly-summary?household_id=X → last 6 months aggregated (personal + shared)
GET  /transactions/pending              → pending email txns grouped: awaiting_reconciliation + unmatched_email
PATCH /transactions/{id}/category      → update category + train merchant_category_selections
DELETE /transactions/{id}              → hard-delete pending email transaction (deletes splits first)

GET  /budgets/monthly/{id}?month=YYYY-MM   → budget status
POST /budgets/monthly/{id}                 → set monthly budget
GET  /budgets/personal/{id}?month=YYYY-MM-DD → income, pace chart, household + personal waterfall
GET  /budgets/allocation/{id}?month=YYYY-MM-DD → current allocation + suggestions
POST /budgets/allocation/{id}              → upsert allocation (hogar_pct, ahorro_pct, personal_pct)

GET  /bank-accounts                         → list user's bank accounts
POST /bank-accounts                         → create bank account
PATCH /bank-accounts/{id}                   → update bank account
DELETE /bank-accounts/{id}                  → delete bank account

POST /bank-connect/connect                  → store encrypted creds + trigger initial async sync
DELETE /bank-connect/disconnect?bank_code=X → hard delete credentials
POST /bank-connect/sync?bank_code=X        → manual sync trigger (async with callback)
GET  /bank-connect/sync-status?bank_code=X → poll sync progress
GET  /bank-connect/connections              → list connected banks
POST /bank-connect/webhooks/luka-connect   → callback from Luka Connect service

POST /webhooks/gmail                        → Gmail push notification
POST /webhooks/outlook                      → Outlook push notification
GET  /webhooks/whatsapp                    → WhatsApp verify webhook
POST /webhooks/whatsapp                    → WhatsApp message receive
```

---

## ARQ Jobs

| Job | Trigger | What it does |
|-----|---------|-------------|
| `process_email` | On-demand (enqueued by webhook) | Fetch email → parse bank amount/merchant → lookup_merchant() → create Transaction+TransactionSplit → save WhatsApp session → send WhatsApp alert |
| `renew_mail_watches` | Cron 3am daily | Renew Gmail (7d expiry) and Outlook (3d expiry) subscriptions |
| `purge_raw_emails` | Cron hourly | Set `raw_email_text = NULL` on transactions >24h old |
| `cleanup_processed_webhooks` | Cron 4am daily | Delete idempotency records >7 days |
| `schedule_connect_syncs` | Cron hourly | Find users due for daily bank sync, enqueue `run_connect_sync` for each |
| `run_connect_sync` | On-demand (enqueued by scheduler) | Send WhatsApp 2FA nudge, call Luka Connect async with callback |

---

## Design System (Tailwind tokens)

Defined in `frontend/app/globals.css` via `@theme inline`:

```
luka-primary  = #2563EB  (blue — active states, buttons, bars)
luka-light    = #EFF6FF  (page background, inactive hover)
luka-sky      = #38BDF8  (shared/secondary data series)
luka-dark     = #0F172A  (headings, primary text)
luka-muted    = #64748B  (secondary text, labels)
luka-success  = #10B981  (positive trends, available balance)
luka-danger   = #EF4444  (budget exceeded, sign-out button)
```

---

## Key Architectural Decisions

1. **EmailProvider abstraction** — `GmailProvider` and `OutlookProvider` share the same `EmailProvider` interface; `get_email_provider()` factory selects by `email_provider` field on User.

2. **ARQ webhook ACK pattern** — Webhooks acknowledge in <200ms, enqueue `process_email` job to ARQ; all heavy work is async in the worker process.

3. **WhatsApp session state** — Redis key `wa_session:{phone}:{txn_id}` holds multi-turn conversation state. Txn ID embedded in button/list IDs for concurrent message support.

4. **Joint account auto-split** — `bank_accounts.account_type == 'joint'` → transaction auto-classified as `shared`, skip WhatsApp split question.

5. **Partner privacy** — `get_partner_stats()` PostgreSQL SECURITY DEFINER function: membership guard at the top, returns only aggregates, no raw partner transaction rows ever leave the DB.

6. **Merchant learning** — Global `merchants` table shared across all users. LLM categorizes on first encounter, frequency of user selections improves future suggestions.

7. **Luka Connect** — Standalone bank scraping service (separate repo `luka-connect`). Replaces Fintoc. Node.js/Express + Puppeteer + Chromium. Deployed on its own Railway project. Stateless — credentials managed by Luka backend, encrypted with AES-256-GCM.

8. **No ledger/debt table** — Contribution transparency via aggregate query on transactions. No debt tracking between partners.

9. **Store reset on sign-out** — Zustand `reset()` called in `finally` block so stale householdId/userId never persists across sessions.

10. **Session management (PWA-aware)** — `SessionGuard` detects PWA via `display-mode: standalone`. PWA mode: persistent session, token refresh via `getUser()` on app resume (visibilitychange), refresh token saved to localStorage on every mount as backup for iOS cookie eviction. Browser mode: 30-minute inactivity timeout with activity tracking. Fresh-login cookie (`luka-fresh-login`, 60s TTL) prevents stale localStorage timestamp from triggering false sign-out after OAuth. Login page auto-recovers PWA sessions via `refreshSession()` from localStorage backup.

11. **User auto-provisioning** — `get_current_user()` in `security.py` auto-creates the `users` row on first authenticated request using Supabase JWT metadata (name, email, OAuth provider). No separate signup endpoint needed.

12. **Bank connect flow** — User enters RUT + password in onboarding modal → backend encrypts with AES-256-GCM → calls Luka Connect `/scrape` → user approves 2FA on phone → Luka Connect callbacks with movements → backend maps + dedup + reconciles with email txns.

13. **asyncpg compatibility** — `statement_cache_size=0` set on async engine to handle Supabase's PgBouncer transaction-mode pooler which doesn't support named prepared statements.

---

## Environment Variables Required

All loaded via Pydantic Settings from `.env`:

```env
# Database (Supabase)
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# Job Queue
REDIS_URL=redis://...

# Gmail (Google Cloud Pub/Sub)
GCP_PROJECT_ID=luka-490500
PUBSUB_AUDIENCE=https://luka-production-eb87.up.railway.app/webhooks/gmail
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
TOKEN_ENCRYPTION_KEY=...  # Fernet key for encrypting Google OAuth tokens

# Outlook (Microsoft Graph)
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
OUTLOOK_CLIENT_STATE=<random-secret>

# WhatsApp Cloud API
WHATSAPP_APP_SECRET=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...

# Luka Connect (bank scraping service)
LUKA_CONNECT_URL=https://<luka-connect-railway-url>
LUKA_CONNECT_API_KEY=<shared API key>
CONNECT_ENCRYPTION_KEY=<64-char hex, generate: python3 -c "import secrets; print(secrets.token_hex(32))">
BACKEND_PUBLIC_URL=https://luka-production-eb87.up.railway.app

# LLM
GEMINI_API_KEY=...   # Google AI Studio (Gemini 2.5 Flash-Lite)
OPENAI_API_KEY=...   # Legacy — no longer used, kept for cleanup

# App
FRONTEND_URL=https://your-app.vercel.app
ENVIRONMENT=production
```

---

## Test Coverage

```
backend/tests/          138 passing, 7 skipped (require live DB)

test_auth.py            ← Auth middleware
test_budget_allocation_service.py ← Allocation suggestions (default, historical, rounding)
test_budget_personal_service.py   ← Personal ceiling, pace, breakdown (waterfall + allocation modes)
test_budgets_api.py     ← Budget endpoints (1 skipped: live DB)
test_email_parser.py    ← Regex parsing for Chilean bank emails
test_email_webhooks.py  ← Gmail + Outlook webhook handlers
test_bank_connect_encryption.py ← AES-256-GCM encrypt/decrypt roundtrip (3 tests)
test_bank_connect_mapper.py    ← Movement→transaction mapping + dedup key (7 tests)
test_health.py          ← Health check
test_household_privacy.py ← RLS policies (2 skipped: live DB)
test_households.py      ← Create/invite (3 skipped: live DB)
test_merchant_llm.py    ← LLM categorization mock
test_merchant_normalizer.py ← Name normalization rules
test_merchant_service.py ← Lookup caching logic
test_migrations.py      ← Alembic migration chain (1 skipped: live DB)
test_transactions_api.py ← GET /mine, GET /shared
test_whatsapp_sender.py ← Message generation
test_whatsapp_webhook.py ← Webhook HMAC + flow handling
test_notifications_api.py ← Notification CRUD endpoints (4 tests)
test_llm_grouping.py     ← LLM grouping + fallback (3 tests)
test_canonical_merchants.py ← Canonical merchant creation (1 test)
test_merchant_review_api.py ← Review API endpoints (3 tests)
```

---

## What Is NOT Yet Implemented

| Gap | Impact | Notes |
|-----|--------|-------|
| WhatsApp Integration | ✅ DONE | Cloud API verified in Live Mode. Webhook listener and sender functional. |
| Frontend Redesign Tier 1 | ✅ DONE | DM Sans, card-based transactions, bottom sheets, collapsible filters, mobile-first |
| Frontend Redesign Tier 2 | ✅ DONE | Settings page (7 sections), login/onboarding polish, invite flow with self-invite protection |
| Google OAuth token storage | ✅ DONE | Fernet-encrypted tokens in users table (google_access_token_enc, google_refresh_token_enc) |
| Resend email integration | ✅ DONE | Transactional emails via Resend HTTP API (Railway blocks outbound SMTP) |
| Email watch setup | ✅ DONE | Gmail Pub/Sub watch live, OIDC auth working, fallback fetch when History API empty |
| WhatsApp PIN verification | ✅ DONE | Send/verify PIN via Redis (5-min TTL), brute-force protection (5 attempts) |
| Email pipeline end-to-end | ✅ DONE | Gmail → Pub/Sub → webhook → ARQ worker → fetch email → WhatsApp notification |
| Email pre-filter | ✅ DONE | 27 Spanish + 20 English financial keywords, 60+ bank sender domains (Chile + US), bank name inference from sender |
| Email parser HTML support | ✅ DONE | Strips HTML before regex. CLP + USD amount parsing, English date formats, transfer recipient extraction, "Where:" merchant patterns |
| Gemini LLM classification | ✅ DONE | Gemini 2.5 Flash-Lite (replaced OpenAI gpt-4o-mini). 3 categories for new merchants, 1 for known. Lazy client init, code-fence stripping |
| WhatsApp transaction flow | ✅ DONE | Split question → category picker → ✅ confirmation. Txn ID embedded in button/list IDs for concurrent message support. |
| Email-only users | ✅ DONE | Bank account not required — household resolved from HouseholdMember. Bank name inferred from sender domain (source_bank_name column). |
| Transaction dedup | ✅ DONE | Per-email Redis key `txn_processed:{message_id}` (24h TTL) |
| Merchant race condition | ✅ DONE | IntegrityError on duplicate insert → rollback + re-query existing row |
| Luka Connect deployment | ✅ DONE | Deployed on Railway, scraping 301 movements in ~4 min, 291 transactions imported |
| Migration 017 on production | ✅ DONE | Fintoc columns dropped, bank_credentials + source_type added |
| Luka Connect backend env vars | ✅ DONE | All 4 env vars set on Railway |
| Auto-create bank accounts from scrape | ✅ DONE | ensure_accounts() creates/updates accounts from movements, creditCards, allBalances |
| Store balances from scrape | ✅ DONE | balance_current, balance_limit stored per account, updated on each sync |
| Link transactions to bank accounts | ✅ DONE | Transactions linked via bank_account_id during scrape ingestion |
| Show bank/account on transaction rows | ✅ DONE | Transaction cards show bank name |
| Transaction splits for scraped txns | ✅ DONE | Luka Connect scraping now creates personal splits; account type change backfills missing splits |
| Currency preference | ✅ DONE | Migration 021, PATCH /auth/me, TransactionsConfigSection in settings, tx page reads preference |
| Banco Falabella | ✅ DONE | Enabled in frontend + backend BANK_NAMES, no 2FA |
| Multi-bank parser | ⚠️ PARTIAL | Banco de Chile (compra+comprobante+transfer), Edwards (incoming transfer), Santander (outgoing transfer), BofA (credit card alert). Falabella, BCI, Estado still need email samples |
| Transaction dedup (cross-sender) | ✅ DONE | 5-min window dedup by amount+user prevents BChile compra+comprobante double entry |
| PendingBlock UI | ✅ DONE | Matches regular card style (gradient icon, bank name, email tag). USD formatting (US$17.08). Inline category + split-type dropdowns. Hidden icon on mobile. |
| WhatsApp labels aligned | ✅ DONE | Split buttons now say Personal/Hogar matching dashboard; LLM constrained to fixed category list |
| Household category breakdown | ✅ DONE | Per-category spending table with mini proportion bars, member amounts + %, sorted by total |
| Settlement suggestions | ✅ DONE | "X debe transferir $Y a Z" based on configurable split ratio (default 50/50) |
| Split ratio config | ✅ DONE | PATCH endpoint + modal UI, stores in households.split_ratio JSONB column (migration 019) |
| Subscriptions auto-detection | ✅ DONE | Groups by merchant, 2+ consecutive months, 20% amount tolerance, predicts next charge date |
| Subscriptions timeline UI | ✅ DONE | KPI cards + vertical timeline with predicted dates + price change alerts (yellow banners) |
| Subscriptions nav item | ✅ DONE | "Suscripciones" in sidebar (after Presupuesto) + "Suscrip." in mobile bottom nav |
| Merchant cleaning & review pipeline | ✅ DONE | LLM groups raw names → canonical merchants → user review (Tinder cards). Notifications drive user to review. CLI + web training UI at /train |
| Canonical merchant display_name | ✅ DONE | Transactions show clean display_name via canonical merchant join, fallback to raw_merchant_name |
| Notification system | ✅ DONE | Backend CRUD, unread badge in sidebar/bottom nav, notifications page with review/dismiss |
| Email domain for Resend | Low | Currently sends from onboarding@resend.dev — custom domain needed for production emails |
| Alembic auto-run on Railway | Low | Run manually: `cd backend && python3 -m alembic upgrade head` |

---

## Deployment

**Backend (Railway):** ✅ LIVE
- URL: `https://luka-production-eb87.up.railway.app`
- Configured via `backend/railway.toml`
- Entry: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Worker: separate Railway service running `arq worker.WorkerSettings`
- Redis: Railway add-on (auto-injects `REDIS_URL`)
- `/health` returns `{"status":"ok","app":"luka"}`

**Frontend (Vercel):** ✅ LIVE
- URL: `https://luka-lovat.vercel.app`
- Root: `frontend/`
- Framework: Next.js (auto-detected)
- Environment vars set: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Supabase redirect URL configured: `https://luka-lovat.vercel.app/auth/callback`

**Luka Connect (Railway):** ✅ LIVE
- URL: `https://luka-connect-production.up.railway.app`
- Repo: `rlabrao96/luka-connect` (GitHub, private)
- Dockerfile with Chromium + Xvfb, auto-deploy on push
- `/health` returns `{"status":"ok","chromium":true}`

**Database (Supabase):** ✅ LIVE
- All 21 migrations applied (`021 head`)
- Migration 009 adds `last_synced_at` and `import_started_at` to `bank_accounts`
- Migration 010 adds bank account settings overhaul columns
- Migration 011 adds `transaction_type`, `transfer_to_account_id`, `household_budget_allocations`
- Project: `mvovcodijqjvzxxthsxg.supabase.co`
- Note: migrations must be run manually via local `python3 -m alembic upgrade head` (Railway releaseCommand was unreliable)
