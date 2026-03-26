# Luka Connect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Luka Connect as a standalone bank scraping API service, integrate it into Luka's backend (replacing Fintoc), and update the frontend with credential entry + sync UI.

**Architecture:** Luka Connect is a stateless Node.js/Express API in its own repo, wrapping the open-banking-chile fork. Luka's FastAPI backend orchestrates credentials, scheduling, and transaction mapping. The two communicate via HTTP + webhook callbacks.

**Tech Stack:** Node.js 20 + Express + Puppeteer (Connect), FastAPI + ARQ + AES-256-GCM (Backend), Next.js 14 + Tailwind (Frontend)

**Spec:** `docs/superpowers/specs/2026-03-26-luka-connect-design.md`

---

## Phase 1: Luka Connect Service (new repo)

> This phase produces a standalone, Dockerized API that can scrape banks and return JSON. Fully testable in isolation.

### Task 1: Initialize `luka-connect` repo

**Files:**
- Create: `luka-connect/package.json`
- Create: `luka-connect/tsconfig.json`
- Create: `luka-connect/.gitignore`
- Create: `luka-connect/.env.example`

- [ ] **Step 1: Create GitHub repo and clone**

```bash
gh repo create rlabrao96/luka-connect --private --clone
cd luka-connect
```

- [ ] **Step 2: Initialize Node.js project**

```bash
npm init -y
```

- [ ] **Step 3: Install dependencies**

```bash
npm install express puppeteer dotenv
npm install -D typescript @types/node @types/express tsup
```

Note: `puppeteer` (not `puppeteer-core`) — bundles Chromium automatically. The fork used `puppeteer-core` and required `CHROME_PATH`. For Docker we want the bundled version.

- [ ] **Step 4: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true,
    "resolveJsonModule": true
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Create package.json scripts and type field**

Update `package.json`:
```json
{
  "type": "module",
  "scripts": {
    "build": "tsup src/index.ts --format esm --target es2022 --clean --dts",
    "dev": "tsup src/index.ts --format esm --target es2022 --watch",
    "start": "node dist/index.js"
  }
}
```

- [ ] **Step 6: Create .env.example**

```env
PORT=3001
ALLOWED_API_KEYS=dev-key-change-me
CHROME_PATH=
```

- [ ] **Step 7: Create .gitignore**

```
node_modules/
dist/
.env
screenshots/
debug/
```

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "chore: initialize luka-connect repo with dependencies"
```

---

### Task 2: Copy scraper core from fork

**Files:**
- Create: `luka-connect/src/types.ts` (copy from fork)
- Create: `luka-connect/src/utils.ts` (copy from fork)
- Create: `luka-connect/src/infrastructure/browser.ts` (copy from fork)
- Create: `luka-connect/src/infrastructure/scraper-runner.ts` (copy from fork)
- Create: `luka-connect/src/actions/*.ts` (7 files, copy from fork)
- Create: `luka-connect/src/banks/*.ts` (9 files, copy from fork)
- Create: `luka-connect/src/registry.ts` (adapted from fork's `index.ts`)

Source fork: `test-scraper/open-banking-chile-fork/src/`

- [ ] **Step 1: Copy type definitions**

Copy `test-scraper/open-banking-chile-fork/src/types.ts` → `luka-connect/src/types.ts`

No modifications needed — types are already well-defined with `BankMovement`, `ScrapeResult`, `ScraperOptions`, `CreditCardBalance`, `BankCredentials`.

- [ ] **Step 2: Copy utils**

Copy `test-scraper/open-banking-chile-fork/src/utils.ts` → `luka-connect/src/utils.ts`

- [ ] **Step 3: Copy infrastructure layer**

```bash
mkdir -p src/infrastructure
cp ../test-scraper/open-banking-chile-fork/src/infrastructure/browser.ts src/infrastructure/
cp ../test-scraper/open-banking-chile-fork/src/infrastructure/scraper-runner.ts src/infrastructure/
```

- [ ] **Step 4: Copy actions layer**

```bash
mkdir -p src/actions
cp ../test-scraper/open-banking-chile-fork/src/actions/*.ts src/actions/
```

Files: `login.ts`, `navigation.ts`, `extraction.ts`, `pagination.ts`, `credit-card.ts`, `balance.ts`, `two-factor.ts`

- [ ] **Step 5: Copy all 9 bank files**

```bash
mkdir -p src/banks
cp ../test-scraper/open-banking-chile-fork/src/banks/*.ts src/banks/
```

Files: `bchile.ts`, `bci.ts`, `bestado.ts`, `bice.ts`, `edwards.ts`, `falabella.ts`, `itau.ts`, `santander.ts`, `scotiabank.ts`

- [ ] **Step 6: Create registry (adapted from fork's index.ts)**

Create `luka-connect/src/registry.ts` — same as fork's `src/index.ts` but without CLI-specific exports:

```typescript
import bchile from "./banks/bchile.js";
import bci from "./banks/bci.js";
import bestado from "./banks/bestado.js";
import bice from "./banks/bice.js";
import edwards from "./banks/edwards.js";
import falabella from "./banks/falabella.js";
import itau from "./banks/itau.js";
import santander from "./banks/santander.js";
import scotiabank from "./banks/scotiabank.js";
import type { BankScraper } from "./types.js";

export const banks: Record<string, BankScraper> = {
  bchile, bci, bestado, bice, edwards, falabella, itau, santander, scotiabank,
};

export function getBank(id: string): BankScraper | undefined {
  return banks[id];
}

export function listBanks(): Array<{ id: string; name: string; url: string }> {
  return Object.values(banks).map((b) => ({ id: b.id, name: b.name, url: b.url }));
}
```

- [ ] **Step 7: Build to verify everything compiles**

```bash
npm run build
```

Expected: Clean build, no errors. Fix any import path issues (`.js` extensions in imports).

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: copy scraper core from open-banking-chile fork"
```

---

### Task 3: Build the Express API layer

**Files:**
- Create: `luka-connect/src/index.ts`
- Create: `luka-connect/src/scraper.ts`
- Create: `luka-connect/src/middleware/auth.ts`

- [ ] **Step 1: Create auth middleware**

Create `luka-connect/src/middleware/auth.ts`:

```typescript
import type { Request, Response, NextFunction } from "express";

const ALLOWED_KEYS = (process.env.ALLOWED_API_KEYS || "")
  .split(",")
  .map((k) => k.trim())
  .filter(Boolean);

export function apiKeyAuth(req: Request, res: Response, next: NextFunction): void {
  const key = req.headers["x-api-key"] as string | undefined;
  if (!key || !ALLOWED_KEYS.includes(key)) {
    res.status(401).json({ error: "Invalid or missing API key" });
    return;
  }
  next();
}
```

- [ ] **Step 2: Create scraper wrapper**

Create `luka-connect/src/scraper.ts`. This manages browser lifecycle and dispatches to bank modules:

```typescript
import { getBank } from "./registry.js";
import type { ScrapeResult } from "./types.js";

interface ScrapeRequest {
  bank: string;
  rut: string;
  password: string;
  mode: "full" | "recent";
}

export async function runScrape(req: ScrapeRequest): Promise<ScrapeResult> {
  const bank = getBank(req.bank);
  if (!bank) {
    return { success: false, bank: req.bank, movements: [], error: `Unknown bank: ${req.bank}` };
  }

  const result = await bank.scrape({
    rut: req.rut,
    password: req.password,
    headful: true, // Required for some banks (calendar interaction, 2FA)
    onProgress: (step) => console.log(`[${req.bank}] ${step}`),
  });

  return result;
}
```

Note: The `mode` field ("full" vs "recent") will be used to control date ranges. For now, the scraper always fetches the maximum available. The mode distinction will be refined when we add date-range filtering in a future iteration.

- [ ] **Step 3: Create Express app with /scrape and /health endpoints**

Create `luka-connect/src/index.ts`:

```typescript
import "dotenv/config";
import express from "express";
import { apiKeyAuth } from "./middleware/auth.js";
import { runScrape } from "./scraper.js";
import type { ScrapeResult } from "./types.js";

const app = express();
app.use(express.json());

// Health check (no auth required)
app.get("/health", (_req, res) => {
  res.json({ status: "ok", chromium: true });
});

// Scrape endpoint (auth required)
app.post("/scrape", apiKeyAuth, async (req, res) => {
  const { bank, rut, password, mode, callbackUrl, jobId } = req.body;

  // Validate required fields
  if (!bank || !rut || !password) {
    res.status(400).json({ error: "Missing required fields: bank, rut, password" });
    return;
  }

  // Synchronous mode: no callbackUrl, return result directly
  if (!callbackUrl) {
    try {
      const result = await runScrape({ bank, rut, password, mode: mode || "full" });
      res.json(result);
    } catch (err: any) {
      res.status(500).json({ success: false, error: err.message });
    }
    return;
  }

  // Async mode: return immediately, POST result to callbackUrl when done
  res.json({ jobId, status: "started" });

  // Run scrape in background (not awaited)
  setImmediate(async () => {
    try {
      // Notify: awaiting 2FA
      await postCallback(callbackUrl, { jobId, status: "awaiting_2fa" });

      const result = await runScrape({ bank, rut, password, mode: mode || "recent" });

      await postCallback(callbackUrl, {
        jobId,
        status: result.success ? "completed" : "failed",
        ...(result.success
          ? { movements: result.movements, balances: result.allBalances, creditCards: result.creditCards }
          : { error: result.error }),
      });
    } catch (err: any) {
      await postCallback(callbackUrl, { jobId, status: "failed", error: err.message }).catch(() => {});
    }
  });
});

async function postCallback(url: string, body: Record<string, unknown>): Promise<void> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    console.error(`Callback failed: ${resp.status} ${await resp.text()}`);
  }
}

const PORT = parseInt(process.env.PORT || "3001", 10);
app.listen(PORT, () => {
  console.log(`Luka Connect listening on port ${PORT}`);
});
```

- [ ] **Step 4: Build and test locally**

```bash
npm run build
PORT=3001 ALLOWED_API_KEYS=test-key node dist/index.js
```

In another terminal:
```bash
# Health check
curl http://localhost:3001/health
# Expected: {"status":"ok","chromium":true}

# Auth rejection
curl -X POST http://localhost:3001/scrape -H "Content-Type: application/json" -d '{}'
# Expected: 401 {"error":"Invalid or missing API key"}

# Missing fields
curl -X POST http://localhost:3001/scrape -H "Content-Type: application/json" -H "X-API-Key: test-key" -d '{}'
# Expected: 400 {"error":"Missing required fields: bank, rut, password"}
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Express API with /scrape and /health endpoints"
```

---

### Task 4: Dockerize Luka Connect

**Files:**
- Create: `luka-connect/Dockerfile`
- Create: `luka-connect/docker-compose.yml`
- Create: `luka-connect/.dockerignore`

- [ ] **Step 1: Create .dockerignore**

```
node_modules
dist
.env
screenshots
debug
.git
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM node:20-slim

# Install Chromium dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    xvfb \
    --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*

# Set Puppeteer to use system Chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV DISPLAY=:99

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY dist/ ./dist/

EXPOSE 3001

# Start Xvfb (virtual display) and the app
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x720x24 &>/dev/null & node dist/index.js"]
```

- [ ] **Step 3: Create docker-compose.yml for local dev**

```yaml
services:
  luka-connect:
    build: .
    ports:
      - "3001:3001"
    environment:
      - PORT=3001
      - ALLOWED_API_KEYS=dev-key
    # Chromium needs extra capabilities
    cap_add:
      - SYS_ADMIN
    # Shared memory for Chrome
    shm_size: "2gb"
```

- [ ] **Step 4: Build Docker image and test**

```bash
npm run build  # Build TypeScript first
docker compose build
docker compose up -d
curl http://localhost:3001/health
# Expected: {"status":"ok","chromium":true}
docker compose down
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Docker setup with Chromium and Xvfb"
```

---

### Task 5: Deploy Luka Connect to Railway

**Files:**
- Create: `luka-connect/railway.json` (optional, Railway auto-detects Dockerfile)

- [ ] **Step 1: Push repo to GitHub**

```bash
git push -u origin main
```

- [ ] **Step 2: Create Railway project**

Go to Railway dashboard → New Project → Deploy from GitHub repo → select `luka-connect`.

Or via CLI:
```bash
railway login
railway init  # Creates new project
railway link  # Links to this repo
```

- [ ] **Step 3: Set environment variables in Railway**

```
PORT=3001
ALLOWED_API_KEYS=<generate-a-strong-key>
```

- [ ] **Step 4: Deploy and verify**

Railway auto-deploys on push. After deploy:
```bash
curl https://<railway-url>/health
# Expected: {"status":"ok","chromium":true}
```

- [ ] **Step 5: Save the deployed URL — needed for Luka backend config**

Note the Railway URL (e.g., `https://luka-connect-production.up.railway.app`). This goes into Luka backend's env as `LUKA_CONNECT_URL`.

- [ ] **Step 6: Commit railway.json if created**

```bash
git add -A && git commit -m "chore: add Railway deployment config"
```

---

## Phase 2: Luka Backend — Fintoc Removal

> Clean removal of all Fintoc code before adding the new bank_connect module. This keeps the migration clean.

### Task 6: Remove Fintoc module and tests

**Files:**
- Delete: `backend/modules/fintoc/client.py`
- Delete: `backend/modules/fintoc/classifier.py`
- Delete: `backend/modules/fintoc/reconciler.py`
- Delete: `backend/modules/fintoc/__init__.py`
- Delete: `backend/tests/test_fintoc_classifier.py`
- Delete: `backend/tests/test_fintoc_reconciler.py`
- Delete: `backend/tests/test_fintoc_client_accounts.py`
- Delete: `backend/tests/test_fintoc_import.py`

- [ ] **Step 1: Delete Fintoc module directory**

```bash
rm -rf backend/modules/fintoc/
```

- [ ] **Step 2: Delete Fintoc test files**

```bash
rm -f backend/tests/test_fintoc_classifier.py
rm -f backend/tests/test_fintoc_reconciler.py
rm -f backend/tests/test_fintoc_client_accounts.py
rm -f backend/tests/test_fintoc_import.py
```

- [ ] **Step 3: Remove Fintoc config from Settings**

In `backend/core/config.py`, remove line 22:
```python
# REMOVE this line:
fintoc_api_key: str = ""
```

- [ ] **Step 4: Remove Fintoc jobs from worker**

In `backend/worker.py`:
- Remove `import_fintoc_history` and `run_fintoc_sync` from imports (lines 7, 11)
- Remove `import_fintoc_history` from `functions` list (line 25)
- Remove `cron(run_fintoc_sync, ...)` from `cron_jobs` (line 30)
- Update `job_timeout` comment (line 36) — no longer about Fintoc

Updated `backend/worker.py`:
```python
import redis.asyncio as aioredis
from arq import cron
from arq.connections import RedisSettings
from core.config import settings
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
    send_invite_email,
)


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = [process_email, send_invite_email]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),  # 3am daily
        cron(purge_raw_emails, minute=0),  # every hour
        cron(cleanup_processed_webhooks, hour=4, minute=0),  # 4am daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300
```

- [ ] **Step 5: Remove Fintoc job functions from tasks.py**

In `backend/jobs/tasks.py`:
- Remove the `run_fintoc_sync` function entirely (~lines 435-542)
- Remove the `import_fintoc_history` function entirely (~lines 545-696)
- Remove any Fintoc-related imports at the top of the file

- [ ] **Step 6: Simplify process_email — remove Fintoc status logic**

In `backend/jobs/tasks.py`, in the `process_email` function (~lines 291-293), change:

```python
# OLD:
has_fintoc = bank_account is not None
txn_status = "pending" if has_fintoc else "settled"
```

to:

```python
# NEW: All email transactions are settled (no Fintoc reconciliation)
txn_status = "settled"
```

Also remove the now-unused `has_fintoc` variable if referenced elsewhere in the function.

- [ ] **Step 7: Remove Fintoc endpoints from bank_accounts router**

In `backend/modules/bank_accounts/router.py`:
- Remove `from modules.fintoc.client import FintocClient` import
- Remove `GET /fintoc/accounts` endpoint
- Remove `POST /fintoc/connect` endpoint
- Remove `POST /webhooks/fintoc-link` endpoint
- Remove `POST /sync-balances` endpoint (this was Fintoc-specific)
- Remove `FintocAccountIn`, `ConnectFintocRequest` Pydantic models
- Remove import-status related logic (stale guard, etc.)

Keep: `GET /` (list bank accounts), `POST /` (create), `PATCH /{id}` (update), `DELETE /{id}` (delete)

- [ ] **Step 8: Run tests to verify nothing is broken**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All remaining tests pass. Fintoc tests are deleted so they won't run. Any test that referenced Fintoc indirectly (e.g., `test_bank_accounts_routes.py`) may need fixes — check for Fintoc-specific endpoint tests and remove them.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "refactor: remove Fintoc module, jobs, and endpoints"
```

---

### Task 7: Database migration — drop Fintoc columns, add bank_credentials + source_type

**Files:**
- Create: `backend/alembic/versions/017_remove_fintoc_add_bank_connect.py`
- Modify: `backend/modules/transactions/models.py`
- Modify: `backend/modules/households/models.py` (BankAccount model)

- [ ] **Step 1: Create Alembic migration**

Create `backend/alembic/versions/017_remove_fintoc_add_bank_connect.py`:

```python
"""Remove Fintoc columns, add bank_credentials table and source_type.

Revision ID: 017
Revises: 016
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision = "017"
down_revision = "016"


def upgrade() -> None:
    # --- Drop Fintoc columns from bank_accounts ---
    op.drop_column("bank_accounts", "fintoc_link_id")
    op.drop_column("bank_accounts", "fintoc_account_id")
    op.drop_column("bank_accounts", "import_status")
    op.drop_column("bank_accounts", "last_synced_at")
    op.drop_column("bank_accounts", "import_started_at")
    op.drop_column("bank_accounts", "balance_available")
    op.drop_column("bank_accounts", "balance_current")

    # --- Drop Fintoc column from transactions ---
    op.drop_column("transactions", "fintoc_id")

    # --- Add source_type to transactions ---
    op.add_column(
        "transactions",
        sa.Column("source_type", sa.String(), nullable=False, server_default="email"),
    )

    # --- Create bank_credentials table ---
    op.create_table(
        "bank_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bank_code", sa.String(), nullable=False),
        sa.Column("encrypted_rut", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_iv", sa.LargeBinary(), nullable=False),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(), nullable=True),
        sa.Column("current_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "bank_code"),
    )

    # --- RLS policy for bank_credentials ---
    op.execute("""
        ALTER TABLE bank_credentials ENABLE ROW LEVEL SECURITY;
    """)
    op.execute("""
        CREATE POLICY bank_credentials_user_policy ON bank_credentials
        FOR ALL USING (user_id = auth.uid());
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS bank_credentials_user_policy ON bank_credentials;")
    op.execute("ALTER TABLE bank_credentials DISABLE ROW LEVEL SECURITY;")
    op.drop_table("bank_credentials")
    op.drop_column("transactions", "source_type")
    op.add_column("transactions", sa.Column("fintoc_id", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_current", sa.Integer(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_available", sa.Integer(), nullable=True))
    op.add_column("bank_accounts", sa.Column("import_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bank_accounts", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bank_accounts", sa.Column("import_status", sa.String(), nullable=False, server_default="done"))
    op.add_column("bank_accounts", sa.Column("fintoc_account_id", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("fintoc_link_id", sa.String(), nullable=True))
```

- [ ] **Step 2: Update Transaction model**

In `backend/modules/transactions/models.py`:
- Remove `fintoc_id` column (line 26)
- Change `source` comment to reflect new values: `gmail|outlook|connect|manual`
- Add `source_type` column:

```python
source_type: Mapped[str] = mapped_column(String, nullable=False, default="email", server_default="email")
```

Keep `transaction_type` (expense/income/transfer) — it's used by budgets.
Keep `transfer_to_account_id` — useful for transfer tracking.

- [ ] **Step 3: Update BankAccount model**

In `backend/modules/households/models.py`, remove from `BankAccount` class:
- `fintoc_link_id` (line 53)
- `fintoc_account_id` (line 54)
- `import_status` (lines 61-63)
- `last_synced_at` (line 64)
- `import_started_at` (lines 65-66)
- `balance_available` (line 68)
- `balance_current` (line 69)

Keep: `id`, `household_id`, `user_id`, `bank_name`, `account_type`, `cardholder_name`, `email_sender_pattern`, `account_kind`, `account_number`, `currency`, `is_active`, `created_at`

- [ ] **Step 4: Run migration**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/ -v
```

Fix any test failures from removed columns (e.g., tests that set `fintoc_id` or `import_status`).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: migration 017 — drop Fintoc columns, add bank_credentials table"
```

---

## Phase 3: Luka Backend — Bank Connect Module

> New module that handles credentials, syncing, and transaction mapping.

### Task 8: BankCredential model + encryption

**Files:**
- Create: `backend/modules/bank_connect/__init__.py`
- Create: `backend/modules/bank_connect/models.py`
- Create: `backend/modules/bank_connect/encryption.py`
- Create: `backend/tests/test_bank_connect_encryption.py`
- Modify: `backend/core/config.py`

- [ ] **Step 1: Write failing test for encryption**

Create `backend/tests/test_bank_connect_encryption.py`:

```python
import os
import pytest

os.environ.setdefault("CONNECT_ENCRYPTION_KEY", "a" * 64)  # 32 bytes hex

from modules.bank_connect.encryption import encrypt, decrypt


def test_encrypt_decrypt_roundtrip():
    plaintext = "12345678-9"
    encrypted, iv = encrypt(plaintext)
    assert encrypted != plaintext.encode()
    assert len(iv) == 12  # GCM standard nonce
    result = decrypt(encrypted, iv)
    assert result == plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    e1, iv1 = encrypt("password1")
    e2, iv2 = encrypt("password2")
    assert e1 != e2


def test_wrong_iv_fails():
    encrypted, iv = encrypt("secret")
    wrong_iv = os.urandom(12)
    with pytest.raises(Exception):
        decrypt(encrypted, wrong_iv)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_bank_connect_encryption.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Add config field**

In `backend/core/config.py`, add:

```python
connect_encryption_key: str = ""  # 32-byte hex key for AES-256-GCM
luka_connect_url: str = "http://localhost:3001"
luka_connect_api_key: str = ""
backend_public_url: str = "http://localhost:8000"  # Used for webhook callback URLs
```

- [ ] **Step 4: Implement encryption module**

Create `backend/modules/bank_connect/__init__.py` (empty).

Create `backend/modules/bank_connect/encryption.py`:

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.config import settings


def _get_key() -> bytes:
    key_hex = settings.connect_encryption_key
    if not key_hex or len(key_hex) != 64:
        raise ValueError("CONNECT_ENCRYPTION_KEY must be a 64-char hex string (32 bytes)")
    return bytes.fromhex(key_hex)


def encrypt(plaintext: str) -> tuple[bytes, bytes]:
    """Encrypt plaintext with AES-256-GCM. Returns (ciphertext, iv)."""
    key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return ciphertext, iv


def decrypt(ciphertext: bytes, iv: bytes) -> str:
    """Decrypt ciphertext with AES-256-GCM. Returns plaintext string."""
    key = _get_key()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode("utf-8")
```

- [ ] **Step 5: Add cryptography dependency**

```bash
cd backend && pip install cryptography && pip freeze | grep cryptography >> requirements.txt
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_bank_connect_encryption.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 7: Create BankCredential model**

Create `backend/modules/bank_connect/models.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class BankCredential(Base):
    __tablename__ = "bank_credentials"
    __table_args__ = (UniqueConstraint("user_id", "bank_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_code: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_rut: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String, nullable=True)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: bank_connect encryption + BankCredential model"
```

---

### Task 9: Bank Connect service layer

**Files:**
- Create: `backend/modules/bank_connect/service.py`
- Create: `backend/tests/test_bank_connect_service.py`

- [ ] **Step 1: Write failing test for connect flow**

Create `backend/tests/test_bank_connect_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from modules.bank_connect.service import store_credentials, delete_credentials, get_connection_status


@pytest.mark.asyncio
async def test_store_credentials_encrypts_and_saves(mock_db):
    """store_credentials should encrypt rut+password and create a BankCredential row."""
    user_id = "test-user-id"
    result = await store_credentials(
        db=mock_db, user_id=user_id, bank_code="bchile", rut="12345678-9", password="secret123"
    )
    assert result.bank_code == "bchile"
    assert result.encrypted_rut != b"12345678-9"  # Should be encrypted
    assert result.next_sync_at is not None  # Should be scheduled


@pytest.mark.asyncio
async def test_delete_credentials_hard_deletes(mock_db):
    """delete_credentials should remove the row entirely."""
    # Store first, then delete
    cred = await store_credentials(
        db=mock_db, user_id="test-user", bank_code="bchile", rut="123", password="abc"
    )
    await delete_credentials(db=mock_db, user_id="test-user", bank_code="bchile")
    status = await get_connection_status(db=mock_db, user_id="test-user", bank_code="bchile")
    assert status is None
```

Note: `mock_db` fixture will need to be defined or adapted from existing test fixtures. Check `backend/tests/conftest.py` for existing patterns.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_bank_connect_service.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement service**

Create `backend/modules/bank_connect/service.py`:

```python
import uuid
from datetime import datetime, timedelta, timezone
from random import randint

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.bank_connect.encryption import encrypt, decrypt
from modules.bank_connect.models import BankCredential

# Rate limit: 1 scrape per user per bank per hour
_MIN_SYNC_INTERVAL = timedelta(hours=1)


async def store_credentials(
    db: AsyncSession, user_id: str, bank_code: str, rut: str, password: str
) -> BankCredential:
    """Encrypt and store bank credentials. Sets initial sync schedule."""
    encrypted_rut, iv_rut = encrypt(rut)
    encrypted_password, iv_password = encrypt(password)
    # Use same IV for both (simplification) — in production, use separate IVs
    # For now, we concatenate: iv = iv_rut (12 bytes) + iv_password (12 bytes) = 24 bytes
    iv = iv_rut + iv_password

    # Schedule first sync: random time in next 24h
    next_sync = _random_next_sync()

    cred = BankCredential(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        bank_code=bank_code,
        encrypted_rut=encrypted_rut,
        encrypted_password=encrypted_password,
        encryption_iv=iv,
        next_sync_at=next_sync,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def delete_credentials(db: AsyncSession, user_id: str, bank_code: str) -> None:
    """Hard delete credentials for a user+bank."""
    await db.execute(
        delete(BankCredential).where(
            BankCredential.user_id == uuid.UUID(user_id),
            BankCredential.bank_code == bank_code,
        )
    )
    await db.commit()


async def get_connection_status(
    db: AsyncSession, user_id: str, bank_code: str
) -> BankCredential | None:
    """Get credential record (without decrypting)."""
    result = await db.execute(
        select(BankCredential).where(
            BankCredential.user_id == uuid.UUID(user_id),
            BankCredential.bank_code == bank_code,
        )
    )
    return result.scalar_one_or_none()


async def get_user_connections(db: AsyncSession, user_id: str) -> list[BankCredential]:
    """List all bank connections for a user."""
    result = await db.execute(
        select(BankCredential).where(BankCredential.user_id == uuid.UUID(user_id))
    )
    return list(result.scalars().all())


async def decrypt_credentials(cred: BankCredential) -> tuple[str, str]:
    """Decrypt rut and password from a BankCredential."""
    iv_rut = cred.encryption_iv[:12]
    iv_password = cred.encryption_iv[12:24]
    rut = decrypt(cred.encrypted_rut, iv_rut)
    password = decrypt(cred.encrypted_password, iv_password)
    return rut, password


async def trigger_sync(
    db: AsyncSession,
    cred: BankCredential,
    mode: str = "recent",
    callback_url: str | None = None,
) -> dict:
    """Call Luka Connect to start a scrape. Returns sync response."""
    # Rate limit check
    if cred.last_sync_at and (datetime.now(timezone.utc) - cred.last_sync_at) < _MIN_SYNC_INTERVAL:
        return {"error": "rate_limited", "message": "Max 1 sync per hour"}

    rut, password = await decrypt_credentials(cred)
    job_id = str(uuid.uuid4())

    # Update credential with job tracking
    cred.current_job_id = uuid.UUID(job_id)
    cred.last_sync_status = "in_progress"
    await db.commit()

    payload = {
        "bank": cred.bank_code,
        "rut": rut,
        "password": password,
        "mode": mode,
        "jobId": job_id,
    }
    if callback_url:
        payload["callbackUrl"] = callback_url

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        resp = await client.post(
            f"{settings.luka_connect_url}/scrape",
            json=payload,
            headers={"X-API-Key": settings.luka_connect_api_key},
        )
        return resp.json()


def _random_next_sync() -> datetime:
    """Random time in the next 24h window."""
    now = datetime.now(timezone.utc)
    offset_minutes = randint(60, 1440)  # 1-24 hours from now
    return now + timedelta(minutes=offset_minutes)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_bank_connect_service.py -v
```

Adapt test fixtures as needed for your DB session mock pattern.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: bank_connect service — store, delete, decrypt, trigger sync"
```

---

### Task 10: Movement mapper + dedup

**Files:**
- Create: `backend/modules/bank_connect/mapper.py`
- Create: `backend/tests/test_bank_connect_mapper.py`

- [ ] **Step 1: Write failing test for mapper**

Create `backend/tests/test_bank_connect_mapper.py`:

```python
import pytest
from datetime import datetime, timezone
from modules.bank_connect.mapper import map_movement_to_transaction, normalize_description


def test_normalize_description():
    assert normalize_description("  Compra STARBUCKS  SANTIAGO  ") == "compra starbucks santiago"
    assert normalize_description("Abono Api En Linea:775009764") == "abono api en linea:775009764"


def test_map_movement_basic():
    movement = {
        "date": "18-03-2026",
        "time": "13:36",
        "description": "Compra en STARBUCKS",
        "amount": -3500,
        "balance": 150000,
        "source": "account",
        "currency": "CLP",
        "accountNumber": "****7502",
        "accountName": "Cuenta Corriente",
    }
    result = map_movement_to_transaction(movement, user_id="uid", household_id="hid", bank_account_id="baid")
    assert result["raw_merchant_name"] == "Compra en STARBUCKS"
    assert result["amount"] == -3500
    assert result["currency"] == "CLP"
    assert result["source_type"] == "connect"
    assert result["transaction_date"].year == 2026
    assert result["transaction_date"].month == 3
    assert result["transaction_date"].day == 18
    assert result["transaction_date"].hour == 13
    assert result["transaction_date"].minute == 36


def test_dedup_key():
    from modules.bank_connect.mapper import dedup_key
    key = dedup_key("18-03-2026", "compra starbucks", -3500, "baid")
    assert isinstance(key, str)
    assert len(key) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_bank_connect_mapper.py -v
```

- [ ] **Step 3: Implement mapper**

Create `backend/modules/bank_connect/mapper.py`:

```python
import hashlib
from datetime import datetime, timezone


def normalize_description(desc: str) -> str:
    """Normalize description for dedup comparison."""
    return " ".join(desc.strip().lower().split())


def dedup_key(date_str: str, normalized_desc: str, amount: float, bank_account_id: str) -> str:
    """Generate a dedup key from movement fields."""
    raw = f"{date_str}|{normalized_desc}|{amount}|{bank_account_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_movement_date(date_str: str, time_str: str | None = None) -> datetime:
    """Parse dd-mm-yyyy date and optional HH:MM time into a timezone-aware datetime."""
    day, month, year = date_str.split("-")
    hour, minute = (0, 0)
    if time_str:
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    return datetime(int(year), int(month), int(day), hour, minute, tzinfo=timezone.utc)


def map_movement_to_transaction(
    movement: dict,
    user_id: str,
    household_id: str,
    bank_account_id: str | None,
) -> dict:
    """Map a raw Luka Connect movement to transaction fields."""
    return {
        "user_id": user_id,
        "household_id": household_id,
        "bank_account_id": bank_account_id,
        "raw_merchant_name": movement["description"],
        "amount": movement["amount"],
        "currency": movement.get("currency", "CLP"),
        "transaction_date": parse_movement_date(movement["date"], movement.get("time")),
        "source": "connect",
        "source_type": "connect",
        "status": "settled",
        "transaction_type": "expense" if movement["amount"] < 0 else "income",
    }
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_bank_connect_mapper.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: bank_connect mapper — movement to transaction + dedup"
```

---

### Task 11: Bank Connect router (API endpoints)

**Files:**
- Create: `backend/modules/bank_connect/router.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Create router**

Create `backend/modules/bank_connect/router.py`:

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from core.config import settings
from modules.bank_connect.service import (
    store_credentials,
    delete_credentials,
    get_connection_status,
    get_user_connections,
    trigger_sync,
)

router = APIRouter(prefix="/bank-connect", tags=["bank-connect"])


class ConnectRequest(BaseModel):
    bank_code: str
    rut: str
    password: str


class SyncStatusResponse(BaseModel):
    bank_code: str
    last_sync_at: str | None
    last_sync_status: str | None
    current_job_id: str | None
    next_sync_at: str | None


@router.post("/connect")
async def connect_bank(
    body: ConnectRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted credentials and trigger initial full sync (async).
    Frontend polls GET /bank-connect/sync-status to track progress."""
    cred = await store_credentials(
        db=db,
        user_id=str(user.id),
        bank_code=body.bank_code,
        rut=body.rut,
        password=body.password,
    )

    # Trigger async initial sync with callback — frontend polls sync-status
    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    result = await trigger_sync(db=db, cred=cred, mode="full", callback_url=callback_url)
    return {"status": "started", "bank_code": body.bank_code, "job_id": str(cred.current_job_id)}


@router.delete("/disconnect")
async def disconnect_bank(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete credentials and stop scheduling."""
    await delete_credentials(db=db, user_id=str(user.id), bank_code=bank_code)
    return {"status": "disconnected"}


@router.post("/sync")
async def manual_sync(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync (async with webhook callback)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found for this bank")

    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    result = await trigger_sync(db=db, cred=cred, mode="recent", callback_url=callback_url)
    return result


@router.get("/sync-status")
async def sync_status(
    bank_code: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll sync progress (for frontend during initial connection)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found")
    return SyncStatusResponse(
        bank_code=cred.bank_code,
        last_sync_at=cred.last_sync_at.isoformat() if cred.last_sync_at else None,
        last_sync_status=cred.last_sync_status,
        current_job_id=str(cred.current_job_id) if cred.current_job_id else None,
        next_sync_at=cred.next_sync_at.isoformat() if cred.next_sync_at else None,
    )


@router.get("/connections")
async def list_connections(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected banks for the current user."""
    connections = await get_user_connections(db=db, user_id=str(user.id))
    return [
        {
            "bank_code": c.bank_code,
            "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
            "last_sync_status": c.last_sync_status,
            "next_sync_at": c.next_sync_at.isoformat() if c.next_sync_at else None,
        }
        for c in connections
    ]
```

- [ ] **Step 2: Create webhook handler for Luka Connect callbacks**

Add to `backend/modules/bank_connect/router.py`:

```python
from modules.bank_connect.mapper import (
    map_movement_to_transaction,
    normalize_description,
    dedup_key,
    parse_movement_date,
)
from modules.transactions.models import Transaction
from modules.merchants.service import lookup_merchant
from sqlalchemy import select, and_
from datetime import timedelta


class ConnectCallback(BaseModel):
    jobId: str
    status: str  # "awaiting_2fa", "completed", "failed"
    movements: list[dict] | None = None
    balances: dict | None = None
    creditCards: list[dict] | None = None
    error: str | None = None


@router.post("/webhooks/luka-connect")
async def handle_connect_callback(
    body: ConnectCallback,
    db: AsyncSession = Depends(get_db),
):
    """Receive callback from Luka Connect after a scrape completes."""
    # Find credential by job ID
    result = await db.execute(
        select(BankCredential).where(BankCredential.current_job_id == uuid.UUID(body.jobId))
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Unknown job ID")

    if body.status == "awaiting_2fa":
        cred.last_sync_status = "awaiting_2fa"
        await db.commit()
        return {"status": "ack"}

    if body.status == "failed":
        cred.last_sync_status = f"failed_{body.error or 'unknown'}"
        cred.current_job_id = None
        if body.error == "login_failed":
            cred.next_sync_at = None  # Disable auto-sync
        await db.commit()
        return {"status": "ack"}

    if body.status == "completed" and body.movements:
        created, enriched, skipped = await _process_movements(
            db=db, cred=cred, movements=body.movements
        )
        cred.last_sync_at = datetime.now(timezone.utc)
        cred.last_sync_status = "success"
        cred.current_job_id = None
        cred.next_sync_at = _random_next_sync()
        await db.commit()
        return {"status": "ok", "created": created, "enriched": enriched, "skipped": skipped}

    return {"status": "ack"}


async def _process_movements(
    db: AsyncSession, cred: BankCredential, movements: list[dict]
) -> tuple[int, int, int]:
    """Process movements: dedup, reconcile with email txns, create new ones."""
    from modules.bank_connect.service import _random_next_sync
    from datetime import datetime, timezone

    created = 0
    enriched = 0
    skipped = 0

    for mov in movements:
        norm_desc = normalize_description(mov["description"])
        dk = dedup_key(mov["date"], norm_desc, mov["amount"], str(cred.user_id))

        # Check for exact duplicate (same movement already imported)
        existing = await db.execute(
            select(Transaction).where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "connect",
                Transaction.raw_merchant_name == mov["description"],
                Transaction.amount == mov["amount"],
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        # Check for email match (amount exact + date ±1 day)
        mov_date = parse_movement_date(mov["date"], mov.get("time"))
        email_match = await db.execute(
            select(Transaction).where(
                Transaction.user_id == cred.user_id,
                Transaction.source_type == "email",
                Transaction.amount == mov["amount"],
                Transaction.transaction_date >= mov_date - timedelta(days=1),
                Transaction.transaction_date <= mov_date + timedelta(days=1),
            ).limit(1)
        )
        email_txn = email_match.scalar_one_or_none()

        if email_txn:
            # Enrich email transaction with Connect data
            email_txn.transaction_date = mov_date  # More precise time
            enriched += 1
        else:
            # Resolve household_id from user's household membership
            from modules.households.models import HouseholdMember, BankAccount
            hm_result = await db.execute(
                select(HouseholdMember.household_id).where(HouseholdMember.user_id == cred.user_id)
            )
            household_id = hm_result.scalar_one_or_none()
            if not household_id:
                skipped += 1
                continue

            # Match accountNumber to existing bank_accounts
            ba_id = None
            if mov.get("accountNumber"):
                ba_result = await db.execute(
                    select(BankAccount.id).where(
                        BankAccount.user_id == cred.user_id,
                        BankAccount.account_number == mov["accountNumber"],
                    )
                )
                ba_id = ba_result.scalar_one_or_none()

            # Create new transaction from Connect
            txn_data = map_movement_to_transaction(
                movement=mov,
                user_id=str(cred.user_id),
                household_id=str(household_id),
                bank_account_id=str(ba_id) if ba_id else None,
            )
            txn = Transaction(**txn_data)
            db.add(txn)
            created += 1

    await db.commit()
    return created, enriched, skipped
```

- [ ] **Step 3: Register router in main.py**

In `backend/main.py`, add:

```python
from modules.bank_connect.router import router as bank_connect_router
app.include_router(bank_connect_router)
```

Follow the existing pattern for other routers in `main.py`.

- [ ] **Step 4: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: bank_connect router — connect, disconnect, sync, webhook handler"
```

---

### Task 12: ARQ jobs for scheduled syncs

**Files:**
- Create: `backend/modules/bank_connect/scheduler.py`
- Modify: `backend/jobs/tasks.py` (add new jobs)
- Modify: `backend/worker.py` (register new jobs)

- [ ] **Step 1: Create scheduler logic**

Create `backend/modules/bank_connect/scheduler.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from modules.bank_connect.models import BankCredential


async def get_due_syncs(db: AsyncSession) -> list[BankCredential]:
    """Find all credentials due for sync (next_sync_at <= now)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(BankCredential).where(
            BankCredential.next_sync_at <= now,
            BankCredential.next_sync_at.isnot(None),
            BankCredential.current_job_id.is_(None),  # Not already syncing
            BankCredential.last_sync_status != "failed_login",  # Not disabled
        )
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Add ARQ jobs to tasks.py**

Add to `backend/jobs/tasks.py`:

```python
async def schedule_connect_syncs(ctx: dict) -> None:
    """Hourly cron: find users due for sync, enqueue run_connect_sync for each."""
    async with AsyncSessionLocal() as db:
        from modules.bank_connect.scheduler import get_due_syncs
        due = await get_due_syncs(db)
        redis = ctx["redis"]  # ArqRedis pool from worker startup
        for cred in due:
            await redis.enqueue_job(
                "run_connect_sync",
                str(cred.id),
            )
        if due:
            print(f"[SCHEDULE_CONNECT_SYNCS] Enqueued {len(due)} syncs", flush=True)


async def run_connect_sync(ctx: dict, credential_id: str) -> None:
    """Run a single bank sync: decrypt creds, send WhatsApp 2FA nudge, call Luka Connect."""
    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.service import trigger_sync
    from modules.whatsapp.sender import send_text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BankCredential).where(BankCredential.id == credential_id)
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return

        # Send WhatsApp 2FA nudge to user
        from modules.auth.models import User
        user_result = await db.execute(select(User).where(User.id == cred.user_id))
        user = user_result.scalar_one_or_none()
        if user and user.phone_whatsapp:
            await send_text(
                to=user.phone_whatsapp,
                body=(
                    "Luka está sincronizando tu banco. "
                    "Aprueba la Clave Dinámica en tu app del banco."
                ),
            )

        # Trigger async scrape with callback
        callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
        await trigger_sync(db=db, cred=cred, mode="recent", callback_url=callback_url)
```

- [ ] **Step 3: Register jobs in worker.py**

Update `backend/worker.py`:

```python
from jobs.tasks import (
    process_email,
    renew_mail_watches,
    purge_raw_emails,
    cleanup_processed_webhooks,
    send_invite_email,
    schedule_connect_syncs,
    run_connect_sync,
)

class WorkerSettings:
    functions = [process_email, send_invite_email, run_connect_sync]
    cron_jobs = [
        cron(renew_mail_watches, hour=3, minute=0),
        cron(purge_raw_emails, minute=0),
        cron(cleanup_processed_webhooks, hour=4, minute=0),
        cron(schedule_connect_syncs, minute=0),  # Every hour, check for due syncs
    ]
    ...
    job_timeout = 300  # 5 min — enough for bank scrape + 2FA wait
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: ARQ jobs — schedule_connect_syncs + run_connect_sync"
```

---

## Phase 4: Frontend Changes

> Replace Fintoc widget with Luka Connect credential modal + sync UI.

### Task 13: Remove Fintoc from frontend

**Files:**
- Delete: `frontend/app/lib/fintoc.d.ts`
- Delete: `frontend/app/(dashboard)/components/FintocAccountPicker.tsx`
- Delete: `frontend/app/lib/hooks/useImportStatus.ts`
- Modify: `frontend/app/lib/api.ts` (remove Fintoc interfaces/methods)
- Modify: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`

- [ ] **Step 1: Delete Fintoc-specific files**

```bash
rm -f frontend/app/lib/fintoc.d.ts
rm -f frontend/app/(dashboard)/components/FintocAccountPicker.tsx
rm -f frontend/app/lib/hooks/useImportStatus.ts
```

- [ ] **Step 2: Remove Fintoc interfaces and methods from api.ts**

In `frontend/app/lib/api.ts`:
- Remove `FintocAccount` interface
- Remove `SelectedFintocAccount` interface
- Remove `ConnectFintocPayload` interface
- Remove `ConnectFintocResult` interface
- Remove `getFintocAccounts()` method
- Remove `connectFintocAccounts()` method
- Remove `getImportStatus()` method

- [ ] **Step 3: Add Luka Connect API methods to api.ts**

Add to `frontend/app/lib/api.ts`:

```typescript
// --- Luka Connect ---

interface ConnectBankPayload {
  bank_code: string;
  rut: string;
  password: string;
}

interface SyncStatus {
  bank_code: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  current_job_id: string | null;
  next_sync_at: string | null;
}

interface BankConnection {
  bank_code: string;
  last_sync_at: string | null;
  last_sync_status: string | null;
  next_sync_at: string | null;
}

const bankConnect = {
  connect: (payload: ConnectBankPayload) =>
    apiFetch("/bank-connect/connect", { method: "POST", body: JSON.stringify(payload) }),

  disconnect: (bankCode: string) =>
    apiFetch(`/bank-connect/disconnect?bank_code=${bankCode}`, { method: "DELETE" }),

  syncStatus: (bankCode: string): Promise<SyncStatus> =>
    apiFetch(`/bank-connect/sync-status?bank_code=${bankCode}`),

  manualSync: (bankCode: string) =>
    apiFetch(`/bank-connect/sync?bank_code=${bankCode}`, { method: "POST" }),

  connections: (): Promise<BankConnection[]> =>
    apiFetch("/bank-connect/connections"),
};
```

- [ ] **Step 4: Clean up ImportStatusBanner references**

Remove ImportStatusBanner/ImportStatusBannerClient components if they exist and remove references from any dashboard layout files.

- [ ] **Step 5: Clean up BankAccountsSection**

In `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`:
- Remove import_status checks and banners
- Remove Fintoc connect button
- Remove `formatLastSync()` if Fintoc-specific

- [ ] **Step 6: Verify frontend builds**

```bash
cd frontend && npm run build
```

Fix any TypeScript errors from removed imports.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "refactor: remove all Fintoc references from frontend"
```

---

### Task 14: Bank credential entry modal (onboarding)

**Files:**
- Modify: `frontend/app/(auth)/onboarding/connect-bank/page.tsx` (full rewrite)

- [ ] **Step 1: Rewrite connect-bank onboarding page**

Replace the Fintoc widget with a Luka-branded credential entry form. The page should:

1. Show a form with RUT + Clave Internet fields
2. On submit: call `POST /bank-connect/connect`
3. Show progress modal with 2FA instructions
4. Poll `GET /bank-connect/sync-status` every 3 seconds
5. On success: show summary ("Se importaron X movimientos") → navigate to next onboarding step

Key UI elements:
- Bank selector (dropdown, start with "Banco de Chile" only)
- RUT input (with Chilean RUT formatting)
- Password input (masked)
- "Conectar" button
- Lock icon + "Tus datos están encriptados" text
- Progress bar with countdown timer (2 min)
- "Aprueba la Clave Dinámica en tu app del banco" message

Use existing design tokens: `luka-primary` (#2563EB), `luka-light` (#EFF6FF).

Follow the existing onboarding page pattern from other steps.

- [ ] **Step 2: Test the flow manually**

Start frontend dev server, navigate through onboarding to step 3, verify:
- Form renders correctly
- Validation works (empty fields, RUT format)
- Submit calls backend (may fail if Connect isn't running — that's OK)

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: replace Fintoc widget with bank credential entry modal"
```

---

### Task 15: Sync status UI in settings

**Files:**
- Modify: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`
- Create: `frontend/app/lib/hooks/useSyncStatus.ts` (optional, replaces useImportStatus)

- [ ] **Step 1: Create useSyncStatus hook**

Create `frontend/app/lib/hooks/useSyncStatus.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function useSyncStatus(bankCode: string) {
  return useQuery({
    queryKey: ["sync-status", bankCode],
    queryFn: () => api.bankConnect.syncStatus(bankCode),
    refetchInterval: (data) =>
      data?.current_job_id ? 3000 : false, // Poll while syncing
    enabled: !!bankCode,
  });
}
```

- [ ] **Step 2: Update BankAccountsSection with sync status**

Add to the bank accounts settings page:
- Show last sync time and status for each connected bank
- "Sincronizar ahora" button that calls `api.bankConnect.manualSync()`
- "Desconectar" button that calls `api.bankConnect.disconnect()`
- Visual indicator: green dot = last sync success, red = failed, yellow = in progress

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: add sync status UI and manual sync to bank settings"
```

---

## Phase 5: Integration Testing + Deploy

### Task 16: End-to-end integration test

- [ ] **Step 1: Verify Luka Connect is deployed and healthy**

```bash
curl https://<luka-connect-url>/health
```

- [ ] **Step 2: Set backend env vars**

Add to Luka backend (Railway):
```
LUKA_CONNECT_URL=https://<luka-connect-url>
LUKA_CONNECT_API_KEY=<the-key-from-connect>
CONNECT_ENCRYPTION_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
```

- [ ] **Step 3: Run migration on production**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 4: Deploy backend to Railway**

Push changes, Railway auto-deploys.

- [ ] **Step 5: Deploy frontend to Vercel**

Push changes, Vercel auto-deploys.

- [ ] **Step 6: Test full flow**

1. Log into Luka
2. Go through onboarding → connect bank step
3. Enter Banco de Chile credentials
4. Approve 2FA on phone
5. Verify transactions appear in dashboard
6. Verify WhatsApp alerts still work for new emails
7. Test manual sync from settings
8. Verify disconnect works

- [ ] **Step 7: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration testing fixes for Luka Connect"
```

---

## Summary

| Phase | Tasks | What it produces |
|-------|-------|-----------------|
| 1: Luka Connect Service | 1-5 | Standalone bank scraping API, Dockerized, deployed on Railway |
| 2: Fintoc Removal | 6-7 | Clean codebase with no Fintoc references, new DB schema |
| 3: Backend Module | 8-12 | bank_connect module with encryption, service, mapper, router, ARQ jobs |
| 4: Frontend | 13-15 | Credential entry modal, sync status UI, Fintoc removal |
| 5: Integration | 16 | End-to-end verified deployment |
