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
- 13 routers registered (auth, transactions, households, budgets, bank_accounts, bank_connect, plaid, subscriptions, notifications, settings, merchant_review, email webhooks, whatsapp webhooks)
- CacheHeaderMiddleware: `private, max-age=30` on GET endpoints
- CORS: configured from `settings.cors_origins` env var
- Health check: `GET /health`
- Talks to: PostgreSQL, Redis, Supabase Auth

### Fast Worker (`backend/worker.py:FastWorkerSettings`)
- Handles: email processing, invite emails, cron jobs
- Config: max_jobs=20, job_timeout=60s
- Queue: `arq:queue` (default)
- Cron jobs: mail watch renewal (3am), raw email purge (hourly), webhook cleanup (4am), bank connect syncs (6h), subscription cache (5:30am), Plaid syncs (3:30am)

### Slow Worker (`backend/worker.py:SlowWorkerSettings`)
- Handles: bank syncs (Connect + Plaid), LLM merchant review, reconciliation
- Config: max_jobs=5, job_timeout=600s
- Queue: `arq:queue:slow`
- Cron: reconciliation job (6am daily)
- Routing: jobs in `SLOW_JOBS` set in `backend/jobs/queue.py` → slow queue

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
| `users` | User accounts, profile, encrypted OAuth tokens | → household_members, transactions |
| `households` | Shared financial unit (individual/couple) | → household_members, bank_accounts, budgets |
| `household_members` | User↔household junction (role: owner/member) | → users, households |
| `household_invites` | Invitation tokens with expiry | → households |
| `transactions` | Core financial records | → users, households, bank_accounts, merchants |
| `transaction_splits` | Per-tx split info (personal/partner/shared) | → transactions |
| `bank_accounts` | Connected accounts with sync state | → households, users |
| `merchants` | Raw merchant names → canonical mapping | → canonical_merchants |
| `canonical_merchants` | Verified merchant entities | ← merchants |
| `merchant_category_selections` | User category choices per merchant | → merchants, users |
| `household_budgets` | Monthly budget per account | → households, bank_accounts |
| `category_budgets` | Per-category monthly limits | → household_budgets |
| `household_budget_allocations` | Split % (hogar/ahorro/personal) | → households |
| `bank_credentials` | AES-256-GCM encrypted Luka Connect creds | → users |
| `plaid_items` | Plaid connection state per user | → users |
| `notifications` | In-app notifications | → users |
| `notification_preferences` | WhatsApp toggle per user | → users |
| `user_category_preferences` | Custom category ordering | → users |
| `processed_webhooks` | Idempotency tracking | — |
| `failed_jobs` | Failed job logging | — |
| `merchant_review_jobs` | Async LLM review batches | → users |

### Key Relationships
- A user belongs to one household via `household_members`
- Transactions belong to a user + household + optional bank_account + optional merchant
- Bank accounts belong to a household, linked to a user
- Budget hierarchy: household → household_budgets → category_budgets

## Key Flows

### Email Transaction Flow
1. Gmail/Outlook sends push notification → `POST /webhooks/gmail` or `/webhooks/outlook`
2. Webhook handler ACKs immediately (<200ms), enqueues `process_email` to fast worker
3. Worker fetches email via Gmail API / Microsoft Graph (auto-refreshes OAuth tokens)
4. Pre-filter: 27 Spanish financial keywords → if match, parse transaction data from HTML
5. Dedup: Redis-based per-email (24h TTL) + cross-sender 5-minute window
6. Merchant lookup: known → instant category, new → 3 LLM suggestions (Gemini)
7. Transaction saved with status `pending_email`
8. WhatsApp notification sent to user with split type buttons

### WhatsApp Conversational Flow
1. User receives transaction alert with interactive buttons
2. User picks split type (Personal/Hogar/Pareja)
3. Category picker presented (inline keyboard)
4. User confirms → transaction_split created, status updated
5. Manual expense: user sends natural language → parsed into transaction

### Bank Sync Flow (Luka Connect)
1. User enters bank credentials → encrypted (AES-256-GCM) → stored in `bank_credentials`
2. `schedule_connect_syncs` cron (every 6h) enqueues `run_connect_sync` for each credential
3. Slow worker calls Luka Connect API → scraper fetches transactions
4. Mapper deduplicates + maps to Luka transaction format → saved to DB
5. Reconciliation job (6am daily) matches email and bank-sourced transactions

### Plaid Sync Flow
1. User connects via Plaid Link widget → public token exchanged for access token
2. `schedule_plaid_syncs` cron (3:30am daily) enqueues `run_plaid_sync_job`
3. Slow worker calls Plaid Sync API with cursor pagination
4. Mapper detects account kind, maps Plaid transactions → saved to DB

### Reconciliation Flow
1. `run_reconciliation_job` cron (6am daily) scans recent bank-sourced transactions
2. For each bank tx, `find_email_match()` uses 3-tier priority matching:
   - **Exact:** same merchant (ilike), ±2 days, 0% amount tolerance
   - **Fuzzy:** ±3 days, 30% amount tolerance
   - **Sum match:** N email txs from same merchant whose amounts sum to bank tx (5% tolerance)
3. On match: copies merchant_id, category, transaction_type from email tx → bank tx; re-links splits; deletes email tx
4. `detect_transfers()` finds same-amount opposite-sign pairs across accounts within ±2 days, marks both as transfer

### Encryption
- **Fernet** (`backend/core/encryption.py`): symmetric encryption for OAuth provider tokens (Google, Microsoft)
- **AES-256-GCM** (`backend/modules/bank_connect/encryption.py`): bank credentials (RUT + password), 12-byte random nonce per field

## Authentication & Authorization

- **Provider:** Supabase Auth (Google OAuth for Gmail users, Microsoft OAuth for Outlook users)
- **Token strategy:** JWT validated locally via PyJWT + JWKS (ES256 primary, RS256/HS256 fallback)
- **Frontend:** Supabase JS SDK handles token refresh; `middleware.ts` redirects unauthenticated users
- **Backend:** `get_current_user()` dependency validates JWT, caches user profile in Redis (5-min TTL)
- **Session management:** SessionGuard component — PWA persistent sessions + 30-min browser inactivity timeout with visibility change detection
- **RLS:** Supabase Row Level Security on sensitive tables; SECURITY DEFINER aggregate RPC for partner data (no raw partner rows exposed)
- **OAuth tokens:** Google/Microsoft provider tokens encrypted with Fernet, stored in `users` table for API access (Gmail, Graph)

## Background Processing

### Worker Architecture
Two ARQ worker processes deployed as separate Railway services:

| Worker | Queue | Max Jobs | Timeout | Purpose |
|--------|-------|----------|---------|---------|
| Fast | `arq:queue` | 20 | 60s | Email processing, invite emails, cron scheduling |
| Slow | `arq:queue:slow` | 5 | 600s | Bank syncs, LLM review, reconciliation |

Routing logic in `backend/jobs/queue.py`: jobs listed in `SLOW_JOBS` set are enqueued to slow queue.

### Cron Jobs

| Job | Schedule | Worker | Purpose |
|-----|----------|--------|---------|
| `renew_mail_watches` | 3:00 AM daily | Fast | Refresh Gmail watch subscriptions (7-day expiry) |
| `purge_raw_emails` | Hourly | Fast | Clean old email data |
| `cleanup_processed_webhooks` | 4:00 AM daily | Fast | Remove webhook dedup records |
| `schedule_connect_syncs` | Every 6h | Fast | Enqueue Luka Connect sync jobs |
| `refresh_subscriptions_cache` | 5:30 AM daily | Fast | Pre-compute recurring transaction patterns |
| `schedule_plaid_syncs` | 3:30 AM daily | Fast | Enqueue Plaid sync jobs |
| `run_reconciliation_job` | 6:00 AM daily | Slow | Match email + bank transactions |

### Async Tasks

| Task | Queue | Description |
|------|-------|-------------|
| `process_email` | Fast | Fetch email → parse → categorize → save → WhatsApp alert |
| `send_invite_email` | Fast | Format and send household invite via Resend/SMTP |
| `run_connect_sync` | Slow | Pull transactions from Luka Connect scraper |
| `run_plaid_sync_job` | Slow | Sync US bank via Plaid API |
| `process_merchant_review` | Slow | LLM-batch group unverified merchants |

## External Integrations

| Service | Purpose | Config |
|---------|---------|--------|
| **Google Cloud Pub/Sub** | Gmail push notifications (real-time email alerts) | `GCP_PROJECT_ID`, OIDC auth, topic: `luka-gmail-notifications` |
| **Gmail API** | Fetch email content, manage watch subscriptions | OAuth tokens stored encrypted in users table |
| **Microsoft Graph** | Outlook email fetch + webhook subscriptions | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` |
| **WhatsApp Cloud API** | Transaction alerts + conversational split flow | `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN` |
| **Luka Connect** | Chilean bank scraping (Banco de Chile + 8 others) | Separate repo, `LUKA_CONNECT_URL` + `LUKA_CONNECT_API_KEY` |
| **Plaid** | US bank account connections + transaction sync | `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` |
| **Google Gemini** | LLM merchant categorization (Gemini 2.5 Flash) | `GEMINI_API_KEY` |
| **Resend** | Transactional emails (invites) — Railway blocks SMTP | API key in env |
| **Supabase** | PostgreSQL hosting + Auth provider + RLS | `SUPABASE_URL`, keys |

## Infrastructure & Deployment

**Backend (Railway)**
- Builder: Dockerfile (`backend/Dockerfile`)
- Start: `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- Restart: ON_FAILURE, max 3 retries
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
| GET | `/auth/me` | Get current user profile |
| PATCH | `/auth/me` | Update profile (name, phone) |
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
| GET/POST | `/budgets/monthly/{household_id}` | Monthly budget CRUD |
| GET | `/budgets/personal/{household_id}` | Personal budget view |
| GET/POST | `/budgets/allocation/{household_id}` | 50/20/30 allocation |
| GET/POST | `/budgets/categories/{household_id}` | Per-category budgets |

### Bank Accounts (`/bank-accounts`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/bank-accounts` | List connected accounts |
| POST | `/bank-accounts` | Create account manually |
| PATCH | `/bank-accounts/{id}` | Update account details |
| DELETE | `/bank-accounts/{id}` | Delete (cascade: splits → txns → account) |

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
| GET | `/subscriptions/detected` | Auto-detected recurring transactions |

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
- `AllocationCard` — 50/20/30 allocation sliders with suggestion pills
- `MonthSelector` — dropdown (desktop) / bottom sheet (mobile)
- `PendingBlock` — pending/unreconciled transaction buckets
- `MerchantCard` — merchant review approval cards
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

## Testing

**Backend:** 45+ test files in `backend/tests/`, ~150-200 test functions using pytest + pytest-asyncio
- Coverage areas: auth, transactions, budgets, households, email parsing, WhatsApp handler, merchant normalization, bank connect encryption/mapping, queue routing, worker settings, notifications, categories, subscriptions, reconciliation
- Config: `asyncio_mode = "auto"`, testpaths = `["tests"]`
- Run: `cd backend && pytest -v`

**Frontend:** No test infrastructure configured (no Jest/Vitest/Playwright)

**CI/CD:** No GitHub Actions pipeline. Deployment is manual via Railway (backend) and Vercel (frontend auto-deploy on push)

## Design Decisions

**Two-tier worker queue:** Email webhooks must ACK in <200ms, but bank syncs can take 10+ minutes. Splitting into fast (max_jobs=20, 60s) and slow (max_jobs=5, 600s) workers prevents slow jobs from blocking webhook processing.

**No debt ledger:** Partner contributions are computed via aggregate queries on transactions, not maintained in a separate table. This avoids dual-write consistency issues and keeps the schema simpler.

**Global merchant DB:** Merchant categorizations are shared across all users to build a training dataset. Individual users can override categories via `merchant_category_selections`.

**PyJWT over Supabase SDK for auth:** Local JWT validation with JWKS avoids a network round-trip to Supabase on every request. Fallback chain (ES256 → RS256 → HS256) handles Supabase key rotation.

**Redis user cache:** `get_current_user()` caches user profiles for 5 minutes, avoiding repeated DB lookups on sequential API calls from the same user.

**Joint account auto-classification:** Bank accounts with `account_type = 'joint'` auto-classify all transactions as shared, skipping the WhatsApp split question.

**Luka Connect over Fintoc:** Fintoc was removed entirely and replaced with Luka Connect (standalone bank scraper). Luka Connect supports 9 Chilean banks via browser automation, stored as AES-256-GCM encrypted credentials.

**3-tier reconciliation:** Email transactions arrive first (real-time), bank transactions arrive later (scheduled sync). Reconciliation matches them with decreasing confidence: exact → fuzzy → sum-match. Email data enriches bank transactions (user-edited categories transfer over), then email duplicates are deleted.

**Per-user merchant overrides:** `merchant_category_selections` supports both global (shared dataset) and per-user category choices via nullable `user_id` FK. Users see their own overrides first, global selections second, LLM suggestions last.

**Subscription detection without extra tables:** Recurring expenses are detected from transaction patterns (2+ consecutive months, ±20% amount tolerance) using a computed view, cached in Redis for 3 days. No additional database tables needed.
