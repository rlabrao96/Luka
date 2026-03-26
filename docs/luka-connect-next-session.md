# Luka Connect — Next Session: Account Detection + Balances + Transaction Enrichment

> Prompt document for continuing work on Luka Connect integration in a separate terminal.
> Generated: 2026-03-26

---

## Current State (Working in Production)

Luka Connect is **fully operational**:
- `luka-connect` repo deployed on Railway (separate project)
- Banco de Chile: login + scrape working (301 movements, ~4 min)
- Backend webhook receives callback, processes movements, creates transactions
- Frontend: bank selector modal (onboarding + settings), sync status with polling
- 291 transactions successfully imported on first real run

**What's NOT working yet:**
- Transactions have no bank account linked (all `bank_account_id = NULL`)
- Balances not shown (scraper provides them but backend ignores them)
- No auto-creation of bank accounts from scraped data
- Transaction list doesn't show which bank/account each transaction belongs to
- Credit card cupos not stored anywhere

---

## What Luka Connect Already Returns

The scraper callback (`POST /bank-connect/webhooks/luka-connect`) sends:

### `movements[]` — each movement has:
```json
{
  "date": "18-03-2026",
  "time": "13:36",
  "description": "Abono Api En Linea:775009764",
  "amount": 23654,
  "balance": 154277,
  "source": "account",           // or "credit_card_unbilled" or "credit_card_billed"
  "currency": "CLP",             // or "USD"
  "accountNumber": "****7502",   // masked
  "accountName": "Cuenta Corriente Moneda Local"  // human-readable
}
```

### `balances{}` — all account balances:
```json
{
  "Cuenta Corriente Moneda Local": 154277,
  "Cuenta Corriente USD": 1234,
  "Linea de Credito": 5000000
}
```

### `creditCards[]` — credit card cupos:
```json
[
  {
    "label": "Visa ****1234",
    "national": { "used": 150000, "available": 850000, "total": 1000000 },
    "international": { "used": 50, "available": 450, "total": 500, "currency": "USD" },
    "billingPeriod": "Marzo 2026",
    "nextBillingDate": "19 de abril"
  }
]
```

---

## What Needs to Be Built

### 1. Auto-Create Bank Accounts from Scrape Data

When the webhook receives movements, extract unique accounts and auto-create `bank_accounts` rows:

**From movements:** group by `accountNumber + accountName + currency + source` → create:
- Cuenta Corriente CLP (account_kind: "checking_account", currency: "CLP")
- Cuenta Corriente USD (account_kind: "checking_account", currency: "USD")
- Línea de Crédito (account_kind: "line_of_credit", currency: "CLP")
- TC Visa Nacional (account_kind: "credit_card", currency: "CLP")
- TC Visa Internacional (account_kind: "credit_card", currency: "USD")
- TC Mastercard Nacional (account_kind: "credit_card", currency: "CLP")
- TC Mastercard Internacional (account_kind: "credit_card", currency: "USD")

Each `bank_account` should have:
- `bank_name`: "Banco de Chile"
- `account_number`: from movement's `accountNumber`
- `account_kind`: derived from `source` + `accountName`
- `currency`: from movement
- `account_type`: "personal" (default, user can change later)

**Dedup:** Don't create duplicates on subsequent syncs — match by `user_id + account_number + currency`.

### 2. Link Transactions to Bank Accounts

After auto-creating accounts, set `bank_account_id` on each transaction. The current webhook handler already has a `ba_map` lookup — it just needs the accounts to exist first.

### 3. Store Balances

Two options:
- **A)** Add `balance_current` back to `bank_accounts` table (we dropped it with Fintoc). Update on each sync.
- **B)** Create a separate `account_balances` table with history.

Recommendation: **A** for now. Re-add `balance_current` (and maybe `balance_available` for credit cards) to `bank_accounts`. Update from `balances{}` and `creditCards[]` in the webhook handler.

### 4. Store Credit Card Cupos

The credit card data (nacional/internacional used/available/total) could go in:
- JSON column on `bank_accounts` (e.g., `credit_card_info JSONB`)
- Or a dedicated `credit_card_cupos` table

Recommendation: JSON column on `bank_accounts` — simple, one query, updated on each sync.

### 5. Frontend: Show Account Info on Transactions

Currently transactions don't show which bank/account they belong to. Need to:
- Show bank name + account type badge on each transaction row
- Add account filter to the transactions page
- Show balances in the "Saldos Disponibles" cards (currently showing "—")

### 6. Frontend: Settings — Show All Detected Accounts

In the settings bank accounts section, show all auto-created accounts with:
- Bank name + account number
- Account type (Cuenta Corriente, TC, Línea de Crédito)
- Currency
- Current balance
- Last updated

---

## Key Files to Modify

### Backend (Luka repo):
- `backend/modules/bank_connect/router.py` — webhook handler `_process_movements()`: auto-create accounts, link transactions, update balances
- `backend/modules/households/models.py` — may need to re-add `balance_current` to BankAccount or add credit card JSON field
- `backend/alembic/versions/018_*.py` — migration for new/restored columns
- `backend/modules/bank_accounts/router.py` — ensure list endpoint returns balance info

### Frontend (Luka repo):
- `frontend/app/(dashboard)/transactions/page.tsx` — show bank/account on each row, add account filter
- `frontend/app/(dashboard)/components/` — update balance cards to show real data
- `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx` — show auto-created accounts

### Luka Connect (luka-connect repo):
- **No changes needed** — it already returns all the data. The work is on the Luka side.

---

## Implementation Order

1. **Migration** — re-add `balance_current` + add `credit_card_info` JSONB to `bank_accounts`
2. **Auto-create accounts** in webhook handler (group movements by account, dedup)
3. **Link transactions** to accounts (set `bank_account_id`)
4. **Update balances** from callback data
5. **Frontend: balances** — wire up the Saldos Disponibles cards
6. **Frontend: transaction rows** — show bank/account badge
7. **Frontend: settings** — show all detected accounts

---

## Reference: Scraper Output Types

See `luka-connect/src/types.ts` for the full TypeScript types:
- `BankMovement` — individual movement
- `CreditCardBalance` — credit card cupos
- `ScrapeResult` — top-level result with movements, balances, creditCards

## Reference: Test Data

See `test-scraper/last_result.json` for a real 301-movement scrape result from Banco de Chile. This shows the exact format of all fields.

---

## Quick Start

```bash
# In the Luka repo
cd "/Users/rlabrao/Documents/Proyectos AI/Finanzas Personales"

# Check current state
git log --oneline -5

# Run backend locally
cd backend && uvicorn main:app --reload --port 8000

# Run frontend locally
cd frontend && npm run dev

# Check production logs
# Luka backend: Railway dashboard → Luka project → backend service → Deploy Logs
# Luka Connect: Railway dashboard → Luka-connect project → Deploy Logs
```
