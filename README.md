# Luka

Latin American personal finance SaaS for individuals, couples, and groups. Automatically captures transactions from bank email notifications (Gmail/Outlook), bank scraping (Luka Connect), and open banking (Plaid for US); classifies them via LLM; enables actions via WhatsApp; and visualizes spending on a responsive web dashboard.

**LATAM-first:** Three-layer email parser (declarative templates, Gemini LLM waterfall, legacy regex) covering 101 banks across 6 countries (CL, CO, MX, PE, BR, US). Multi-currency throughout — nothing hardcoded to a single country or currency.

## Tech Stack

**Backend**
- Python 3.12 + FastAPI 0.111
- SQLAlchemy 2.0 async + asyncpg (PostgreSQL ORM)
- ARQ async job queue (two-tier: fast + slow workers)
- Redis (caching + job queue)
- Google Gemini (LLM email parsing + merchant categorization)

**Frontend**
- Next.js 16 (App Router) + React 19
- Tailwind CSS 4 + shadcn/ui (Radix-based components)
- Zustand 5 (client state, persisted to localStorage)
- TanStack Query 5 (server state, 30s staleTime)
- Recharts (financial charts)

**Database**
- Supabase PostgreSQL 15
- Alembic migrations (39 versions; `pg_trgm` extension enabled for fuzzy merchant matching)

**Auth**
- Supabase Auth — Google OAuth (Gmail users); Microsoft OAuth wired but hidden by default (see `NEXT_PUBLIC_ENABLE_MICROSOFT_LOGIN`)
- PyJWT + JWKS validation, ES256/RS256 asymmetric only (legacy HS256 shared secret revoked)
- Supabase publishable/secret API keys (new format, not legacy anon/service_role JWTs)

**Infrastructure**
- Railway (backend API + fast worker + slow worker)
- Vercel (frontend)
- Google Cloud Pub/Sub (Gmail push notifications)
- Resend (transactional emails)

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL (or Supabase project)
- Redis

### Installation

```bash
# Backend
cd backend
cp .env.example .env          # Fill in required env vars (see below)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head

# Frontend
cd frontend
cp .env.local.example .env.local   # Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_API_URL
npm install
```

### Running Locally

```bash
# Backend API server
cd backend && uvicorn main:app --reload     # http://localhost:8000

# ARQ workers (separate terminals)
arq worker.FastWorkerSettings               # email processing, light cron
arq worker.SlowWorkerSettings               # bank syncs, LLM, reconciliation, template agent

# Frontend
cd frontend && npm run dev                  # http://localhost:3000
```

## Project Structure

```
backend/
  main.py             FastAPI app factory + 16 routers
  worker.py           ARQ FastWorkerSettings + SlowWorkerSettings
  core/               Config, database, security (PyJWT), cache (Redis)
  modules/            Feature modules (see "What Luka Does" below)
  jobs/               ARQ task definitions + queue routing
  alembic/            Database migrations (37 versions)
  tests/              56 test files (~401 tests)

frontend/
  app/
    (auth)/           Login, onboarding (setup-household, connect-bank, verify-whatsapp)
    (dashboard)/      Home, transactions, budgets, household, subscriptions, notifications, settings
    (public)/         Privacy policy, terms, data-deletion
    lib/              API client, Zustand store, React Query hooks, Supabase clients

docs/                 Architecture docs, design specs, research
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL async connection string |
| `REDIS_URL` | Yes | Redis for caching and job queue |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase publishable key (`sb_publishable_...`) — env var name retained for compat |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase secret key (`sb_secret_...`) — env var name retained for compat |
| `FRONTEND_URL` | Yes | Frontend URL for CORS and invite links |
| `GCP_PROJECT_ID` | Yes | Google Cloud project for Pub/Sub |
| `PUBSUB_AUDIENCE` | Yes | Gmail webhook push endpoint URL |
| `WHATSAPP_APP_SECRET` | Yes | Meta WhatsApp Cloud API secret |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | WhatsApp sender phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | Yes | WhatsApp Cloud API access token |
| `GEMINI_API_KEY` | Yes | Google Gemini for email parsing + merchant categorization |
| `OPENAI_API_KEY` | No | OpenAI fallback for categorization |
| `PLAID_CLIENT_ID` | No | Plaid client ID (US bank connections) |
| `PLAID_SECRET` | No | Plaid API secret |
| `PLAID_ENV` | No | Plaid environment (sandbox/production) |
| `MICROSOFT_CLIENT_ID` | No | Azure app for Outlook integration |
| `MICROSOFT_CLIENT_SECRET` | No | Azure app secret |
| `OUTLOOK_CLIENT_STATE` | No | Outlook webhook verification secret |
| `LLM_WATERFALL_THRESHOLDS` | No | Confidence thresholds per model (default: 0.9,0.8,0.7,0.0) |
| `LLM_SHADOW_VALIDATION_RATE` | No | Shadow validation sample rate (default: 0.25) |
| `TEMPLATE_AGENT_MIN_EMAILS` | No | Min LLM-parsed emails before template generation (default: 20) |
| `ENVIRONMENT` | No | `development` or `production` (default: development) |
| `NEXT_PUBLIC_ENABLE_MICROSOFT_LOGIN` | No | Frontend flag (`true`/`false`). Hides the Microsoft OAuth button unless set to `true`. Outlook ingest end-to-end is not yet production-ready. |
| `ANALYZE` | No | Set to `true` and run `npx next build --webpack` to dump a bundle report to `.next/analyze/*.html` |

## What Luka Does

**Auth & Users** (`backend/modules/auth/`)
Handles user registration via Supabase OAuth (Google/Microsoft), profile management, encrypted email provider token storage, and WhatsApp PIN verification. Users are auto-provisioned on first OAuth login.

**Households & Partners** (`backend/modules/households/`)
Supports individual and couple households. Partners can be invited via shareable links. Manages split ratios, contribution tracking, settlement calculations, and category breakdowns between partners. No debt ledger — contributions are computed via aggregate queries.

**Email Pipeline** (`backend/modules/email/`)
Three-layer email parsing system for LATAM expansion:
1. **Layer 1 — Declarative Templates:** Auto-generated JSON extraction templates (CSS selectors + regex + fixed transforms). Zero LLM cost per email once promoted.
2. **Layer 2 — Gemini LLM Waterfall:** Confidence-based model escalation (3.1 Flash Lite -> 2.5 Flash -> 3 Flash -> 2.5 Pro). Circuit breaker for API outages (50% error rate -> 15min cooldown).
3. **Layer 3 — Legacy Regex:** Fallback for Banco de Chile formats with transaction type inference from subject/body keywords.

Receives Gmail push notifications via Google Cloud Pub/Sub and Outlook webhooks via Microsoft Graph. DB-backed bank registry (101 banks across CL, CO, MX, PE, BR, US) with Redis-cached lookups replaces hardcoded sender domains. Financial keyword filter now supports Spanish, English, and Portuguese. Empty email bodies are detected and skipped before parsing to prevent LLM hallucinations.

**Template Agent** (`backend/modules/email/template_agent.py`)
Autonomous ARQ cron job (daily 2am on slow worker). Discovers banks with sufficient LLM-parsed emails but no active template, generates declarative templates via Gemini, validates against LLM ground truth (100% amount match, 95% merchant match required), promotes to production, and auto-retires on shadow validation drift.

**Bank Registry** (`backend/modules/email/bank_registry_service.py`)
DB-backed bank registry with Redis cache (24h TTL). 101 banks seeded across 6 countries. Supports exact domain match + subdomain fallback. Stores known subjects, notification types, and active template references per bank.

**Bank Connect — Chile** (`backend/modules/bank_connect/`)
Integrates with Luka Connect, a standalone bank scraping service (separate repo). Stores AES-256-GCM encrypted bank credentials, triggers scraping jobs, maps scraped movements to Luka transactions with deduplication. Scheduled syncs run every 6 hours.

**Bank Connect — US** (`backend/modules/plaid/`)
Plaid Link integration for US bank accounts (production). Handles link token creation, public token exchange, transaction sync with cursor pagination, and account kind detection. Amounts stored in cents. Smart transaction mapping: extracts person names from Zelle transfers, detects credit card payments (Amex, Chase, etc.) and only flags as "transfer" if the target card account exists in the system. Person-to-person payments (Zelle, bank transfers) are classified as expense/income, not transfer. Pending (processing) Plaid transactions are surfaced in the frontend pending section with a "bank" badge. Scheduled syncs run daily.

**Transaction Processing** (`backend/modules/transactions/`)
Core transaction storage with support for personal, partner, and shared split types. Tracks transaction type (income/expense/transfer), source (email/bank_connect/plaid/whatsapp/manual), and reconciliation status. Unified sign convention: expenses and transfers are stored as negative amounts, income as positive — consistent across all sources (email, Plaid, bank connect). Optimistic category updates with merchant feedback loops.

**Reconciliation** (`backend/modules/reconciliation/`)
Matches email-sourced transactions with bank-sourced transactions using 3-tier priority matching (exact -> fuzzy -> sum-match). Dedup now requires currency + signed-amount equality + `bank_account_id` parity and skips the merchant filter for transfer-typed emails. Runs inline during Plaid/Connect sync, during the 6am reconciliation cron, and via a dedicated `reconciliation_tick` that fires every 15 min on the slow worker. The tick orchestrates four passes per household: (1) rematch aging email pendings against settled Plaid rows via `find_plaid_match_for_email`, (2) `detect_transfers` over 7 days (with `user_id` + currency equality guards — no cross-member, no cross-currency pairing), (3) `detect_refunds` over 90 days (same-account opposite-sign pairs → writes `refund_pair_id`), (4) aging pass — email pendings older than 14 days that have had a Plaid sync since creation get promoted to `status='orphan'` and surface in the `unmatched_email` pending bucket. Transfer rows, refund pairs, and orphans are excluded from spend/income totals by `exclude_from_totals` applied across all aggregation paths.

**Transaction consolidation (2026-04-20)** — Full reconciliation overhaul landed: canonical `pending | settled | orphan` status vocabulary (replaced legacy `confirmed`), new `card_last_four` / `refund_pair_id` / `orphaned_at` / `dismissed_by_user` columns on `transactions`, CC counterpart resolution via last-4 match against `BankAccount.account_number` + bank_name substring, CLP 100× scaling bug fixed in Plaid modify branch, and manual-match/dismiss/bulk-action endpoints with a shadcn-based `PendingBlock` UI (three buckets, age badges, floating bulk toolbar) and a `PairedTransactionCard` that groups linked transfers/refunds into one visual card. See [spec](docs/superpowers/specs/2026-04-20-transaction-consolidation-fix-design.md). One-time cleanup: `cd backend && python3 -m scripts.cleanup_rafael_pending --dry-run`.

**Merchant Categorization** (`backend/modules/merchants/`, `backend/modules/merchant_review/`)
Two-tier system: known merchants resolve instantly from a global DB cache, new merchants get 3 LLM-suggested categories (Gemini 2.5 Flash). Canonical merchant grouping via LLM batching. Training UI at `/train` for local admin use. User category selections feed back into the merchant database.

**WhatsApp Integration** (`backend/modules/whatsapp/`)
Full conversational flow via Meta WhatsApp Cloud API. Transaction alerts include sender, subject, and Chile-timezone time. Interactive split type selection (Personal/Hogar), category picker, and confirmation. Transfers (CC payments, own-account moves) receive an informational-only message with no split/category flow. Supports manual expense entry via natural language.

**Budgets & Allocations** (`backend/modules/budgets/`)
Monthly household budgets with waterfall ceiling logic and a multi-level Sankey flow visualization. The v3 `/budgets/v2/{household_id}` endpoint dispatches to two dedicated builders: `_build_hogar_sankey` (4 levels: per-source income → `Ingresos Hogar` hub → 5 allocation nodes including `Gastos fijos`/`Cuotas`/`Meta de ahorro`/`Gasto personal`/`Disponible hogar` → per-category breakdown) and `_build_personal_sankey` (3 allocation levels with its own `Mis ingresos` hub). Caller-relative privacy: each viewer sees their own income categories broken out at Level 0, while other members appear as one aggregated node per member (`Ingresos {Name}` for full mode, `Contribución fija {Name}` for fixed mode). Forecast engine, 50/20/30 allocation suggestions, per-category caps, cuotas (installment purchases), savings target + payday + personal allocation settings, contribution-mode dispatch (full / fixed / reimbursement) with privacy invariant enforced by construction in `contribution_service.income_breakdown_for_household_view`. Budget configuration (savings target, payday, personal allocation, contribution mode, per-category caps) lives in a single accordion modal on `/budgets` triggered by a gear button next to the currency toggle — no more navigating to `/settings` to tweak a number.

**Notifications** (`backend/modules/notifications/`)
In-app notification system with unread counts, per-user notification preferences (WhatsApp toggle), and CRUD operations.

**Subscriptions** (`backend/modules/subscriptions/`)
Automatic recurring transaction detection via DB-backed cache (refreshed on demand). Each detected subscription supports an explicit user-set classification (`Personal` or `Compartido` / shared) via a click-to-flip pill in the subscriptions detail table. Toggling the classification cascades to the last 3 months of underlying `transaction_splits` rows via `reclassify_subscription_split`, upserts the override, and invalidates the detection cache atomically. The household-bills aggregate filters by effective `split_type='shared'` so personal subscriptions are correctly excluded from the household pot — and a symmetric `get_user_shared_known_bills` helper preserves flow conservation when reimbursement-mode members have personal bills.

**Bank Accounts** (`backend/modules/bank_accounts/`)
Manual bank account creation and management. Supports personal, partner, and joint (hogar) account types. Balance tracking with sync timestamps.

**Settings** (`backend/modules/settings/`)
User notification preferences, custom category ordering with drag-and-drop (up to 20 per type), category hide/show, and usage tracking. Categories fetched dynamically via API — all dropdowns across the app reflect user preferences in real time.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design, data model, API endpoints, worker jobs
- [NEXT-STEPS.md](NEXT-STEPS.md) — Pending work, known issues, future ideas
- [Design Specs](docs/superpowers/specs/) — Original design documents
- [Bank Email Research](docs/bank-email-notifications-research.md) — 30 banks across 6 LATAM countries
