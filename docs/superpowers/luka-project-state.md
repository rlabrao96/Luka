# Luka — Project State Document
**Date:** 2026-03-18
**Status:** All 4 implementation plans complete + all critical gaps closed. App is LIVE in production (Railway + Vercel). Awaiting WhatsApp/Gmail/Outlook credentials to enable email capture pipeline.

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
│   │   └── security.py            ← Supabase JWT validation, get_current_user()
│   ├── modules/
│   │   ├── auth/                   ← User model + GET /auth/me
│   │   ├── households/             ← Household, Member, Invite, BankAccount, Budget models
│   │   │                             POST /, POST /{id}/invite, GET /{id}/summary, GET /{id}/partner-stats
│   │   ├── transactions/           ← Transaction, TransactionSplit, ProcessedWebhook, FailedJob models
│   │   │                             GET /transactions/mine, GET /transactions/shared
│   │   ├── merchants/              ← Merchant, MerchantCategorySelection models
│   │   │                             lookup_merchant() → DB cache → LLM fallback
│   │   ├── email/                  ← EmailProvider abstraction (Gmail + Outlook)
│   │   │                             POST /webhooks/gmail, POST /webhooks/outlook
│   │   ├── whatsapp/               ← WhatsApp Cloud API sender + session state + webhook handler
│   │   │                             GET/POST /webhooks/whatsapp
│   │   ├── budgets/                ← Budget service + GET/POST /budgets/monthly/{household_id}
│   │   └── fintoc/                 ← FintocClient + reconcile_transactions()
│   ├── jobs/
│   │   ├── queue.py                ← ARQ enqueue helpers
│   │   └── tasks.py                ← 5 async tasks (see ARQ Jobs below)
│   ├── alembic/
│   │   └── versions/
│   │       ├── 001_initial_schema.py     ← All 12 tables
│   │       ├── 002_rls_policies.py       ← RLS + get_partner_stats() SECURITY DEFINER
│   │       └── 003_fintoc_bank_account_fields.py ← fintoc_link_id, fintoc_account_id
│   └── tests/                      ← 17 test files (31 passing, 7 skipped/integration)
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
│   │   │   │   ├── useTransactions.ts  ← useMyTransactions, useSharedTransactions, useMonthlySpending
│   │   │   │   ├── useHousehold.ts     ← useHouseholdSummary, usePartnerStats
│   │   │   │   └── useBudget.ts        ← useBudgetStatus, useSetBudget
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
│   │   └── (dashboard)/            ← Route group (no URL prefix)
│   │       ├── layout.tsx          ← Sidebar (lg) + BottomNav (mobile) + <main>
│   │       ├── page.tsx            ← /  — Home: KPIs + SpendingChart + CategoryDonut + RecentTransactions
│   │       ├── transactions/page.tsx  ← /transactions — tabs (mine/shared) + search
│   │       ├── household/page.tsx     ← /household — contribution bars + partner stats
│   │       ├── budgets/page.tsx       ← /budgets — joint account progress bar
│   │       ├── settings/page.tsx      ← /settings — sign-out + privacy disclosure
│   │       └── components/
│   │           ├── Sidebar.tsx         ← Desktop nav (hidden on mobile)
│   │           ├── BottomNav.tsx       ← Mobile bottom tabs (hidden on lg+)
│   │           ├── KpiCard.tsx         ← Metric card with trend coloring
│   │           ├── SpendingChart.tsx   ← Recharts AreaChart (personal/shared)
│   │           ├── CategoryDonut.tsx   ← Recharts PieChart donut
│   │           ├── RecentTransactions.tsx ← Transaction list with split badges
│   │           ├── StoreInitializer.tsx   ← Calls GET /auth/me on mount, populates Zustand
│   │           └── InactivityGuard.tsx    ← Auto-logout after 1h inactivity
│   ├── components/ui/              ← shadcn/ui: badge, button, card, input, tabs, table, separator, avatar
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

## Database Schema (12 tables)

```sql
users              — id, email, full_name, whatsapp_verified, email_provider,
                     mail_watch_subscription_id (Outlook), mail_watch_expiry

households         — id, name, type ('individual'|'couple')

household_members  — id, household_id, user_id, role ('owner'|'member')

household_invites  — id, household_id, invited_by, invited_email,
                     token, expires_at, accepted_at

bank_accounts      — id, household_id, user_id, bank_name, account_type
                     ('personal'|'joint'), email_sender_pattern,
                     fintoc_link_id (nullable), fintoc_account_id (nullable)

household_budgets  — id, household_id, bank_account_id, month (DATE),
                     budgeted (Numeric), source

merchants          — id, raw_name (UNIQUE), normalized_name,
                     llm_suggested_categories (JSON), total_selections

merchant_category_selections — id, merchant_id, category, count, last_used_at

transactions       — id, user_id, household_id, bank_account_id, merchant_id,
                     amount, currency, transaction_date, category,
                     status ('pending'|'reconciled'), source, fintoc_id,
                     raw_email_text (purged after 24h)

transaction_splits — id, transaction_id, split_type ('personal'|'partner'|'shared'),
                     category, decided_by_user_id, whatsapp_message_id, decided_at

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

GET  /auth/me                               → current user

POST /households/                           → create household
POST /households/{id}/invite               → invite partner by email
GET  /households/{id}/summary              → member contributions (own data only)
GET  /households/{id}/partner-stats        → partner aggregate via SECURITY DEFINER RPC

GET  /transactions/mine?limit=N            → current user's transactions
GET  /transactions/shared?household_id=X   → shared household transactions
GET  /transactions/monthly-summary?household_id=X → last 6 months aggregated (personal + shared)

GET  /budgets/monthly/{id}?month=YYYY-MM   → budget status
POST /budgets/monthly/{id}                 → set monthly budget

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
| `run_fintoc_sync` | Cron 2am nightly | Fetch settled Fintoc txns → reconcile vs pending by amount + date±3d + fuzzy merchant ≥70% |

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

3. **WhatsApp session state** — Redis key `whatsapp:session:{phone}` holds multi-turn conversation state (pending transaction, which step the user is on).

4. **Joint account auto-split** — `bank_accounts.account_type == 'joint'` → transaction auto-classified as `shared`, skip WhatsApp split question.

5. **Partner privacy** — `get_partner_stats()` PostgreSQL SECURITY DEFINER function: membership guard at the top, returns only aggregates, no raw partner transaction rows ever leave the DB.

6. **Merchant learning** — Global `merchants` table shared across all users. LLM categorizes on first encounter, frequency of user selections improves future suggestions.

7. **Fintoc reconciliation** — Matches email-parsed pending transactions to Fintoc-settled transactions using: exact amount match → ±3 day date window → rapidfuzz partial_ratio ≥ 70% on merchant name.

8. **No ledger/debt table** — Contribution transparency via aggregate query on transactions. No debt tracking between partners.

9. **Store reset on sign-out** — Zustand `reset()` called in `finally` block so stale householdId/userId never persists across sessions.

10. **Inactivity auto-logout** — `InactivityGuard` tracks activity events and signs out after 1h idle. Uses `localStorage` timestamp so closing and reopening the browser after 1h also triggers sign-out on return.

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
GCP_PROJECT_ID=luka-project
PUBSUB_AUDIENCE=https://your-domain/webhooks/gmail

# Outlook (Microsoft Graph)
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
OUTLOOK_CLIENT_STATE=<random-secret>

# WhatsApp Cloud API
WHATSAPP_APP_SECRET=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...

# Fintoc
FINTOC_API_KEY=...

# LLM
OPENAI_API_KEY=...

# App
FRONTEND_URL=https://your-app.vercel.app
ENVIRONMENT=production
```

---

## Test Coverage

```
backend/tests/          31 passing, 7 skipped (require live DB)

test_auth.py            ← Auth middleware
test_budgets_api.py     ← Budget endpoints (1 skipped: live DB)
test_email_parser.py    ← Regex parsing for Chilean bank emails
test_email_webhooks.py  ← Gmail + Outlook webhook handlers
test_fintoc_reconciler.py ← Reconciliation engine (exact, window, fuzzy, no-match)
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
```

---

## What Is NOT Yet Implemented

| Gap | Impact | Notes |
|-----|--------|-------|
| WhatsApp PIN verify | Low | Onboarding step exists in UI, backend logic not fully wired. Blocked on WhatsApp credentials. |
| Email watch setup | Medium | Onboarding connects email — initial watch setup needs triggering once after first login. Blocked on GCP/Azure credentials. |
| Fintoc OAuth link flow | Medium | FintocClient exists, cron job exists. Missing: UI flow for user to authorize Fintoc and store `fintoc_link_id` |
| Vault integration | Low | Supabase Vault for OAuth tokens (noted in design spec, not wired) — optional hardening |
| Google/Microsoft OAuth login | Blocking for real users | GCP OAuth credentials not yet configured in Supabase |

---

## Deployment

**Backend (Railway):** ✅ LIVE
- URL: `https://luka-production-14f5.up.railway.app`
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

**Database (Supabase):** ✅ LIVE
- All 3 migrations applied (`alembic upgrade head` — confirmed at `003 head`)
- Project: `mvovcodijqjvzxxthsxg.supabase.co`
