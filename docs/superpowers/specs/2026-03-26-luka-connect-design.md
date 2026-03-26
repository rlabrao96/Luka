# Luka Connect — Design Spec

> Direct bank connection service for Luka. Replaces Fintoc with browser-based bank scraping.
> Date: 2026-03-26

---

## Overview

Luka Connect is a standalone, stateless Node.js service that logs into Chilean banks via browser automation (Puppeteer + Chromium) and returns raw transaction data. It lives in its own repo (`luka-connect`), deployed as a Dockerized service on Railway.

Luka's FastAPI backend orchestrates everything: credential storage, sync scheduling, movement-to-transaction mapping, and reconciliation with the existing email pipeline. Luka Connect has no database and no business logic — it only knows how to talk to banks.

### Why

- Fintoc cannot provide credit card transactions for individuals (checking/sight only)
- Fintoc was running on sandbox data — never provided real production value
- The bank scraper provides comprehensive coverage: checking (CLP + USD), credit cards (billed + unbilled), line of credit, balances
- Email pipeline stays for real-time categorized alerts; Connect handles daily comprehensive sync

---

## Architecture

```
User → Luka Frontend → Luka Backend (FastAPI)
                            │
                            ├── bank_credentials table (AES-256-GCM encrypted)
                            ├── ARQ cron: schedule_connect_syncs (hourly)
                            ├── ARQ job: run_connect_sync
                            │       │
                            │       ├── decrypt credentials
                            │       ├── WhatsApp 2FA nudge
                            │       └── POST /scrape → Luka Connect
                            │                              │
                            │                              └── Node.js + Puppeteer + Chromium
                            │                                  (login, scrape, return JSON)
                            │
                            ├── POST /webhooks/luka-connect (callback)
                            │       ├── map movements → transactions
                            │       ├── dedup + reconcile with email txns
                            │       └── LLM categorize new-only txns
                            │
                            └── Email pipeline (unchanged, parallel)
```

### Two Pipelines

| Pipeline | Purpose | Trigger | Latency |
|----------|---------|---------|---------|
| Email | Real-time categorized alerts + WhatsApp | Gmail/Outlook push | ~1-3 seconds |
| Luka Connect | Comprehensive daily sync (all account types) | ARQ cron (daily) or manual | ~2-3 minutes |

Email is the "winner" when both capture the same transaction — it arrived first and already has a category. Connect enriches email transactions with balance, time, and account data. Connect-only transactions get LLM categorized as new.

---

## Luka Connect Service (`luka-connect` repo)

### Endpoints

```
POST /scrape
  Headers: X-API-Key: <shared secret>
  Body: {
    bank: "bchile",
    rut: "12345678-9",
    password: "...",
    mode: "full" | "recent",
    callbackUrl: "https://luka-backend/webhooks/luka-connect" | null,
    jobId: "uuid"
  }

  Sync response (mode=full, callbackUrl=null):
    { success, movements[], balances{}, creditCards{} }

  Async response (mode=recent, with callbackUrl):
    { jobId, status: "started" }
    → POSTs to callbackUrl:
      { jobId, status: "awaiting_2fa" }
      { jobId, status: "completed", movements[], balances{}, creditCards{} }
      { jobId, status: "failed", error: "2fa_timeout" | "login_failed" | "bank_error" }

GET /health
  → { status: "ok", chromium: true }
```

### Sync vs Async

- **Initial connection (onboarding):** Synchronous. `mode=full`, `callbackUrl=null`. Frontend polls `GET /bank-connect/sync-status` on Luka backend. Returns 3 months of history.
- **Scheduled/manual syncs:** Asynchronous. `mode=recent`, with `callbackUrl`. Returns last 1-2 days. Luka Connect POSTs callback when done.

### Security

- No public access. Only Luka backend calls it via shared API key.
- Credentials come in the request body, exist only in memory during the scrape, never persisted by Connect.
- HTTPS between services. Railway private networking when possible.

### Tech Stack

- Node.js 20 + Express/Fastify (thin API layer)
- TypeScript
- Puppeteer + bundled Chromium
- Xvfb (virtual framebuffer for headful mode)
- Docker (based on `node:20-slim` + Chromium deps, ~800MB image)

### Repo Structure

```
luka-connect/
├── src/
│   ├── index.ts          # Express app, /scrape + /health
│   ├── scraper.ts        # Browser lifecycle, dispatches to bank modules
│   ├── banks/
│   │   ├── bchile.ts     # Banco de Chile (enhanced, primary)
│   │   ├── bci.ts        # Copied from fork
│   │   ├── santander.ts  # Copied from fork
│   │   ├── itau.ts       # Copied from fork
│   │   ├── estado.ts     # Copied from fork
│   │   └── ...           # All 9 bank files from fork
│   └── types.ts          # Movement, Balance, CreditCard types
├── Dockerfile
├── docker-compose.yml    # Local dev with Chrome
├── package.json
├── tsconfig.json
└── README.md
```

### Movement Object (output format)

```json
{
  "date": "18-03-2026",
  "time": "13:36",
  "description": "Abono Api En Linea:775009764",
  "amount": 23654,
  "balance": 154277,
  "source": "account",
  "currency": "CLP",
  "accountNumber": "****7502",
  "accountName": "Cuenta Corriente Moneda Local"
}
```

Sources: `account`, `credit_card_unbilled`, `credit_card_billed`

---

## Luka Backend Changes

### New Module: `backend/modules/bank_connect/`

```
modules/bank_connect/
├── models.py      # BankCredential SQLAlchemy model
├── encryption.py  # AES-256-GCM encrypt/decrypt
├── service.py     # connect, disconnect, trigger_sync, process_callback
├── scheduler.py   # schedule_connect_syncs logic
├── mapper.py      # raw movement → Transaction mapping + dedup
└── router.py      # API endpoints
```

### New Endpoints

```
POST   /bank-connect/connect          # Store credentials + trigger initial full sync
DELETE /bank-connect/disconnect        # Hard delete credentials, stop scheduling
POST   /bank-connect/sync             # Manual sync trigger
GET    /bank-connect/sync-status       # Poll sync progress (for frontend)
GET    /bank-connect/connections        # List connected banks for current user
POST   /webhooks/luka-connect          # Callback from Luka Connect service
```

### New DB Table: `bank_credentials`

```sql
bank_credentials (
  id              uuid PK DEFAULT gen_random_uuid(),
  user_id         uuid FK → users NOT NULL,
  bank_code       varchar NOT NULL,          -- 'bchile', 'bci', etc.
  encrypted_rut   bytea NOT NULL,
  encrypted_password bytea NOT NULL,
  encryption_iv   bytea NOT NULL,
  next_sync_at    timestamptz,
  last_sync_at    timestamptz,
  last_sync_status varchar,                  -- 'success', 'failed_2fa', 'failed_login', 'failed_error'
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  UNIQUE(user_id, bank_code)
)
```

RLS policy: users can only read/delete their own rows.

### Modified Table: `transactions`

Add column: `source_type varchar DEFAULT 'email'` — values: `'email'`, `'connect'`, `'manual'`

### New ARQ Jobs

| Job | Type | Description |
|-----|------|-------------|
| `schedule_connect_syncs` | Cron (hourly) | Find users with `next_sync_at <= now()`, enqueue `run_connect_sync` for each |
| `run_connect_sync` | On-demand | Decrypt creds, send WhatsApp 2FA nudge, call Luka Connect async |

### Credential Encryption

- Algorithm: AES-256-GCM
- Key: `CONNECT_ENCRYPTION_KEY` env var (separate from other secrets)
- Per-credential random IV stored alongside ciphertext
- Decrypt only when building a `/scrape` request — never at rest in plaintext

### Movement → Transaction Mapping

For each movement from Luka Connect callback:

1. **Dedup check:** `date + normalized_description + amount + bank_account_id`
2. **Match against email txns:** amount exact + date ±1 day
   - **Match found:** Enrich email txn with balance, time, account data. Keep email's category. Skip creating duplicate.
   - **No match:** Create new transaction with `source_type='connect'`. Run LLM categorization.

### Bank Lockout Prevention

- Max 1 scrape per user per bank per hour (enforced before calling Connect)
- Single attempt per sync — no retries on failure
- 120s timeout, then graceful abort
- `failed_login` → disable auto-sync until user re-enters credentials

### Fintoc Removal

- Delete `modules/fintoc/` entirely
- Remove ARQ jobs: `run_fintoc_sync`, `import_fintoc_history`
- Migration: drop Fintoc-specific columns from `transactions` and `bank_accounts` (`fintoc_id`, `fintoc_link_id`, etc.)
- Remove `@fintoc/fintoc-js` from frontend

---

## Frontend Changes

### Onboarding Step 3: Replace Fintoc Widget

**Credential entry modal:**
```
┌─────────────────────────────────┐
│  Conectar Banco de Chile        │
│                                 │
│  RUT: [_______________]         │
│  Clave Internet: [________]     │
│                                 │
│  [Conectar]                     │
│                                 │
│  🔒 Tus datos están encriptados │
│     y solo se usan para         │
│     sincronizar tus movimientos │
└─────────────────────────────────┘
```

**Progress modal (initial sync, synchronous):**
```
┌─────────────────────────────────┐
│  Conectando con Banco de Chile  │
│  ████████░░░░░░  60%            │
│                                 │
│  Aprueba la Clave Dinámica      │
│  en tu app del banco            │
│                                 │
│  Tiempo restante: 1:45          │
└─────────────────────────────────┘
```

Frontend polls `GET /bank-connect/sync-status` every 2-3 seconds. On success → show summary → continue onboarding.

### Dashboard Additions

- **Sync status indicator** — Last sync time, next scheduled sync, current status. In sidebar or settings page.
- **Manual sync button** — "Sincronizar ahora" in settings or bank account detail. Triggers async flow + WhatsApp 2FA nudge.
- **Bank credentials management** — View connected banks, delete connection, re-enter credentials if password changed.

### Removals

- Fintoc widget and `@fintoc/fintoc-js` package
- Fintoc onboarding step
- Import status polling for Fintoc
- All Fintoc references in bank account screens

---

## Failure Modes

| Scenario | Behavior |
|----------|----------|
| 2FA timeout (120s) | Abort, notify user via WhatsApp ("sync failed, try again later"), retry at next scheduled sync |
| Wrong password | Abort, mark `failed_login`, disable auto-sync, notify user to update credentials |
| Bank website changed | Scrape fails with `bank_error`, log details, notify user |
| Luka Connect service down | Backend gets connection error, log, retry at next cycle |
| Partial scrape | Return what was collected, flag as incomplete in sync status |

---

## Data Flow Summary

### Pipeline 1: Email (real-time)
```
Bank email → Gmail/Outlook push → parse → LLM categorize →
  create transaction (source='email', has category) → WhatsApp alert
```

### Pipeline 2: Luka Connect (daily comprehensive)
```
ARQ cron → decrypt creds → WhatsApp 2FA nudge → POST /scrape →
  user approves 2FA → callback with movements →
  for each movement:
    match existing email txn? (amount + date ±1 day)
      YES → enrich with balance/time/account, keep category
      NO  → create transaction (source='connect') → LLM categorize
```

### Pipeline 3: Initial connection (one-time)
```
Onboarding → enter creds → sync POST /scrape (mode=full) →
  approve 2FA → 3 months imported → all LLM categorized → dashboard populated
```

---

## Deployment

| Service | Platform | Estimated Cost |
|---------|----------|---------------|
| Luka Connect | Railway (Docker) | ~$10-15/mo (Chrome memory) |
| Luka Backend | Railway (existing) | No change |
| Frontend | Vercel (existing) | No change |
| Database | Supabase (existing) | No change (one new table) |

---

## Scope Boundaries

**In scope:**
- Luka Connect service (repo, Docker, Railway deploy)
- Backend bank_connect module (credentials, scheduling, mapping, webhook)
- Frontend credential modal + sync status UI
- Fintoc removal
- Banco de Chile fully working

**Out of scope (future work):**
- Other banks beyond Banco de Chile (files copied but not enhanced/tested)
- Advanced retry strategies
- Multi-user concurrency optimization
- Credential rotation reminders
