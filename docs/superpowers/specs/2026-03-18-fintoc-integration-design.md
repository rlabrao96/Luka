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
2. **Frontend — Account Selection UI** shown after widget completes
3. **Backend — `POST /bank-accounts/fintoc/connect`** endpoint
4. **Backend — `import_fintoc_history` ARQ job** (runs once per account on connection)
5. **Backend — `GET /bank-accounts/import-status`** lightweight polling endpoint
6. **DB — Migration 004** adds `'partner'` as valid `account_type`

### What Stays Unchanged

- Nightly `run_fintoc_sync` cron (ongoing 7-day reconciliation window)
- `FintocClient` and `reconcile_transactions()` (used by cron, untouched)
- All other backend modules

---

## Database Change

**Migration 004:** Extend `bank_accounts.account_type` to accept `'partner'`.

Current: `personal | joint`
New: `personal | partner | joint`

`partner` = additional credit card issued to the user's partner. Transactions on this account are auto-split as `split_type='partner'`.

---

## Data Flow

### Connecting a Bank (Onboarding or Settings)

```
User clicks "Connect Bank"
  → Fintoc JS widget opens (modal)
  → User authenticates with their bank
  → Fintoc returns: link_token + list of accounts
       (each: fintoc_account_id, name, type, last 4 digits)
  → UI renders Account Selection:
       per account: checkbox + personal/partner/joint selector
  → User confirms selection
  → POST /bank-accounts/fintoc/connect
       { link_token, accounts: [{ fintoc_account_id, label }] }
  → Backend:
       - Creates BankAccount row per selected account
           (fintoc_link_id, fintoc_account_id, account_type=label)
       - Enqueues import_fintoc_history job per account
  → Frontend shows loading banner → redirects (onboarding) or stays (settings)
```

### Historical Import Job (`import_fintoc_history`)

```
Input: bank_account_id

1. Load BankAccount (fintoc_link_id, fintoc_account_id, account_type, user_id, household_id)
2. FintocClient.fetch_transactions(account_id, since=today-90d, until=today)
3. For each FintocTransaction:
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
4. Log result: { imported: N, skipped: N }
5. On error: log to failed_jobs, keep partial progress (idempotency handles retry)
```

### Import Status Endpoint

```
GET /bank-accounts/import-status?household_id={id}

Returns:
{
  "importing": bool,       // true if any import job is still pending/running
  "accounts_importing": N  // count of accounts still being imported
}
```

Frontend polls this every 5 seconds while `importing=true`, then removes the banner.

---

## API Endpoints

### New Endpoints

```
POST /bank-accounts/fintoc/connect
  Body: { link_token: str, accounts: [{ fintoc_account_id: str, label: "personal"|"partner"|"joint" }] }
  Auth: required
  Returns: { created: N, accounts: [BankAccount] }
  Errors:
    409 if any fintoc_account_id already exists → "Account already connected"

GET /bank-accounts/import-status
  Query: household_id
  Auth: required
  Returns: { importing: bool, accounts_importing: int }
```

### Existing Endpoint — Modified

```
GET /bank-accounts/  (currently implicit via household summary)
```

The `/households/{id}/summary` response already returns bank accounts. No new list endpoint needed — the settings page uses this.

---

## Frontend Components

### `/onboarding/connect-bank/page.tsx` (rewrite)

**Before:** Manual form (bank_name dropdown + account_type radio)
**After:**
- "Connect Bank" button → calls Fintoc widget
- After widget success → renders `<FintocAccountPicker accounts={...} />`
- `<FintocAccountPicker>`: list of accounts, each with checkbox + personal/partner/joint select
- "Confirm" button → POST to `/bank-accounts/fintoc/connect`
- On success → show "Importing history..." banner → navigate to next onboarding step

### `/settings/page.tsx` (extend)

Add "Connected Accounts" section:
- List of `BankAccount` rows: bank name, account type badge, last 4 digits, label badge
- "Add Account" button → same Fintoc widget + picker flow as onboarding
- On success → refetch household summary

### New component: `<FintocAccountPicker />`

Shared between onboarding and settings. Props:
```ts
{
  accounts: FintocAccount[]  // returned by widget
  onConfirm: (selected: SelectedAccount[]) => void
  loading: boolean
}
```

### Import Status Banner

Small banner shown at top of dashboard when `importing=true`:
> "Importing transaction history — this may take a moment."

Polls `GET /bank-accounts/import-status` every 5s. Disappears automatically when done.
Lives in the dashboard layout (`(dashboard)/layout.tsx`).

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
| Duplicate fintoc_account_id | Backend returns 409. Frontend shows "Account already connected." |
| Import job fails mid-way | Log to failed_jobs. Partial progress kept. Safe to retry (idempotent). |
| Fintoc API rate limit during import | Job stops, logs error. Retry picks up from where it left off. |
| Import status poll fails | Frontend silently retries. Banner stays visible. |

---

## ARQ Job Registration

```python
# jobs/tasks.py — new job
async def import_fintoc_history(ctx: dict, bank_account_id: str) -> None:
    ...

# jobs/queue.py — new enqueue helper
async def enqueue_fintoc_history_import(bank_account_id: str) -> None:
    ...
```

Job is enqueued on-demand (not cron). No timeout override needed — 90 days of transactions is typically < 500 rows per account.

---

## Import Status Implementation

**Simple approach:** Query `failed_jobs` + a new `import_jobs` lightweight tracking.

Actually, simplest: add `import_status` field to `BankAccount`:

```
bank_accounts.import_status: 'pending' | 'importing' | 'done' | 'failed'
```

Set to `'pending'` on account creation, `'importing'` when job starts, `'done'` on success, `'failed'` on error.

`GET /bank-accounts/import-status` → count accounts where `import_status IN ('pending', 'importing')`.

This requires **Migration 005** adding `import_status` column (default `'done'` for existing accounts, `'pending'` for new Fintoc-connected ones).

---

## Fintoc JS SDK Integration

Fintoc provides a script tag SDK. Load it in the frontend:

```html
<script src="https://js.fintoc.com/v1/"></script>
```

Usage pattern:
```ts
const widget = Fintoc.create({
  publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY,
  product: 'movements',
  country: 'cl',
  onSuccess: (linkToken) => { /* fetch accounts, show picker */ },
  onExit: () => { /* user cancelled */ },
  onError: (err) => { /* show error */ },
})
widget.open()
```

New env var required: `NEXT_PUBLIC_FINTOC_PUBLIC_KEY` (public key, safe for frontend).

---

## Migrations Summary

| Migration | Change |
|-----------|--------|
| 004 | Extend `bank_accounts.account_type` to allow `'partner'` |
| 005 | Add `bank_accounts.import_status VARCHAR DEFAULT 'done'` |

---

## Files to Create / Modify

### Backend
| File | Action |
|------|--------|
| `backend/alembic/versions/004_partner_account_type.py` | New migration |
| `backend/alembic/versions/005_bank_account_import_status.py` | New migration |
| `backend/modules/households/models.py` | Add `import_status` field |
| `backend/modules/households/router.py` | Add `POST /bank-accounts/fintoc/connect`, `GET /bank-accounts/import-status` |
| `backend/jobs/tasks.py` | Add `import_fintoc_history` job |
| `backend/jobs/queue.py` | Add `enqueue_fintoc_history_import` helper |

### Frontend
| File | Action |
|------|--------|
| `frontend/app/(auth)/onboarding/connect-bank/page.tsx` | Rewrite |
| `frontend/app/(dashboard)/settings/page.tsx` | Add Connected Accounts section |
| `frontend/app/(dashboard)/layout.tsx` | Add import status banner |
| `frontend/app/(dashboard)/components/ImportStatusBanner.tsx` | New component |
| `frontend/app/lib/hooks/useBankAccounts.ts` | New hook (import status polling) |
| `frontend/app/lib/api.ts` | Add `connectFintocAccounts()`, `getImportStatus()` |

---

## Success Criteria

- User can connect a Chilean bank account via Fintoc widget in onboarding
- User can add additional accounts from Settings
- 90 days of transactions appear in the dashboard within minutes of connecting
- Each transaction has the correct split (personal/partner/shared) based on account label
- Duplicate account connections are rejected gracefully
- Import failure is logged and safely retryable
