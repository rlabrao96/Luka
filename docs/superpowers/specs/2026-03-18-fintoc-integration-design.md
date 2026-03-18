# Fintoc Integration — Full Design Spec
**Date:** 2026-03-18
**Status:** Approved

---

## Overview

Replace the manual bank account entry flow with a full Fintoc Link integration. Users connect their Chilean bank accounts and credit cards via the Fintoc JS widget. On connection, 90 days of historical transactions are imported automatically, giving the dashboard spending history from day one. Ongoing reconciliation (existing nightly cron) continues unchanged.

---

## Goals

- Fintoc is the **only** way to connect a bank account (no manual entry)
- Support multiple banks and credit cards per user
- Import 3 months of transaction history automatically on account connection
- Support personal, partner (additional card), and joint account labeling
- Allow adding accounts from both onboarding and settings

---

## Non-Goals (deferred)

- LLM categorization of historical transactions (post-MVP)
- Disconnect/remove a connected account (post-MVP)
- Admin retry UI for failed import jobs (v1: failed_jobs table only)
- Fintoc webhook for link creation events

---

## Architecture

### What Gets Built

1. **Frontend — Fintoc Link Widget** in `/onboarding/connect-bank` (replaces manual form) + new "Connected Accounts" section in `/settings`
2. **Frontend — `<FintocAccountPicker />`** shared component shown after widget completes (account selection + labeling)
3. **Frontend — `<ImportStatusBanner />`** dashboard banner with polling hook
4. **Backend — new `bank_accounts` router** (`backend/modules/bank_accounts/router.py`) registered at `/bank-accounts` prefix in `main.py`
5. **Backend — `POST /bank-accounts/fintoc/connect`** endpoint
6. **Backend — `GET /bank-accounts/import-status`** polling endpoint
7. **Backend — `import_fintoc_history` ARQ job** (runs once per account on connection)
8. **DB — Migration 004** adds `'partner'` as valid `account_type`
9. **DB — Migration 005** adds `import_status` column to `bank_accounts`

### What Stays Unchanged

- Nightly `run_fintoc_sync` cron (ongoing 7-day reconciliation window)
- `FintocClient` and `reconcile_transactions()` (used by cron, untouched)
- All other backend modules

---

## Database Changes

### Migration 004 — Partner account type

Extend `bank_accounts.account_type` to accept `'partner'`.

```
Current: 'personal' | 'joint'
New:     'personal' | 'partner' | 'joint'
```

`partner` = additional credit card issued to the user's partner. Transactions on this account are auto-split as `split_type='partner'`.

### Migration 005 — Import status tracking

Add `import_status` column to `bank_accounts`:

```sql
ALTER TABLE bank_accounts
  ADD COLUMN import_status VARCHAR DEFAULT 'done';
```

Default `'done'` for all existing accounts. New Fintoc-connected accounts start as `'pending'`.

Valid values: `'pending' | 'importing' | 'done' | 'failed'`

**Model file:** `backend/modules/households/models.py` — the `BankAccount` SQLAlchemy model lives here alongside all other household-related models.

---

## Fintoc Link Token Clarification

The Fintoc JS widget's `onSuccess` callback returns a `link_token`. This token IS the persistent identifier stored as `fintoc_link_id` in the DB — it is not a short-lived exchange token. Fintoc uses this same `link_token` for all subsequent API calls (fetching accounts, transactions, etc.). No exchange step is required. The frontend sends it directly to the backend in the POST body, and the backend stores it as-is in `bank_accounts.fintoc_link_id`.

---

## Data Flow

### Connecting a Bank (Onboarding or Settings)

```
User clicks "Connect Bank"
  → Fintoc JS widget opens (modal)
  → User authenticates with their bank
  → Widget onSuccess callback fires with: link_token (persistent) + list of accounts
       (each account: fintoc_account_id, name, type, last 4 digits)
  → UI renders <FintocAccountPicker>:
       per account: checkbox + personal/partner/joint selector
  → User confirms selection
  → POST /bank-accounts/fintoc/connect
       { link_token, accounts: [{ fintoc_account_id, label }] }
  → Backend:
       - Validates caller is member of household (403 if not)
       - Creates BankAccount row per selected account with import_status='pending'
           (fintoc_link_id=link_token, fintoc_account_id, account_type=label)
       - Enqueues import_fintoc_history job per account
  → Frontend shows loading banner → redirects (onboarding) or stays (settings)
```

### Historical Import Job (`import_fintoc_history`)

```
Input: bank_account_id

1. Load BankAccount (fintoc_link_id, fintoc_account_id, account_type, user_id, household_id)
2. Set bank_account.import_status = 'importing'
3. FintocClient.fetch_transactions(account_id, since=today-90d, until=today)
4. For each FintocTransaction:
   a. Skip if Transaction with fintoc_id already exists (idempotent)
   b. INSERT Transaction:
        user_id, household_id, bank_account_id
        amount, transaction_date
        source = 'fintoc'
        status = 'settled'
        category = NULL
        fintoc_id = fintoc_transaction.id
        raw_email_text = NULL
   c. INSERT TransactionSplit:
        split_type = personal→'personal' | partner→'partner' | joint→'shared'
        decided_by_user_id = user_id
        decided_at = now()
5. Set bank_account.import_status = 'done'
6. Log result: { imported: N, skipped: N }
7. On error: set import_status = 'failed', log to failed_jobs, keep partial progress
```

### Import Status Endpoint

```
GET /bank-accounts/import-status?household_id={id}

Auth: caller must be a member of household_id → 403 if not

Returns:
{
  "importing": bool   // true if any account has import_status IN ('pending', 'importing')
}
```

Frontend polls every 5 seconds while `importing=true`, removes banner when `importing=false`.

---

## API Endpoints

### New Router: `backend/modules/bank_accounts/router.py`

Registered in `main.py` with prefix `/bank-accounts`. This is a new module — not added to the existing `households/router.py` — to keep routing clean.

```
POST /bank-accounts/fintoc/connect
  Body: {
    link_token: str,
    household_id: str,
    accounts: [{ fintoc_account_id: str, label: "personal"|"partner"|"joint" }]
  }
  Auth: required + caller must be member of household_id (403 if not)
  Returns: { created: int, accounts: [BankAccount] }
  Errors:
    403 if caller not in household
    409 if any fintoc_account_id already exists → "Account already connected"

GET /bank-accounts/import-status
  Query: household_id (required)
  Auth: required + caller must be member of household_id (403 if not)
  Returns: { importing: bool }
```

### Existing Endpoint — Unchanged

The `/households/{id}/summary` response already returns bank accounts. The settings page uses this to list connected accounts. No new list endpoint needed.

---

## Frontend Components

### `/onboarding/connect-bank/page.tsx` (rewrite)

**Before:** Manual form (bank_name dropdown + account_type radio)
**After:**
- "Connect Bank" button → initializes Fintoc widget
- After widget `onSuccess` → renders `<FintocAccountPicker>`
- On confirm → `POST /bank-accounts/fintoc/connect`
- On success → redirects to next onboarding step (import runs in background)

### `/settings/page.tsx` (extend)

Add "Connected Accounts" section:
- List of `BankAccount` rows from household summary: bank name, last 4 digits, label badge
- "Add Account" button → same Fintoc widget + `<FintocAccountPicker>` flow
- On success → refetch household summary

### New: `frontend/app/(dashboard)/components/FintocAccountPicker.tsx`

Shared between onboarding and settings.

```ts
interface Props {
  accounts: FintocAccount[]   // returned by widget onSuccess
  onConfirm: (selected: SelectedAccount[]) => void
  loading: boolean
}

interface FintocAccount {
  fintoc_account_id: string
  name: string
  type: string          // e.g. "checking_account", "credit_card"
  last_four: string
}

interface SelectedAccount {
  fintoc_account_id: string
  label: "personal" | "partner" | "joint"
}
```

Renders a list of checkboxes with label selectors. "Confirm" disabled if no accounts selected.

### New: `frontend/app/(dashboard)/components/ImportStatusBanner.tsx`

Small top banner: *"Importing transaction history — this may take a moment."*
Uses `useImportStatus` hook. Renders only when `importing=true`.

### New: `frontend/app/lib/hooks/useImportStatus.ts`

Polls `GET /bank-accounts/import-status` every 5s when `householdId` is available.
Returns `{ importing: boolean }`. Stops polling when `importing=false`.

### Modified: `frontend/app/(dashboard)/layout.tsx`

Add `<ImportStatusBanner />` above the main content area.

### Modified: `frontend/app/lib/api.ts`

Add:
- `connectFintocAccounts(payload)` → `POST /bank-accounts/fintoc/connect`
- `getImportStatus(householdId)` → `GET /bank-accounts/import-status`

---

## Split Type Mapping

| Account Label | `account_type` in DB | `split_type` in TransactionSplit |
|---------------|---------------------|----------------------------------|
| personal      | personal            | personal                        |
| partner       | partner             | partner                         |
| joint         | joint               | shared                          |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| User cancels Fintoc widget | No backend state created. Show "Connection cancelled." |
| Widget SDK error | Show "Connection failed — try again." |
| Unauthorized household_id | Backend returns 403. |
| Duplicate fintoc_account_id | Backend returns 409. Frontend shows "Account already connected." |
| Import job fails mid-way | Set import_status='failed'. Log to failed_jobs. Partial progress kept. Safe to retry (idempotent). |
| Fintoc API rate limit during import | Job stops, logs to failed_jobs. Retry picks up from where it left off. |
| Import status poll fails | Frontend silently retries. Banner stays visible. |

---

## ARQ Job Registration

```python
# backend/jobs/tasks.py — new job
async def import_fintoc_history(ctx: dict, bank_account_id: str) -> None:
    ...

# backend/jobs/queue.py — new enqueue helper
async def enqueue_fintoc_history_import(bank_account_id: str) -> None:
    ...
```

Job is enqueued on-demand (not cron). 90 days of transactions is typically < 500 rows per account — no timeout override needed.

---

## Fintoc JS SDK Integration

Fintoc provides a script tag SDK:

```html
<script src="https://js.fintoc.com/v1/"></script>
```

Usage in React (via useEffect + script injection or Next.js Script component):

```ts
const widget = Fintoc.create({
  publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY,
  product: 'movements',
  country: 'cl',
  onSuccess: (linkToken: string) => {
    // linkToken is the persistent fintoc_link_id — store and use directly
    // Fetch available accounts from Fintoc API or receive them from the callback
    // Show <FintocAccountPicker> with the account list
  },
  onExit: () => { /* user cancelled */ },
  onError: (err: Error) => { /* show error message */ },
})
widget.open()
```

New env var required: `NEXT_PUBLIC_FINTOC_PUBLIC_KEY` (public key, safe for browser).

---

## Migrations Summary

| Migration | Change |
|-----------|--------|
| 004 | Add `'partner'` as valid `bank_accounts.account_type` |
| 005 | Add `bank_accounts.import_status VARCHAR DEFAULT 'done'` |

---

## Files to Create / Modify

### Backend

| File | Action |
|------|--------|
| `backend/alembic/versions/004_partner_account_type.py` | New migration |
| `backend/alembic/versions/005_bank_account_import_status.py` | New migration |
| `backend/modules/households/models.py` | Add `import_status` field to `BankAccount` model |
| `backend/modules/bank_accounts/__init__.py` | New module init |
| `backend/modules/bank_accounts/router.py` | New router: `POST /fintoc/connect`, `GET /import-status` |
| `backend/main.py` | Register new bank_accounts router at prefix `/bank-accounts` |
| `backend/jobs/tasks.py` | Add `import_fintoc_history` job |
| `backend/jobs/queue.py` | Add `enqueue_fintoc_history_import` helper |
| `backend/tests/test_fintoc_import.py` | New test file for import job |

### Frontend

| File | Action |
|------|--------|
| `frontend/app/(auth)/onboarding/connect-bank/page.tsx` | Rewrite — replace manual form with Fintoc widget flow |
| `frontend/app/(dashboard)/settings/page.tsx` | Add "Connected Accounts" section with "Add Account" button |
| `frontend/app/(dashboard)/layout.tsx` | Add `<ImportStatusBanner />` |
| `frontend/app/(dashboard)/components/FintocAccountPicker.tsx` | New shared component |
| `frontend/app/(dashboard)/components/ImportStatusBanner.tsx` | New component |
| `frontend/app/lib/hooks/useImportStatus.ts` | New polling hook |
| `frontend/app/lib/api.ts` | Add `connectFintocAccounts()`, `getImportStatus()` |

### Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `NEXT_PUBLIC_FINTOC_PUBLIC_KEY` | Vercel | Fintoc public key for the JS widget |
| `FINTOC_API_KEY` | Railway | Already exists — used by backend FintocClient |

---

## Success Criteria

- User can connect a Chilean bank account via Fintoc widget during onboarding
- User can add additional accounts from Settings after onboarding
- 90 days of transactions appear in the dashboard within minutes of connecting
- Each transaction has the correct split (personal/partner/shared) based on account label
- Duplicate account connections are rejected with a clear error
- Import failure is logged to `failed_jobs` and safely retryable
- Dashboard shows import status banner while import is in progress
- Unauthorized access to another household's import status returns 403
