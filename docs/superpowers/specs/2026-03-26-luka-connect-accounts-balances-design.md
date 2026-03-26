# Luka Connect — Account Detection, Balances & Transaction Enrichment

> Design spec for auto-creating bank accounts from scrape data, storing balances,
> linking transactions, and surfacing financial position on the frontend.
>
> Created: 2026-03-26

---

## Context

Luka Connect scrapes Banco de Chile and sends movements, balances, and credit card
cupos to our webhook. Currently, the webhook creates transactions but:

- No bank accounts are auto-created (`bank_account_id = NULL` on all transactions)
- Balances are received but discarded (columns removed in migration 017)
- Credit card cupos are ignored
- Frontend balance cards show fallback values

This spec covers the full end-to-end: DB changes, account auto-creation, balance
storage, transaction linking, and frontend updates.

---

## 1. Database Migration (018)

Add to `bank_accounts` table:

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| `account_name` | `String` | YES | `NULL` | Human-readable name from scraper (dedup key + display label) |
| `balance_current` | `BigInteger` | YES | `NULL` | Current balance or used amount (negative for CC) |
| `balance_limit` | `BigInteger` | YES | `NULL` | Total cupo for CC, total line for línea de crédito. NULL for checking. |
| `last_synced_at` | `DateTime(tz)` | YES | `NULL` | When balance was last updated by sync |

**No other table changes.** No JSONB columns, no new tables.

---

## 2. Auto-Create Bank Accounts (`_ensure_accounts()`)

New function called in the webhook handler **before** `_process_movements()`. Receives
the full callback data (movements, allBalances, creditCards) and the user's credential.

**Important:** The current `ConnectCallback` Pydantic model uses `balances` as the field name,
but the scraper sends `allBalances`. The model must be updated: rename field to `allBalances: dict | None = None`
(or use `Field(alias="allBalances")`). Similarly, `creditCards` must be verified as a matching field name.

**Session strategy:** `_ensure_accounts()` must use `db.flush()` (not `db.commit()`) so that
account rows get IDs for the `ba_map` but everything rolls back atomically if
`_process_movements()` fails later. One final `db.commit()` at the end of the webhook handler.

**Webhook guard:** The current webhook handler only processes when `body.status == "completed" and body.movements`.
This must change to `body.status == "completed"` — `_ensure_accounts()` should run even when there are no
movements (e.g., a short `days_back` window with no activity), so balances still get updated.
`_process_movements()` only runs if `body.movements` is non-empty.

### Step 1 — Accounts from movements

Group movements by `accountName + currency`. For each unique combination, create a
`bank_account` row:

| Scraper accountName | account_kind | currency |
|---------------------|-------------|----------|
| Cuenta Corriente Moneda Local | `checking_account` | CLP |
| Cuenta Corriente M/E | `checking_account` | USD |

Fields set on creation:
- `bank_name`: mapped from bank code (e.g., `"BANCO_CHILE"` → `"Banco de Chile"`)
- `account_name`: verbatim from scraper `accountName`
- `account_number`: from movement's `accountNumber` (e.g., `"****7502"`)
- `account_kind`: derived from `accountName` (checking, savings, etc.)
- `currency`: from movement
- `account_type`: `"personal"` (default)
- `is_active`: `True`
- `user_id`, `household_id`: from credential/membership lookup

### Step 2 — Accounts from creditCards[]

Each `creditCards[]` entry creates up to 2 accounts (national + international):

| Scraper label | Cupo | account_kind | currency |
|--------------|------|-------------|----------|
| Visa Signature ****5032 | national | `credit_card` | CLP |
| Visa Signature ****5032 | international | `credit_card` | USD |
| Mastercard Black ****7623 | national | `credit_card` | CLP |

Only created if the card has balance data for that cupo (skip if no `national`/`international` object in the JSON).

Fields:
- `account_name`: card label + " Nacional" or " Internacional" (e.g., "Visa Signature ****5032 Nacional") — note: scraper uses English keys `national`/`international` but we use Spanish for display names
- `account_number`: extracted from label (e.g., `"****5032"`)
- `account_kind`: `"credit_card"`

### Step 3 — Line of credit from allBalances

If `allBalances` contains `LINEA_CREDITO_CLP`:
- `account_name`: `"Línea de Crédito"`
- `account_kind`: `"line_of_credit"`
- `currency`: `"CLP"`

### Dedup

Before creating any account, query:
```sql
SELECT id FROM bank_accounts
WHERE user_id = :user_id
  AND bank_name = :bank_name
  AND account_name = :account_name
  AND currency = :currency
```

If found → skip creation, use existing ID. Balance is updated in the next step regardless.

### Return value

`_ensure_accounts()` returns a `ba_map: dict[tuple[str, str], UUID]` mapping
`(account_name, currency)` → `bank_account_id`. This replaces the current
`account_number`-based `ba_map`.

---

## 3. Update Balances

Happens inside `_ensure_accounts()`, for every account (new or existing):

**Checking accounts:**
- Map `accountName` to `allBalances` key (e.g., `"Cuenta Corriente Moneda Local"` → `CUENTA_CORRIENTE_CLP`)
- `balance_current` = value from `allBalances`
- `balance_limit` = `NULL`

**Line of credit:**
- `balance_current` = value from `allBalances["LINEA_CREDITO_CLP"]`
- `balance_limit` = same value (full line available = limit)

**Credit cards** (using English keys from scraper: `national.total`, `national.available`, etc.):
- `balance_current` = `-(total - available)` → negative number representing used amount
- `balance_limit` = `total`
- Example: total = 1,000,000, available = 850,000 → `balance_current = -150000`, `balance_limit = 1000000`
- **Stale data:** If a credit card entry has no cupo data in the current sync (e.g., Mastercard
  with no `national`/`international` objects), leave existing balance values unchanged.
  `last_synced_at` is only updated for accounts where fresh data was received.

**All accounts with fresh data:** `last_synced_at = utcnow()`

---

## 4. Link Transactions to Accounts

In `_process_movements()`, when creating or enriching a transaction:

**For account movements** (`source = "account"`):
- Lookup `ba_map[(mov["accountName"], mov["currency"])]`
- Set `bank_account_id` on the transaction

**For credit card movements** (`source = "credit_card_billed"` or `"credit_card_unbilled"`):
- The scraper doesn't tag which card a CC movement belongs to
- **Fallback:** match to the first credit card account for that currency
- This is correct when the user has one card per currency (common case)
- See "Luka Connect Future Improvements" for the proper fix

**Email enrichment path:** When an email-matched transaction is found and enriched
(date updated), also set `bank_account_id` on it using the same `ba_map` lookup.
Currently the enrichment path only updates the date — it must also link the account.

**Import both billed and unbilled** as regular transactions, no distinction field.
Subsequent syncs only look back 3-4 days (controlled by `days_back` parameter),
so natural dedup handles the billed/unbilled transition.

---

## 5. Luka Connect API: `days_back` Parameter

**Trigger sync endpoint** (`POST /bank-connect/sync`) adds an optional `days_back: int = 4` query parameter.

Backend passes `days_back` through to Luka Connect when starting the scrape job.
This replaces the current `mode` concept in `trigger_sync()`. The backend does not
decide the value — the caller does:

- Frontend manual sync button: `days_back = 4`
- First connection / initial sync: `days_back = 90`
- Future auto-sync scheduler: `days_back = 4`

`trigger_sync()` passes `days_back` in the Luka Connect API request body. **Note:**
Luka Connect doesn't support this parameter yet (see Future Improvements 8.3),
so the backend should send it but Luka Connect will initially ignore it until updated.

Luka Connect is responsible for picking the scrape strategy based on this value
(see Future Improvements section).

---

## 6. Frontend — Transactions Page Balance Section

### Master currency toggle

- Position: next to "Saldos Disponibles" header, right-aligned
- Options: CLP | USD (pill toggle, active = blue filled, inactive = gray)
- Defaults to CLP
- USD option only enabled if user has USD accounts (disabled/grayed otherwise)
- **Filters both balance cards AND the transaction list** below

### 4 aggregated balance cards

| Card | Aggregation | Value | Sublabel | Background |
|------|------------|-------|----------|------------|
| Cuenta Corriente | Sum `balance_current` for all active checking/savings accounts in selected currency | Positive number | Account count if > 1 | Blue `#eff6ff` |
| Tarjeta de Crédito | Sum `balance_current` (negative) for all active CC accounts in selected currency | Negative number (red) | "gastado de $[sum of balance_limit]" | Red `#fef2f2` |
| Línea de Crédito | `balance_current` for line_of_credit in selected currency | Positive number | "disponible" | Green `#ecfdf5` |
| Posición Neta | checking + line_of_credit + TC used (all summed) | Dynamic | "líquido - deuda TC" | Green if >= 0, Red if < 0 |

### Edge cases

- No accounts for selected currency → show "$0" with "sin datos"
- Only one currency exists → show toggle but disable the other option
- No line of credit → hide that card (show 3 cards in grid)
- No credit cards → hide TC card and Posición Neta simplifies to just checking + LOC

### Transaction list

Existing list unchanged. Only change: filtered by selected currency from the toggle.
Existing filters (bank, category, month, search) continue to work independently.

### API endpoint update

`GET /bank-accounts` must be updated to include the new columns in its response:
`account_name`, `balance_current`, `balance_limit`, `last_synced_at`. The frontend
`BankAccountRow` type must replace the orphaned `balance_available` field with
`balance_limit` and add `account_name` + `last_synced_at`.

---

## 7. Frontend — Settings: Detected Accounts

### New section: "Cuentas Detectadas"

Added below the existing Luka Connect and email-linked sections. Grouped by bank.

Each account row shows:
- **Account name** (e.g., "Cuenta Corriente Moneda Local", "Visa Signature ****5032 Nacional")
- **Account kind badge** (Cta. Corriente, TC, Línea de Crédito)
- **Currency badge** (CLP / USD)
- **Current balance** (formatted)
- **Account type toggle**: Personal / Compartida (updates `account_type`)
- **Hide/Show toggle** (sets `is_active`, hidden accounts excluded from balance cards and filters)
- **Last synced** timestamp

**No delete button.** Accounts are managed by sync. Disconnecting the bank (existing button)
removes the credential and stops syncing, but accounts persist.

### Email-linked accounts

Unchanged. The "add bank account" flow for email stays as-is. Default email for new
email-linked accounts = user's registration email.

---

## 8. Luka Connect Future Improvements

Items to implement in the `luka-connect` repo in a future session. Not part of this spec's implementation.

### 8.1 Tag CC movements with card label
Each credit card movement should include a `cardLabel` field (e.g., "Visa Signature ****5032")
so the backend can link CC transactions to the correct card account instead of guessing
first-match per currency.

### 8.2 API vs HTML scrape strategy (Banco de Chile)
When `days_back <= 45`, use Banco de Chile's API instead of HTML scraping.
API returns data in seconds vs ~4 minutes for HTML scrape.

### 8.3 `days_back` parameter support
Luka Connect needs to accept and respect the `days_back` parameter when starting a scrape job.
This controls how far back to fetch movements.

### 8.4 Per-card movement sections
The scraper already parses billed/unbilled sections per card separately. It should preserve
the card association in the output so each movement knows which card it came from.

---

## Key Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Account granularity for CC | One per card per currency | Matches how Chilean banks report cupos (nacional vs internacional are separate credit lines) |
| Billed vs unbilled CC movements | Import both, no distinction | Subsequent syncs use 3-4 day window; natural dedup handles transition |
| Balance storage | Single `balance_current` + `balance_limit` columns | Simple, covers all account types. CC stores used (negative). |
| CC movement → account linking | First matching CC for currency (fallback) | Scraper doesn't tag card; correct for single-card-per-currency (common). Proper fix tracked in future improvements. |
| Currency display | Master toggle filtering everything | No mixing currencies. Toggle filters balances AND transactions. |
| Net financial position | Fourth balance card ("Posición Neta") | Quick health check: can I pay off next month's CC bill? |
| Sync window control | `days_back` param, decided by caller | Backend passes through; Luka Connect picks strategy (API vs scrape) |
| Detected accounts management | Hide/show toggle, no delete | Accounts managed by sync lifecycle, not user deletion |
| Account dedup key | `user_id + bank_name + account_name + currency` | Uses human-readable name from scraper, unique per bank |
