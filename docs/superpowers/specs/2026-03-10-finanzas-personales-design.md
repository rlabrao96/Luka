# Luka — Full System Design
**Date:** 2026-03-10
**Author:** Rafa (with Claude Code)
**Status:** Approved — v2 (post spec review, 2026-03-10)

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [System Architecture](#2-system-architecture)
3. [Database Schema](#3-database-schema)
4. [Backend Modules](#4-backend-modules)
5. [Frontend Structure](#5-frontend-structure)
6. [Security & Encryption](#6-security--encryption)
7. [Error Handling & Resilience](#7-error-handling--resilience)
8. [Infrastructure](#8-infrastructure)

---

## 1. Product Overview

### What It Is
A Chilean personal finance web application focused on joint/couple expense tracking. Transactions are captured automatically via bank email alerts, classified using an LLM, and actioned through WhatsApp interactive messages. A responsive web dashboard provides full financial visibility.

### Core User Models
- **Individual:** Single user tracking personal finances
- **Couple/Household:** Two users sharing a household, with split expense logic and privacy controls between partners

### Key Features
1. Gmail and Outlook push notifications for real-time bank email capture
2. Regex-based email parser for Chilean bank formats (Santander, Banco de Chile, BCI)
3. LLM-powered merchant categorization with proprietary caching database
4. WhatsApp Cloud API interactive messages for expense splitting and categorization
5. Proprietary merchant database that learns from user selections
6. Fintoc Open Banking reconciliation against settled transactions
7. Joint account support with monthly budget tracking
8. Responsive web dashboard (desktop + mobile browser)

### Privacy Model (Couples)
Within a household, each user can see:
- Full detail of their own transactions
- Full detail of shared/household transactions
- Partner's aggregate stats only (total spent, category breakdown, inflows/outflows)
- Partner's individual transactions: **never accessible**

---

## 2. System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        RAILWAY                              │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  FastAPI     │    │  ARQ Worker  │    │    Redis     │  │
│  │  (API +      │───▶│  (async jobs)│◀───│  (job queue  │  │
│  │   Webhooks)  │    │              │    │  + cache)    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────┘  │
│         │                  │                               │
└─────────┼──────────────────┼───────────────────────────────┘
          │                  │
          ▼                  ▼
     Supabase (PostgreSQL)  External APIs
     - users                - OpenAI gpt-4o-mini / Gemini Flash
     - households           - Meta WhatsApp Cloud API
     - bank_accounts        - Fintoc (Open Banking Chile)
     - merchants            - Gmail API
     - transactions         - Microsoft Graph API (Outlook)
     - transaction_splits
     - household_budgets
     - household_invites
     - merchant_category_selections
     - processed_webhooks
     - failed_jobs

┌─────────────────────────────────────────────────────────────┐
│                        VERCEL                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Next.js App (Responsive)               │   │
│  │  Desktop: sidebar nav + KPI cards + charts          │   │
│  │  Mobile:  bottom tab nav + stacked cards            │   │
│  └─────────────────────┬───────────────────────────────┘   │
└────────────────────────┼────────────────────────────────────┘
                         │ REST API calls
                         ▼
                   FastAPI (Railway)
```

### Primary Request Flow

```
Bank sends email to user
  → Gmail / Outlook
    → Push notification to webhook
      → POST /webhooks/gmail  OR  POST /webhooks/outlook
        → Verify signature (< 1ms)
        → Check idempotency (< 5ms)
        → Enqueue ARQ job (< 10ms)
        → Return 200 immediately

ARQ Worker processes job:
  → Fetch email via provider API
  → parse_bank_email() → {amount, raw_merchant, date}
  → Check bank_accounts.account_type:
      'personal' → lookup_merchant() → send WhatsApp split message
      'joint'    → lookup_merchant() → auto-classify shared → send category message
  → lookup_merchant(raw_name):
      DB HIT  → return top cached category
      DB MISS → call LLM → store result → return 4 suggestions
  → User responds on WhatsApp
    → POST /webhooks/whatsapp
      → save transaction + split_type + category
      → update merchant_category_selections (learning)

Fintoc reconciliation (nightly):
  → fetch settled transactions
  → match vs pending: amount (exact) + date (±3d) + merchant (fuzzy >0.7)
  → update status to 'reconciled'
```

### Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.12) |
| Background jobs | ARQ (async Redis Queue) |
| Job broker/cache | Redis |
| Database | Supabase (PostgreSQL 15) |
| ORM | SQLAlchemy async + Alembic |
| Frontend | Next.js 14 (App Router) |
| UI components | shadcn/ui + Tailwind CSS |
| Charts | Recharts |
| Client state | Zustand |
| Server state | TanStack Query |
| Hosting (backend) | Railway |
| Hosting (frontend) | Vercel |
| Auth | Supabase Auth (Google OAuth + Microsoft OAuth) |

---

## 3. Database Schema

### Entity Relationships

```
users ──────────── household_members ──────── households
  │                                               │
  ├── bank_accounts                               ├── household_budgets
  │                                               │
  ▼                                               ▼
transactions ──────────────────────────── transaction_splits
  │
  ▼
merchants ◀── merchant_category_selections
```

### Table Definitions

#### `users`
```sql
id                         UUID PRIMARY KEY DEFAULT gen_random_uuid()
email                      TEXT UNIQUE NOT NULL
full_name                  TEXT NOT NULL
phone_whatsapp             TEXT                    -- stored in Supabase Vault (PII)
whatsapp_verified          BOOL DEFAULT false      -- true after PIN verification
email_provider             TEXT DEFAULT 'gmail'    -- 'gmail' | 'outlook'
mail_watch_subscription_id TEXT                    -- provider-agnostic watch ID
mail_watch_expiry          TIMESTAMPTZ             -- renewal deadline
created_at                 TIMESTAMPTZ DEFAULT now()
updated_at                 TIMESTAMPTZ DEFAULT now()

-- All sensitive tokens stored in Supabase Vault (never plain columns):
-- google_refresh_token, microsoft_refresh_token, phone_whatsapp
```

#### `households`
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid()
name        TEXT NOT NULL               -- "Rafa & Cami"
type        TEXT NOT NULL               -- 'individual' | 'couple'
created_at  TIMESTAMPTZ DEFAULT now()
```

#### `household_members`
```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
household_id  UUID NOT NULL REFERENCES households(id)
user_id       UUID NOT NULL REFERENCES users(id)
role          TEXT NOT NULL DEFAULT 'member'  -- 'owner' | 'member'
joined_at     TIMESTAMPTZ DEFAULT now()

UNIQUE(household_id, user_id)
```

#### `bank_accounts`
```sql
id                   UUID PRIMARY KEY DEFAULT gen_random_uuid()
household_id         UUID NOT NULL REFERENCES households(id)
user_id              UUID NOT NULL REFERENCES users(id)
bank_name            TEXT NOT NULL    -- 'santander' | 'bci' | 'banco_de_chile'
account_type         TEXT NOT NULL    -- 'personal' | 'joint'
cardholder_name      TEXT             -- for joint: which member owns this card
fintoc_link_id       TEXT             -- stored in Supabase Vault
email_sender_pattern TEXT             -- email sender/subject pattern (Gmail + Outlook)
is_active            BOOL DEFAULT true
created_at           TIMESTAMPTZ DEFAULT now()

-- email_sender_pattern examples:
--   Gmail:   "alertas@santander.cl"
--   Outlook: "no-reply@bancochile.cl"
-- Used by both providers to route emails to the correct bank_account record
```

#### `household_budgets`
```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
household_id     UUID NOT NULL REFERENCES households(id)
bank_account_id  UUID NOT NULL REFERENCES bank_accounts(id)
month            DATE NOT NULL           -- first day of month, e.g. 2026-03-01
budgeted         NUMERIC(12,2) NOT NULL  -- deposited amount in CLP
source           TEXT DEFAULT 'manual'  -- 'manual' | 'fintoc'
created_at       TIMESTAMPTZ DEFAULT now()

UNIQUE(household_id, bank_account_id, month)
-- One budget entry per account per month.
-- Supports multiple joint accounts in the same household.
-- Dashboard aggregates across all accounts for the household total.
```

#### `merchants` ← global proprietary dataset
```sql
id                        UUID PRIMARY KEY DEFAULT gen_random_uuid()
raw_name                  TEXT UNIQUE NOT NULL   -- "COMPRA LIDER PROVI"
normalized_name           TEXT                   -- "Lider"
llm_suggested_categories  JSONB                  -- ["Supermercado","Retail",...]
total_selections          INT DEFAULT 0
created_at                TIMESTAMPTZ DEFAULT now()
updated_at                TIMESTAMPTZ DEFAULT now()
```

#### `merchant_category_selections` ← learning layer
```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
merchant_id  UUID NOT NULL REFERENCES merchants(id)
category     TEXT NOT NULL
count        INT DEFAULT 1
last_used_at TIMESTAMPTZ DEFAULT now()

UNIQUE(merchant_id, category)
-- Top category: ORDER BY count DESC LIMIT 1
```

#### `transactions`
```sql
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id           UUID NOT NULL REFERENCES users(id)
household_id      UUID NOT NULL REFERENCES households(id)
bank_account_id   UUID REFERENCES bank_accounts(id)  -- which account triggered this
merchant_id       UUID REFERENCES merchants(id)       -- nullable until matched
raw_merchant_name TEXT NOT NULL
amount            NUMERIC(12,2) NOT NULL              -- CLP
currency          TEXT DEFAULT 'CLP'
transaction_date  TIMESTAMPTZ NOT NULL
category          TEXT             -- denormalized from transaction_splits for fast queries
source            TEXT NOT NULL    -- 'gmail' | 'outlook' | 'fintoc' | 'manual'
status            TEXT NOT NULL DEFAULT 'pending'
                                   -- 'pending' | 'settled' | 'reconciled'
fintoc_id         TEXT             -- for reconciliation matching
raw_email_text    TEXT             -- purged 24h after parsing
created_at        TIMESTAMPTZ DEFAULT now()
updated_at        TIMESTAMPTZ DEFAULT now()

-- category is denormalized here for dashboard queries that don't need to JOIN
-- transaction_splits. Always kept in sync when split is decided.
```

#### `transaction_splits`
```sql
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
transaction_id      UUID NOT NULL REFERENCES transactions(id)
split_type          TEXT NOT NULL   -- 'personal' | 'partner' | 'shared'
category            TEXT            -- final selected category
decided_by_user_id  UUID REFERENCES users(id)
whatsapp_message_id TEXT
decided_at          TIMESTAMPTZ
created_at          TIMESTAMPTZ DEFAULT now()
```

#### `household_invites`
```sql
id             UUID PRIMARY KEY DEFAULT gen_random_uuid()
household_id   UUID NOT NULL REFERENCES households(id)
invited_by     UUID NOT NULL REFERENCES users(id)
invited_email  TEXT NOT NULL
token          TEXT UNIQUE NOT NULL DEFAULT gen_random_uuid()::TEXT
expires_at     TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '7 days'
accepted_at    TIMESTAMPTZ         -- NULL until partner accepts
created_at     TIMESTAMPTZ DEFAULT now()

-- Endpoints:
--   POST /households/{id}/invite  → create invite, send email with link
--   GET  /invite/{token}          → validate token, create user + household_member
```

#### `failed_jobs`
```sql
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
job_name      TEXT NOT NULL          -- e.g. 'process_email'
payload       JSONB NOT NULL         -- original job arguments
error_message TEXT NOT NULL          -- last exception message
attempt_count INT DEFAULT 1
created_at    TIMESTAMPTZ DEFAULT now()
last_failed_at TIMESTAMPTZ DEFAULT now()
-- Ops dashboard: shows failed jobs for manual review/retry
```

#### `processed_webhooks` ← idempotency
```sql
message_id    TEXT PRIMARY KEY    -- Pub/Sub or WhatsApp message ID
processed_at  TIMESTAMPTZ DEFAULT now()
-- Auto-delete entries older than 7 days via scheduled job
```

### Monthly Contribution Query

No ledger/debt table — contributions derived at query time:

```sql
SELECT
  t.user_id,
  u.full_name,
  SUM(t.amount)                                             AS total_paid,
  SUM(t.amount) FILTER (WHERE ts.split_type = 'shared')    AS shared_paid,
  SUM(t.amount) FILTER (WHERE ts.split_type = 'personal')  AS personal_paid
FROM transactions t
JOIN transaction_splits ts ON ts.transaction_id = t.id
JOIN users u ON u.id = t.user_id
WHERE t.household_id = :household_id
  AND DATE_TRUNC('month', t.transaction_date) = DATE_TRUNC('month', NOW())
GROUP BY t.user_id, u.full_name
```

Produces:
```
Gasto total del hogar (Marzo 2026):   $500.000
  Pagado por Rafa:                    $150.000
  Pagado por Cami:                    $350.000
```

### Database Indexes

```sql
-- High-frequency query paths
CREATE INDEX idx_transactions_user_id       ON transactions(user_id);
CREATE INDEX idx_transactions_household_id  ON transactions(household_id);
CREATE INDEX idx_transactions_date          ON transactions(transaction_date DESC);
CREATE INDEX idx_transaction_splits_txn_id  ON transaction_splits(transaction_id);
CREATE INDEX idx_mcs_merchant_id            ON merchant_category_selections(merchant_id);
CREATE INDEX idx_processed_webhooks_at      ON processed_webhooks(processed_at);
-- merchants(raw_name) already indexed via UNIQUE constraint
```

### Row Level Security Policies

```sql
-- Own transactions: full detail
CREATE POLICY "own_transactions" ON transactions
  FOR SELECT USING (user_id = auth.uid());

-- Shared transactions: visible to all household members
CREATE POLICY "shared_transactions" ON transactions
  FOR SELECT USING (
    household_id IN (
      SELECT household_id FROM household_members WHERE user_id = auth.uid()
    )
    AND id IN (
      SELECT transaction_id FROM transaction_splits WHERE split_type = 'shared'
    )
  );

-- Partner stats: aggregate only, via SECURITY DEFINER RPC function
-- No direct row access to partner transactions ever
CREATE FUNCTION get_partner_summary(p_household_id UUID, p_month DATE)
RETURNS JSON SECURITY DEFINER ...
```

---

## 4. Backend Modules

### Project Structure

```
backend/
├── main.py
├── worker.py
├── core/
│   ├── config.py          -- env vars and secrets
│   ├── database.py        -- SQLAlchemy async engine
│   └── security.py        -- JWT middleware
├── modules/
│   ├── email/
│   │   ├── base.py        -- EmailProvider abstract class
│   │   ├── gmail.py       -- GmailProvider implementation
│   │   ├── outlook.py     -- OutlookProvider implementation
│   │   ├── factory.py     -- get_email_provider(user) factory
│   │   └── parser.py      -- regex bank email parser
│   ├── whatsapp/
│   │   ├── router.py      -- POST /webhooks/whatsapp
│   │   ├── sender.py      -- Meta API message sender
│   │   └── handler.py     -- button/list click routing
│   ├── merchants/
│   │   ├── service.py     -- DB lookup + cache logic
│   │   └── llm.py         -- LLM categorization
│   ├── transactions/
│   │   ├── router.py      -- GET /transactions
│   │   └── service.py     -- CRUD + split logic
│   ├── fintoc/
│   │   ├── client.py      -- Fintoc API wrapper
│   │   └── reconciler.py  -- matching engine
│   └── households/
│       ├── router.py      -- GET /households, /summary
│       └── service.py     -- contribution queries
└── jobs/
    └── tasks.py           -- ARQ job definitions
```

### Module 1 — Email Provider Abstraction

Both Gmail and Outlook follow the same interface:

```python
class EmailProvider(ABC):
    async def setup_watch(self, user_id: str) -> dict: ...
    async def fetch_new_emails(self, user_id: str, **kwargs) -> list[RawEmail]: ...
    async def renew_watch(self, user_id: str) -> None: ...

def get_email_provider(user: User) -> EmailProvider:
    return GmailProvider() if user.email_provider == "gmail" else OutlookProvider()
```

**Webhook endpoints:**

```python
# Gmail: Google Cloud Pub/Sub
# Verification: validate Google OIDC Bearer token (not a query param)
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(403)
    token = auth_header.removeprefix("Bearer ")
    try:
        id_token.verify_oauth2_token(
            token, google_requests.Request(),
            audience=settings.PUBSUB_AUDIENCE  # your Cloud Pub/Sub push endpoint URL
        )
    except Exception:
        raise HTTPException(403)
    await enqueue_job("process_email", provider="gmail", ...)
    return {"status": "ok"}

# Outlook: Microsoft Graph Change Notifications
@router.post("/webhooks/outlook")
async def outlook_webhook(request: Request, validationToken: str = None):
    if validationToken:
        # Sanitize before reflecting — alphanumeric + hyphens only
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]{1,256}$', validationToken):
            raise HTTPException(400)
        return PlainTextResponse(validationToken)
    body = await request.json()
    for notification in body.get("value", []):
        if notification.get("clientState") != settings.OUTLOOK_CLIENT_STATE:
            raise HTTPException(403)
        await enqueue_job("process_email", provider="outlook", ...)
    return {"status": "ok"}
```

**Watch renewal:** Scheduled ARQ job runs daily, renews any subscription expiring within 24h.
- Gmail: max 7-day cycle, renew before day 6
- Outlook: max ~3-day cycle (4,230 min), renew daily. Microsoft OAuth access token is also refreshed here to prevent subscription renewal failure on expired tokens.

### Module 2 — Bank Email Parser

Regex targets for Chilean bank formats:

```python
AMOUNT_PATTERN   = r'\$\s?([\d\.]+)'
MERCHANT_PATTERN = r'(?:en|comercio:?)\s+([A-Z0-9 ]+)'
DATE_PATTERN     = r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})'
```

### Module 3 — Merchant Service (Cache + LLM)

**Normalization pipeline** (runs before every DB lookup):
```python
import re

def normalize_merchant(raw: str) -> str:
    # 1. Uppercase + strip whitespace
    s = raw.strip().upper()
    # 2. Remove common Chilean bank prefixes
    s = re.sub(r'^(COMPRA|PAGO|CARGO|TRANSFERENCIA|TRF)\s+', '', s)
    # 3. Strip trailing location suffixes (e.g. "PROVI", "LAS CONDES", "VITACURA")
    s = re.sub(r'\s+(PROVI|PROVIDENCIA|LAS CONDES|VITACURA|MAIPU|ÑUÑOA)\s*$', '', s)
    # 4. Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# "COMPRA LIDER PROVI"       → "LIDER"
# "COMPRA LIDER PROVIDENCIA" → "LIDER"
# "COMPRA LIDER LAS CONDES"  → "LIDER"
# All three become the same cache key → single DB/LLM entry
```

**Lookup flow:**
```
lookup_merchant(raw_name):
  1. normalized = normalize_merchant(raw_name)
  2. Check Redis cache: GET merchant:{normalized}        ← L1 cache (TTL: 24h)
  3. Redis HIT  → return cached top category
  4. Redis MISS → query DB: WHERE normalized_name = normalized
  5. DB HIT     → cache in Redis → return top category from merchant_category_selections
  6. DB MISS    → call LLM (gpt-4o-mini or gemini-1.5-flash)
                → store in DB (raw_name + normalized_name + llm_suggested_categories)
                → cache in Redis
                → return 4 suggested categories

LLM cost per call: < $0.001
Repeat merchants (same normalized name): free (Redis or DB hit)
```

**LLM prompt:**
```
System: You are a Chilean personal finance assistant.
User: Merchant from a Chilean bank transaction: "{raw_name}"
      Return exactly 4 budget categories in JSON, in Spanish.
      Format: {"categories": ["cat1","cat2","cat3","cat4"]}
```

### Module 4 — WhatsApp Integration

**Multi-step conversation state (Redis):**

The personal account flow is two steps: split selection → then (if shared) category selection. WhatsApp webhooks are stateless, so Redis stores the pending context between steps:

```python
# After sending the split buttons, store context in Redis (TTL: 30 min)
await redis.setex(
    f"wa_session:{user_phone}",
    1800,  # 30 minutes
    json.dumps({"transaction_id": str(txn.id), "step": "awaiting_split"})
)

# When button click arrives, retrieve context:
session = json.loads(await redis.get(f"wa_session:{user_phone}") or "{}")
# → routes correctly to split handler or category handler
# → cleared from Redis once final category is saved
```

**Personal account flow:**
```
send_expense_alert() →
  Interactive message: "Gasto de $X en Merchant. ¿Cómo dividimos esto?"
  Buttons: "Mío" | "De Cami" | "Compartido"
  → Store Redis session: {transaction_id, step: "awaiting_split"}

  → "Mío" / "De Cami"  → save split_type='personal'/'partner', clear session, done
  → "Compartido"        → update session: {step: "awaiting_category", split_type: "shared"}
                         → send List Message with 4 categories
                         → user selects category
                         → save split_type='shared', category
                         → update transactions.category (denormalized)
                         → update merchant_category_selections (learning)
                         → clear Redis session
```

**Joint account flow:**
```
send_joint_expense_alert() →
  auto-insert transaction_splits with split_type = 'shared'  ← always shared
  Interactive message: "Gasto compartido de $X en Merchant. ¿Qué categoría?"
  List: 4 LLM/cached categories (no split question needed)
  → Store Redis session: {transaction_id, step: "awaiting_category", split_type: "shared"}
```

**WhatsApp message types used:**
- Initial alert: Interactive Button Message (3 buttons)
- Category selection: Interactive List Message (4 items)

### Module 5 — Fintoc Reconciliation Engine

Runs nightly (ARQ cron) or on-demand:

```
for each settled transaction from Fintoc:
  query pending transactions WHERE:
    amount     = fintoc.amount                    (exact)
    date       BETWEEN date-3d AND date+3d        (±3 day window)
    merchant   similarity > 0.7                   (rapidfuzz partial_ratio)

  MATCH found  → status='reconciled', fintoc_id=fintoc.id
  NO MATCH     → insert as source='fintoc', flag for review
```

### Module 6 — Households & Contributions

```
GET /households/{id}/summary        → monthly totals (both users)
GET /transactions/mine              → full detail, own only
GET /transactions/shared            → full detail, shared only
GET /households/{id}/partner-stats  → aggregate only:
  {
    "total_spent": 350000,
    "total_income": 1200000,
    "by_category": [
      {"category": "Supermercado", "amount": 120000},
      {"category": "Restaurantes", "amount": 85000}
    ]
  }
  -- No merchant names, no dates, no individual rows
```

### Background Jobs (ARQ)

| Job | Trigger | Description |
|---|---|---|
| `process_email` | Webhook (Gmail/Outlook) | Parse email, normalize merchant, lookup/LLM, send WhatsApp |
| `send_whatsapp_alert` | After email parsed | Send interactive message to user |
| `renew_mail_watches` | Daily cron | Renew Gmail (7d) and Outlook (~3d) subscriptions + refresh MS OAuth token |
| `run_fintoc_sync` | Nightly cron / on-demand | Fetch settled transactions, reconcile |
| `purge_raw_emails` | Hourly cron | Set raw_email_text = NULL where age > 24h |
| `cleanup_webhooks` | Daily cron | Delete processed_webhooks older than 7 days |

**Note on Fintoc webhooks:** Fintoc supports real-time webhook events when transactions settle. A `POST /webhooks/fintoc` endpoint should be evaluated in a future iteration to replace the nightly cron with near-real-time reconciliation.

---

## 5. Frontend Structure

### Tech Stack

| Tool | Purpose |
|---|---|
| Next.js 14 (App Router) | Framework, routing, SSR |
| Tailwind CSS | Responsive utility styling |
| shadcn/ui | Components (cards, tables, buttons) |
| Recharts | Area, donut, bar charts |
| Zustand | Client-side state |
| TanStack Query | API data fetching + caching |

### Page Structure

```
app/
├── (auth)/
│   ├── login/page.tsx               -- Google / Microsoft OAuth
│   └── onboarding/
│       ├── connect-email/page.tsx   -- select Gmail or Outlook, authorize
│       ├── setup-household/page.tsx -- solo or invite partner
│       └── connect-bank/page.tsx    -- add personal/joint accounts
│
└── (dashboard)/
    ├── layout.tsx                   -- responsive shell
    ├── page.tsx                     -- Home / Dashboard
    ├── transactions/page.tsx        -- Full history + filters
    ├── household/page.tsx           -- Summary + partner aggregate stats
    ├── budgets/page.tsx             -- Joint account budget tracker
    ├── merchants/page.tsx           -- Merchant database management
    └── settings/page.tsx           -- Account, WhatsApp, email, banks
```

### Responsive Layout

```
DESKTOP (≥1024px)                    MOBILE (<1024px)
┌──────────┬──────────────────────┐  ┌─────────────────────┐
│          │                      │  │  Buenos días, Rafa  │
│  Sidebar │   Main Content       │  │  $312.400 gastados  │
│  240px   │                      │  │  ─────────────────  │
│          │  ┌────┐┌────┐┌────┐  │  │ [card][card][card] │
│  🏠 Home │  │KPI ││KPI ││KPI │  │  │                    │
│  💳 Txns │  └────┘└────┘└────┘  │  │  Últimos gastos    │
│  👥 Hogar│  ┌──────────┐┌─────┐ │  │  ──────────────── │
│  📊 Budget  │  Chart   ││Donut│ │  │  Lider   $15.990  │
│  ⚙️ Config  └──────────┘└─────┘ │  │  Copec   $32.000  │
│          │  Recent transactions  │  ├────────────────────┤
│  [Rafa]  │                      │  │ 🏠  💳  👥  📊  ⚙️│
└──────────┴──────────────────────┘  └────────────────────┘
```

### Dashboard Home
- KPI row: gasto personal / gasto compartido / presupuesto disponible
- Spending trend area chart (mine vs shared overlay, monthly)
- Spending by category donut chart (top 5)
- Recent transactions table (merchant, amount, category, split type, date)
- Transaction type tags: 🟢 Personal / 🔵 De Cami / 🟡 Compartido

### Household Page
- Monthly contribution bar (Rafa % vs Cami %)
- Partner stats section (aggregate only — category totals, in/out)
- Privacy notice: "No se muestran transacciones individuales por privacidad del hogar"

### Budgets Page (joint account households only)
- Monthly budget deposited vs spent progress bar
- Per-card breakdown (Tarjeta Rafa / Tarjeta Cami)
- Daily spending pace chart vs monthly budget

### Design System

```
Primary blue:      #2563EB   -- buttons, active nav, highlights
Light blue bg:     #EFF6FF   -- card backgrounds, page background
Sky accent:        #38BDF8   -- charts, progress bars
Dark text:         #0F172A
Muted text:        #64748B
Success:           #10B981   -- positive values, under budget
Alert:             #EF4444   -- overspent, warnings

Transaction tags:
  Personal:   #DCFCE7 bg / #16A34A text
  De Cami:    #DBEAFE bg / #2563EB text
  Compartido: #FEF9C3 bg / #CA8A04 text
```

---

## 6. Security & Encryption

### Authentication
- **Google OAuth** for Gmail users, **Microsoft OAuth** for Outlook users
- OAuth scopes: `gmail.readonly` (minimum) / `Mail.Read` (minimum)
- JWT tokens via Supabase Auth: 1-hour expiry, httpOnly secure cookie
- Refresh token rotation: each use invalidates previous token

### Data Encryption

| Field | Protection |
|---|---|
| Google refresh token | Supabase Vault (pgsodium AES-256, managed key hierarchy) |
| Microsoft refresh token | Supabase Vault |
| Fintoc link token | Supabase Vault |
| `phone_whatsapp` | Supabase Vault (consistent with other secrets — no separate key mgmt needed) |
| `raw_email_text` | Auto-purged 24h after parsing |
| All DB data at rest | Supabase AES-256 volume encryption |
| All data in transit | TLS 1.3 enforced everywhere |

All sensitive fields use Supabase Vault uniformly. This avoids the pgcrypto key management problem (where the encryption key would need to live in the same environment as the database credentials, providing limited additional protection).

### API & Webhook Security
- Gmail webhook: Google OIDC Bearer token verification (not a query param)
- Outlook webhook: `clientState` secret verification + sanitized `validationToken` handshake
- WhatsApp webhook: HMAC-SHA256 signature verification (`X-Hub-Signature-256`)
- Webhook idempotency: `processed_webhooks` table deduplicates retries
- Rate limiting via `slowapi`: keyed on verified sender identity for webhooks (not source IP, since Google/Meta share IP pools), 60 req/min per authenticated user for API calls
- CORS: only production domain + `localhost:3000` allowed

### Supabase Key Scoping

| Component | Supabase Key Used | Reason |
|---|---|---|
| FastAPI (user-facing API) | `anon` key + JWT | RLS policies enforced, user context respected |
| ARQ Worker (background jobs) | `service_role` key | Needs to write transactions on behalf of users, bypass RLS safely for system operations |

The `service_role` key is **never** sent to or used by the Next.js frontend. FastAPI user-facing endpoints use the `anon` key so that all RLS policies remain active as an enforced safety net.

### CSRF Protection
- JWT stored in `httpOnly; Secure; SameSite=Lax` cookie
- `SameSite=Lax` blocks cross-origin POST requests (covers CSRF for state-changing operations)
- For sensitive mutations (account deletion, partner invite), a double-submit CSRF token is additionally required in the request header

### Chilean Data Privacy (Ley 21.719)

| Requirement | Implementation |
|---|---|
| Informed consent | Explicit data usage screen before OAuth |
| Purpose limitation | Email scope limited to bank alert detection only |
| Right to deletion | `DELETE /api/account` hard-deletes all user data + revokes tokens |
| Data minimization | Raw email text purged after 24h |
| Breach notification | Monitoring alerts → user notification within 72h |

**What the app stores vs. what it does not:**
```
STORED:    amount, merchant (parsed), date, category, split type
NOT STORED: full email content (purged), bank account numbers,
            card numbers, passwords, unrelated email metadata
```

---

## 7. Error Handling & Resilience

### Webhook Response Strategy
Webhooks must respond within 5 seconds or providers retry:
1. Verify signature (< 1ms)
2. Check idempotency table (< 5ms)
3. Enqueue ARQ job (< 10ms)
4. Return 200 — never fail the webhook ACK

All processing happens asynchronously in the worker.

### External API Failure Handling

| Service Down | Behavior |
|---|---|
| OpenAI / Gemini | Retry 3x exponential backoff → fallback: send WhatsApp with manual category input |
| Fintoc | Log failed sync, retry next scheduled run, show "Última sincronización: hace Xh" |
| Meta WhatsApp | Store unsent message, retry queue every 15min for up to 6h |
| Gmail / Graph API | Respect 429 headers, exponential backoff, alert user if > 1h delay |

### ARQ Job Resilience

ARQ does not apply exponential backoff automatically — backoff is implemented in the job body using `tenacity`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=30, max=300))
async def call_llm_with_retry(merchant_name: str) -> dict: ...
```

For the ARQ job itself:
- `max_tries=3` — ARQ retries the full job on unhandled exceptions
- After 3 failures: caught in a `try/except` wrapper, inserts into `failed_jobs` table
- Dead letter pattern: no silent failures, every failure is observable

### Monitoring
- **Sentry** (free tier): exception tracking for FastAPI + Next.js
- **Railway logs**: structured JSON logs
- **Health endpoint**: `GET /health` checked every 60s
- **Uptime monitoring**: Railway built-in alerts

---

## 8. Infrastructure

### Services (Railway)

| Service | Role | Estimated Cost |
|---|---|---|
| FastAPI app | API server + webhook endpoints | ~$3/mo |
| ARQ worker | Background job processor | ~$1/mo |
| Redis | Job queue + merchant cache | ~$1/mo |
| **Total Railway** | | **~$5/mo** |

| Service | Role | Cost |
|---|---|---|
| Supabase | PostgreSQL + Auth + Vault | Free tier → $25/mo |
| Vercel | Next.js hosting | Free tier |
| **Total** | | **~$5-30/mo depending on scale** |

### Environment Variables (Railway)

```
# Database
DATABASE_URL=postgresql+asyncpg://...

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# Gmail
PUBSUB_VERIFICATION_TOKEN=

# Outlook
OUTLOOK_CLIENT_STATE=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# WhatsApp
WHATSAPP_APP_SECRET=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=

# Fintoc
FINTOC_API_KEY=

# LLM
OPENAI_API_KEY=
# or
GEMINI_API_KEY=

# App
FRONTEND_URL=https://tuapp.cl
```

### Deployment Strategy
- **Branch:** `main` → auto-deploy to production (Railway + Vercel GitHub integration)
- **Branch:** `dev` → auto-deploy to staging environment
- **Migrations:** Alembic, run on deploy before app starts
- **Secrets:** Railway environment variables only, never committed to git
- **Secret scanning:** `detect-secrets` pre-commit hook enforced in `.pre-commit-config.yaml` — blocks any commit containing high-entropy strings, API keys, or known secret patterns

---

## Appendix: Onboarding Flow

```
Google/Microsoft Sign-in
  → New user? → 4-step onboarding wizard:

      Step 1: Connect email
              "¿Con qué correo recibes las alertas de tu banco?"
              [Gmail / Google]  [Outlook / Hotmail]
              → OAuth flow → Gmail/Outlook watch subscription created

      Step 2: Verify WhatsApp number
              "¿Cuál es tu número de WhatsApp?"
              → Enter phone number (e.g. +56 9 1234 5678)
              → App sends a 6-digit PIN via WhatsApp
              → User enters PIN to confirm → users.whatsapp_verified = true
              → phone_whatsapp stored in Supabase Vault
              (This step is required — without it, expense alerts cannot be sent)

      Step 3: Setup household
              [Solo — solo quiero controlar mis gastos]
              [Pareja — invitar a mi pareja por email]
              → Invite: creates household_invites record, sends email with link
              → Partner clicks link → token validated → joins household as 'member'

      Step 4: Add bank account(s)
              Bank name + account type:
              [Cuenta personal]  [Cuenta conjunta]
              → email_sender_pattern configured per bank
              → If joint: enable monthly budget tracker
              → Connect Fintoc for reconciliation (optional)

  → Existing user? → Dashboard
```

---

*Design approved: 2026-03-10*
*v2 — post spec review fixes applied: 2026-03-10*
*Next step: Implementation plan*
