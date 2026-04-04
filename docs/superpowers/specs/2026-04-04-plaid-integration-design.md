# Plaid Integration for US Users

**Date:** 2026-04-04
**Status:** Approved
**Author:** Rafael + Claude

## Goal

Add Plaid as a bank connection provider for US-based users. When a user taps "+ Conectar banco", they choose between Chile (luka-connect) and USA (Plaid) via a country flag selector. Plaid covers US banks, credit cards, and fintech accounts (Venmo, etc.).

Additionally, introduce a shared transaction reconciliation system that handles deduplication, transfer detection, and fuzzy matching across both providers.

## Non-Goals

- Replacing luka-connect for Chile
- Plaid webhook-driven sync (cost optimization — daily cron only)
- Real-time Plaid transaction updates (email handles real-time, Plaid is daily batch)

## Architecture Decision

**Separate module** (`modules/plaid/`) alongside existing `modules/bank_connect/`. The two providers are fundamentally different (stored credentials + webhook-push vs OAuth token + cursor-pull), so a unified abstraction would be forced and premature for two providers. Shared logic (reconciliation, account creation patterns) lives in a shared utility.

---

## 1. Data Model

### 1.1 New Table: `plaid_items`

Stores one row per Plaid connection (one user login at one US institution).

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Internal ID |
| `user_id` | UUID FK → users | Who connected this |
| `household_id` | UUID FK → households | For account ownership |
| `plaid_item_id` | string, unique | Plaid's Item ID |
| `access_token` | string | Plaid access token (API token, not user credential) |
| `institution_id` | string | Plaid institution ID (e.g., `ins_3`) |
| `institution_name` | string | Display name ("Chase", "Bank of America", "Venmo") |
| `cursor` | text, nullable | Last `/transactions/sync` cursor for incremental updates |
| `last_sync_at` | datetime, nullable | Timestamp of last successful sync |
| `last_sync_status` | string, nullable | `"success"` / `"failed"` |
| `error_code` | string, nullable | Plaid error code (e.g., `"ITEM_LOGIN_REQUIRED"`) when item needs re-auth |
| `created_at` | datetime | Row creation time |

**Error states:** When a sync fails with `ITEM_LOGIN_REQUIRED` (user changed bank password, institution revoked access), `error_code` is set and syncs stop. The frontend shows a "Reconectar" button that opens Plaid Link in **update mode** (passing the existing `access_token`) so the user can re-authenticate without creating a new Item.

### 1.2 Changes to `bank_accounts`

| Column | Type | Default | Description |
|---|---|---|---|
| `provider` | string | `"luka_connect"` | `"luka_connect"` or `"plaid"` |
| `country` | string(2) | `"CL"` | ISO 3166-1 alpha-2: `"CL"` or `"US"` |
| `plaid_item_id` | UUID FK → plaid_items, nullable | `null` | Links Plaid accounts to their Item |
| `plaid_account_id` | string, nullable | `null` | Plaid's account ID for this specific account |

New `account_kind` value: `"other"` — catch-all for exotic Plaid account types (money market, CD, etc.).

### 1.3 Changes to `transactions`

| Column | Type | Default | Description |
|---|---|---|---|
| `source_type` | string | — | New value `"plaid"` alongside existing `"email"` and `"connect"` |
| `transfer_pair_id` | UUID, nullable | `null` | Links two matched transfer transactions together |
| `plaid_transaction_id` | string, unique (partial), nullable | `null` | Plaid's unique transaction ID for dedup and updates. Partial unique index: `WHERE plaid_transaction_id IS NOT NULL` |

**Transfer detection reuses existing columns:** The `transaction_type` column already supports `"transfer"` (alongside `"expense"` and `"income"`), and `transfer_to_account_id` already exists as an FK to `bank_accounts`. Transfer detection (Section 4.3) sets `transaction_type = "transfer"` on both sides and uses `transfer_pair_id` to link the pair. Budget/dashboard queries already filter on `transaction_type = 'expense'`, so transfers are automatically excluded.

### 1.4 Account Type Mapping

| Plaid type / subtype | `account_kind` |
|---|---|
| `depository` / `checking` | `checking_account` |
| `depository` / `savings` | `savings_account` |
| `credit` / `credit card` | `credit_card` |
| Everything else | `other` |

---

## 2. Backend Module: `modules/plaid/`

### 2.1 File Structure

```
backend/modules/plaid/
  __init__.py
  router.py      — API endpoints
  service.py     — Plaid API client wrapper
  models.py      — PlaidItem SQLAlchemy model
  sync.py        — Transaction sync and account creation logic
  mapper.py      — Plaid transaction → Luka transaction mapping
```

### 2.2 API Endpoints (`router.py`)

#### `POST /plaid/create-link-token`

Creates a Plaid Link token for the frontend widget.

- Auth: requires authenticated user
- Calls Plaid `/link/token/create` with:
  - `country_codes: ["US"]`
  - `products: ["transactions"]`
  - `language: "en"`
  - `user.client_user_id: str(user_id)`
- Returns: `{ link_token: string }`

#### `POST /plaid/exchange-token`

Exchanges the public token from Plaid Link for an access token.

- Auth: requires authenticated user
- Request body: `{ public_token: string, institution_id: string, institution_name: string }`
- Calls Plaid `/item/public_token/exchange`
- Creates `PlaidItem` row with access token, institution info
- Enqueues initial 90-day sync job
- Returns: `{ plaid_item_id: UUID }`

#### `DELETE /plaid/disconnect?plaid_item_id={id}`

Disconnects a Plaid Item and stops billing.

- Auth: requires authenticated user, must own the item
- Calls Plaid `/item/remove` (stops subscription billing)
- Soft-delete: sets `bank_accounts.is_active = false` for associated accounts (preserves transaction history, budget data, and splits)
- Hard-deletes: `PlaidItem` row only (no further syncs needed)
- Returns: `{ success: true }`

#### `POST /plaid/sync?plaid_item_id={id}`

Manual sync trigger (testing only, will be removed later).

- Auth: requires authenticated user, must own the item
- Enqueues `run_plaid_sync` job
- Returns: `{ status: "syncing" }`

### 2.3 Plaid API Client (`service.py`)

Thin wrapper around `plaid-python` SDK:

- `create_link_token(user_id: UUID) → str` — returns link_token
- `exchange_public_token(public_token: str) → tuple[str, str]` — returns (access_token, item_id)
- `sync_transactions(access_token: str, cursor: str | None, count: int = 500) → TransactionsSyncResponse` — calls `/transactions/sync`
- `remove_item(access_token: str) → None` — calls `/item/remove`

Configuration from env vars: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`.

### 2.4 Sync Logic (`sync.py`)

#### `run_plaid_sync(plaid_item_id: UUID, days_requested: int = 3)`

1. Load `PlaidItem` from DB
2. Call `/transactions/sync` with stored cursor, paginate through all results (500 per page, loop on `has_more`)
3. **Accounts**: Call `ensure_plaid_accounts()` — create/update `bank_accounts` rows from Plaid's `accounts` array, update balances (`balance_current`, `balance_limit`, `last_synced_at`)
4. **Added transactions**: For each, run through reconciliation (see Section 4), then create transaction with `source_type="plaid"`
5. **Modified transactions**: Update existing transaction fields (handles tip adjustments, pending → settled)
6. **Removed transactions**: Hard-delete the transaction
7. Update `PlaidItem.cursor`, `last_sync_at`, `last_sync_status`
8. Trigger `process_merchant_review` for new transactions

#### `ensure_plaid_accounts(plaid_item: PlaidItem, plaid_accounts: list)`

For each Plaid account in the response:
- Match by `plaid_account_id` to existing `bank_accounts` row
- If no match: create new `bank_accounts` row with provider="plaid", country="US", mapped `account_kind`
- Update balances on all matched/created accounts

#### Initial sync

First sync after connection uses `days_requested=90` in the `/transactions/sync` options. Subsequent daily syncs use the stored cursor (which inherently fetches only new/modified/removed since last sync — the `days_requested` param is only for first sync).

### 2.5 Transaction Mapper (`mapper.py`)

Maps Plaid transaction fields to Luka transaction fields:

| Plaid field | Luka field |
|---|---|
| `transaction_id` | `plaid_transaction_id` |
| `amount` | `amount` (**sign flip required**: Plaid positive = outflow, but Luka uses negative = expense. Multiply by -1.) |
| `date` | `transaction_date` |
| `merchant_name` or `name` | `raw_name` (fed into merchant training pipeline) |
| `iso_currency_code` | inherited from account's `currency` |
| `account_id` | mapped to `bank_account_id` via `plaid_account_id` |
| `pending` | If `true`, set `status = "pending"`; if `false`, set `status = "confirmed"` |
| (derived from amount sign) | `transaction_type`: `"expense"` if Plaid amount > 0 (outflow), `"income"` if < 0 (inflow) |

Plaid's built-in `personal_finance_category` is used **only** for transfer detection (Section 4.3). For merchant categorization, Luka uses its own LLM-based system.

### 2.6 Worker Additions

In `worker.py`:

- New function: `run_plaid_sync(ctx, plaid_item_id: str, days_requested: int = 3)`
- New cron job: `schedule_plaid_syncs` — runs daily, queries all `PlaidItem` rows, enqueues `run_plaid_sync` for each
- New function: `run_transaction_reconciliation(ctx)` — daily post-processing (see Section 4)

---

## 3. Frontend

### 3.1 Country Selector Modal

New component: `CountrySelectorModal.tsx`

- Triggered by "+ Conectar banco" button (replaces direct navigation to luka-connect)
- Renders a small centered modal with two flag icons (no text labels)
- 🇨🇱 tap → navigates to existing luka-connect onboarding flow (`/onboarding/connect-bank`)
- 🇺🇸 tap → calls `POST /plaid/create-link-token`, then opens Plaid Link widget

### 3.2 Plaid Link Widget

- Install `react-plaid-link` package
- New hook: `usePlaidLink.ts`
  - Receives `link_token` from backend
  - Opens Plaid Link overlay
  - `onSuccess(public_token, metadata)`: sends public_token + institution info to `POST /plaid/exchange-token`, then refreshes bank accounts list
  - `onExit`: closes gracefully, no action needed

### 3.3 API Client Additions (`api.ts`)

```typescript
createPlaidLinkToken(): Promise<{ link_token: string }>
exchangePlaidToken(publicToken: string, institutionId: string, institutionName: string): Promise<{ plaid_item_id: string }>
disconnectPlaid(plaidItemId: string): Promise<void>
syncPlaid(plaidItemId: string): Promise<void>
```

### 3.4 Bank Connection Cards (`BankAccountsSection.tsx`)

- Add small flag icon (🇨🇱 / 🇺🇸) on each bank connection card, derived from `country` field
- Group detected accounts by bank, showing flag + institution name
- "Desconectar" on Plaid banks → calls `disconnectPlaid(plaidItemId)`
- "Sincronizar ahora" on Plaid banks → calls `syncPlaid(plaidItemId)` (temporary, testing only)
- Account kind display: map `"other"` to a generic label like "Otra cuenta"

### 3.5 Plaid Error State

When a Plaid Item has `error_code = "ITEM_LOGIN_REQUIRED"`, the bank card shows a warning state with a "Reconectar" button. Tapping it opens Plaid Link in update mode to re-authenticate.

### 3.6 No Changes Required

Transaction list, dashboard, budgets, merchant training, WhatsApp alerts — all work with transactions regardless of `source_type`. Transfer detection uses the existing `transaction_type = "transfer"` which budget queries already filter out.

---

## 4. Shared Transaction Reconciliation

New shared utility used by both luka-connect and Plaid sync. Runs as a daily post-processing job after all syncs complete.

### 4.1 Email Dedup-and-Enrich

When a bank sync transaction (Plaid or luka-connect) matches an email transaction:

1. **Copy from email tx**: `merchant_id` (category), `account_type` (personal/joint), `transaction_splits` (re-link FK to new tx), custom merchant name (if user edited the merchant's `display_name`)
2. **Apply to bank tx**: create bank transaction with enriched data
3. **Delete email tx**: hard-delete the email transaction — bank tx is now source of truth

**Migration note:** The existing luka-connect dedup logic (in `bank_connect/router.py`) currently enriches the email tx in-place rather than replacing it. This should be updated to use the same delete-and-replace pattern for consistency. Both providers go through this shared reconciliation utility.

### 4.2 Matching Priority

#### 1. Exact single match
- Same merchant name, ±2 days, exact same amount
- Highest confidence

#### 2. Fuzzy single match
- Same merchant name, ±3 days, amount within 30%
- Handles tips (restaurants) and ride adjustments (Uber)

#### 3. Sum match
- Same merchant name, ±3 days
- Sum of N email transactions matches bank transaction amount (within 5%)
- Handles consolidated charges (e.g., Uber ride $23 + toll $2 → bank settles $25)

### 4.3 Transfer Detection

Identifies inter-account transfers and credit card payments to exclude from expense/income calculations.

**Detection methods (applied in order):**

1. **Plaid category tags**: Trust `TRANSFER_IN`, `TRANSFER_OUT`, `LOAN_PAYMENTS` from Plaid's `personal_finance_category`
2. **Cross-account amount matching**: Same absolute amount, ±2 days, opposite signs, across two different accounts in the same household

**When transfer detected:**
- Both transactions get `transaction_type = "transfer"` (reuses existing column)
- Both get the same `transfer_pair_id` (new UUID linking the pair)
- Automatically excluded from budget calculations (existing queries already filter on `transaction_type = 'expense'`)
- Still visible in transaction list (visually distinct)

**Covers:**
- Checking → savings at same bank
- BofA checking → Amex CC payment (cross-institution)
- Venmo → checking transfers
- Any CC payment from any checking account
- Works for both US (Plaid) and Chile (luka-connect) accounts

### 4.4 Scheduling

- Runs as a daily ARQ cron job at a fixed time (e.g., 6am UTC), after sync crons have run (Plaid syncs scheduled before this time)
- Processes all transactions from the last 5 days (covers ±2/3 day matching windows)
- Idempotent — safe to re-run, won't re-match already reconciled transactions

---

## 5. Configuration

### 5.1 Environment Variables

Add to `backend/.env`:

```
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET=your_sandbox_secret
PLAID_ENV=sandbox
```

### 5.2 Dependencies

- **Backend**: `plaid-python` (official Plaid Python SDK)
- **Frontend**: `react-plaid-link` (official Plaid React component)

### 5.3 Plaid Dashboard Setup

1. Create Plaid developer account
2. Enable Transactions product
3. Start in Sandbox environment (free, unlimited testing)
4. Limited Production: 200 free API calls with live data
5. Production: subscription billing per connected Item (~$0.30-0.50/month per Item)

---

## 6. Migration Plan

Single Alembic migration:

1. Create `plaid_items` table
2. Add `provider`, `country`, `plaid_item_id`, `plaid_account_id` to `bank_accounts` (with defaults for existing rows)
3. Add `transfer_pair_id`, `plaid_transaction_id` to `transactions`
4. Create partial unique index on `transactions(plaid_transaction_id) WHERE plaid_transaction_id IS NOT NULL`

Existing data is unaffected — all current rows get `provider="luka_connect"`, `country="CL"`.

---

## 7. Cost Estimate

| Scenario | Monthly Cost |
|---|---|
| Sandbox testing | $0 |
| First 200 live API calls | $0 (Limited Production) |
| 5 US users, 1 bank each | ~$1.50-2.50 |
| 10 US users, 2 banks each | ~$6-10 |
| Manual `/transactions/refresh` calls | ~$0.10 each (avoided by using daily cron only) |
