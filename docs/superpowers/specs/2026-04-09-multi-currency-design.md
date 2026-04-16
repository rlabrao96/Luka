# Multi-Currency Support Design

**Date:** 2026-04-09
**Status:** Approved

---

## Goal

Expand Luka from CLP + USD to 16 LatAm currencies. Users declare which currencies they actively use via a pill bar on the transactions page. Each transaction displays in its own currency. No FX conversion.

---

## Supported Currencies

| Code | Name                  | Symbol  | Decimals | Thousands sep | Decimal sep | Large amount example  |
|------|-----------------------|---------|----------|---------------|-------------|-----------------------|
| CLP  | Peso chileno          | CLP$    | 0        | `.`           | —           | CLP$1.234.567         |
| USD  | Dólar estadounidense  | US$     | 2        | `,`           | `.`         | US$1,234.56           |
| COP  | Peso colombiano       | COP$    | 0        | `.`           | —           | COP$1.234.567         |
| BRL  | Real brasileño        | R$      | 2        | `.`           | `,`         | R$1.234,56            |
| MXN  | Peso mexicano         | MX$     | 2        | `,`           | `.`         | MX$1,234.56           |
| ARS  | Peso argentino        | AR$     | 2        | `.`           | `,`         | AR$1.234,56           |
| PEN  | Sol peruano           | S/      | 2        | `,`           | `.`         | S/1,234.56            |
| UYU  | Peso uruguayo         | $U      | 2        | `.`           | `,`         | $U1.234,56            |
| PYG  | Guaraní paraguayo     | ₲       | 0        | `.`           | —           | ₲1.234.567            |
| BOB  | Boliviano             | Bs.     | 2        | `,`           | `.`         | Bs.1,234.56           |
| VES  | Bolívar venezolano    | Bs.S    | 2        | `,`           | `.`         | Bs.S1,234.56          |
| DOP  | Peso dominicano       | RD$     | 2        | `,`           | `.`         | RD$1,234.56           |
| GTQ  | Quetzal guatemalteco  | Q       | 2        | `,`           | `.`         | Q1,234.56             |
| HNL  | Lempira hondureño     | L       | 2        | `,`           | `.`         | L1,234.56             |
| NIO  | Córdoba nicaragüense  | C$      | 2        | `,`           | `.`         | C$1,234.56            |
| CRC  | Colón costarricense   | ₡       | 0        | `.`           | —           | ₡1.234.567            |

**Formatting algorithm:**
1. If decimals = 0: format as integer, apply thousands separator
2. If decimals = 2: format with 2 decimal places, apply respective thousands and decimal separators
3. Prepend symbol (no space between symbol and number)

---

## Data Model

### New table: `user_currencies`

```sql
user_currencies (
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  currency_code CHAR(3) NOT NULL,
  is_primary    BOOLEAN NOT NULL DEFAULT false,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, currency_code)
)
```

**Rules:**
- Exactly one row per user must have `is_primary = true`
- On first GET /currencies, if the user has no rows, auto-seed from `users.preferred_currency`
- `users.preferred_currency` stays — it always mirrors the `is_primary` row and is still updated by PATCH /auth/me

### Existing tables — no schema changes

- `transactions.currency` (already TEXT, already stored per transaction)
- `bank_accounts.currency` (already TEXT, already stored per account)
- `users.preferred_currency` (kept for backward compatibility; kept in sync with is_primary)

---

## API

### GET /currencies
Returns the user's active currencies sorted by `sort_order`.

```json
[
  {"currency_code": "CLP", "is_primary": true, "sort_order": 0},
  {"currency_code": "USD", "is_primary": false, "sort_order": 1}
]
```

Auto-seeds from `preferred_currency` if no rows exist yet.

### POST /currencies
Adds a currency to the user's active list.

**Body:** `{"currency_code": "COP"}`

**Responses:**
- `201` — added successfully
- `400` — currency_code not in ALLOWED_CURRENCIES
- `409` — currency already in user's list

New row gets `sort_order = max(existing) + 1`, `is_primary = false`.

### DELETE /currencies/{code}
Removes a currency from the user's active list.

**Promotion logic:**
- If user has only 1 currency → `400` ("Debes tener al menos una moneda activa")
- If `code` is not primary → delete row; `sort_order` values of remaining rows are unchanged
- If `code` is primary AND others exist:
  1. Find the row with the lowest `sort_order` among remaining rows (excluding the one being deleted)
  2. Set that row to `is_primary = true`
  3. Update `users.preferred_currency` to that row's `currency_code`
  4. Delete the requested row
  5. `sort_order` values of remaining rows are NOT renumbered (gaps are acceptable)

**Transactions in deleted currencies:** Transactions whose `currency` matches a deleted currency are not affected — they remain in the DB and continue to appear in the "Todas" tab. The currency pill for that currency simply disappears. This is by design.

### PATCH /auth/me (existing — updated behavior)
When `preferred_currency` changes:
1. Validate against `ALLOWED_CURRENCIES` (now 16 codes)
2. Update `users.preferred_currency`
3. Sync `user_currencies`:
   - If table is empty for this user → insert new currency with `is_primary = true`, `sort_order = 0`
   - If new currency already exists in table → set it to `is_primary = true`; set old primary to `is_primary = false`
   - If new currency does not exist in table but other rows do → insert with `is_primary = true`, `sort_order = max(existing) + 1`; set old primary to `is_primary = false`

### ALLOWED_CURRENCIES (auth/schemas.py)
Expand from `{"CLP", "USD"}` to all 16 codes listed above.

---

## Backend Changes

### `backend/modules/auth/schemas.py`
- Expand `ALLOWED_CURRENCIES` set to all 16 currency codes

### `backend/modules/currencies/` (new module)
- `router.py` — GET/POST/DELETE endpoints
- `service.py` — CRUD logic + auto-seed + promotion logic
- `schemas.py` — `UserCurrencyOut`, `AddCurrencyBody`

### `backend/modules/auth/router.py`
- Update PATCH /auth/me to sync `user_currencies` when `preferred_currency` changes

### `backend/modules/whatsapp/sender.py`
- Extend `_format_amount()` to handle all 16 currencies with correct format per currency
- **Note:** `send_edit_options()` is already implemented in this file (WhatsApp Edit Transaction feature was partially applied). No conflict — only `_format_amount` needs extending.

### `backend/alembic/versions/029_user_currencies.py`
- Create `user_currencies` table
- **Note on numbering:** Current alembic head is `028`. This migration is `029` only if the pending `user-categories` plan has not yet been applied. If that plan lands first (it also needs a migration), renumber this to `030`. Always verify with `uv run alembic current` before creating the file.

### `backend/main.py`
- Register currencies router

---

## Frontend Changes

### `frontend/app/lib/api.ts`
- Add `getCurrencies()`, `addCurrency(code)`, `deleteCurrency(code)` API methods
- Add `UserCurrency` TypeScript interface

### `frontend/app/lib/hooks/useCurrencies.ts` (new)
- `useCurrencies()` — TanStack Query, fetches GET /currencies
- `useAddCurrency()` — mutation for POST /currencies
- `useDeleteCurrency()` — mutation for DELETE /currencies/{code}

### `frontend/app/lib/currency.ts` (new)
- `SUPPORTED_CURRENCIES` — array of `{code, name}` for all 16
- `formatAmount(amount: number, currency: string): string` — replaces `formatCLP`
- Correct formatting per currency (integer vs decimal, separators, symbol prefix)

### `frontend/app/(dashboard)/transactions/page.tsx`
- Add `CurrencyPillBar` component (inline or extracted)
- Fetches user currencies, renders pill per currency + "Todas" + "+" button
- Selected currency stored in local state (default: primary currency)
- Filters transaction list: if a currency is selected, only show `txn.currency === selected`; if "Todas", show all
- `[+]` opens a bottom sheet listing unselected currencies from `SUPPORTED_CURRENCIES`
- X on each pill calls `useDeleteCurrency`; cannot remove if only one remains (disable X)

### `frontend/app/(dashboard)/components/TransactionCard.tsx`
- Replace `formatCLP(amount)` with `formatAmount(amount, txn.currency)`

### `frontend/app/(dashboard)/components/PendingBlock.tsx`
- Replace any `formatCLP` usage with `formatAmount(amount, currency)`

### `frontend/app/(dashboard)/settings/components/TransactionsConfigSection.tsx`
- Rename label "Moneda preferida" → "Moneda principal"
- Expand CURRENCIES array to all 16 supported currencies
- Behavior unchanged (still sets preferred_currency via PATCH /auth/me)

---

## UX — Currency Pill Bar

```
[Todas]  [CLP ×]  [USD ×]  [+]
```

- "Todas" — no X, always visible, shows all transactions
- Currency pills — X button removes the currency (disabled if only one active currency)
- Primary currency pill — visually distinct (e.g., bold or underline), but still removable
- `[+]` — opens bottom sheet with the currencies not yet in the user's list; tapping one calls POST /currencies and closes the sheet
- Default selected on page load: primary currency (the one with `is_primary = true`); if for any reason the primary currency is not in the list, fall back to the first currency by `sort_order`
- Selection is local state (not persisted across page reloads)

---

## Coordination Notes

Three untracked plan files exist alongside this spec that affect implementation order and shared files:

### 1. `plans/2026-04-04-user-categories.md` (NOT YET IMPLEMENTED)
- Needs one Alembic migration (`category_type`/`is_custom` columns). Its plan file uses stale numbering (024); actual number will be 029.
- If user-categories lands **before** multi-currency, renumber `029_user_currencies.py` → `030_user_currencies.py`.
- Modifies `backend/modules/settings/schemas.py`, `service.py`, `router.py`, and `backend/tests/test_settings_api.py`. None of these conflict with multi-currency files.
- **Both plans modify `test_settings_api.py`** — coordinate so neither overwrites the other's assertions. Apply changes additively.

### 2. `plans/2026-04-04-whatsapp-edit-transaction.md` (PARTIALLY IMPLEMENTED)
- `send_edit_options()` is **already present** in `backend/modules/whatsapp/sender.py` (confirmed in code). No conflict.
- `backend/modules/whatsapp/session.py` has `save_active_edit` / `get_active_edit_transaction_id` / `clear_active_edit` — verify before re-implementing.
- `handle_text_message` in `handler.py` may or may not be implemented — check before adding.

### 3. `plans/2026-04-04-whatsapp-per-transaction-sessions.md` (ALREADY IMPLEMENTED)
- Per-transaction session keys and `save_msgid` / `get_transaction_id_by_msgid` were applied in Session 14. This spec was written after that — no action needed.

### Frontend `formatAmount` overlap
- `frontend/app/(dashboard)/components/TransactionCard.tsx` has a local `formatCLP()` — replace with `formatAmount(amount, txn.currency)` from the new `currency.ts`.
- `frontend/app/(dashboard)/transactions/page.tsx` has a local `formatAmount()` used **only inside `SummaryBar`** for account balance display (it divides USD by 100). Do **not** replace this with the global `currency.ts` version — balances and transactions use different storage units.

---

## Out of Scope (this release)

- FX conversion / totals in a single currency
- Home page KPIs / charts / budgets filtering by currency
- Email parser support for non-CLP/USD bank email formats
- Per-currency budgets

---

## Testing

- Unit tests for `formatAmount` covering all 16 currencies
- Unit tests for currency service: add, delete, auto-seed, primary promotion
- API tests for GET/POST/DELETE /currencies (validation, 409, promotion)
- Existing `test_settings_api.py` — update to include new currencies in ALLOWED_CURRENCIES check
