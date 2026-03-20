# Spec: Fintoc Account Settings Overhaul
**Date:** 2026-03-20
**Status:** Approved

---

## Overview

Improve the bank account settings experience after Fintoc connection. Users need to see the currency of each account, soft-disable accounts without losing data, change the account type (personal/joint) after connection, and see a professional card-based UI instead of a flat list.

---

## Goals

1. Store and display account currency (CLP / USD) from Fintoc data
2. Allow soft-disabling an account (keeps data, hides from transactions)
3. Allow inline editing of `account_type` per account
4. Redesign account list into card-per-account layout

---

## Non-Goals

- Currency conversion between accounts
- Changing the bank or reconnecting a Fintoc link
- Bulk editing multiple accounts at once

---

## Database

### Migration `010_bank_account_currency.py`

Add `currency` column to `bank_accounts`:

```sql
ALTER TABLE bank_accounts ADD COLUMN currency VARCHAR(3) NULL;
```

Nullable to avoid breaking existing rows. New accounts always have it populated from Fintoc.

### `BankAccount` ORM model (`backend/modules/households/models.py`)

Add `currency` column to the `BankAccount` SQLAlchemy model:

```python
currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
```

Without this, SQLAlchemy will not serialize the column in responses and the `PATCH` handler cannot assign to it.

---

## Backend

### `PATCH /bank-accounts/{account_id}`

New endpoint. Updates `account_type` and/or `is_active` on a bank account.

**Auth:** Bearer token. Only the account owner can edit (same rule as DELETE).

**Request body (Pydantic):**
```python
class UpdateBankAccountBody(BaseModel):
    account_type: Literal["personal", "partner", "joint"] | None = None
    is_active: bool | None = None
```

Use `Literal` (not bare `str`) so invalid values return `422` from FastAPI validation before reaching the DB CHECK constraint.

**Guard:** If `is_active=False` is requested and the account's `import_status` is `'pending'` or `'importing'`, return `409 Conflict` with detail `"Cannot disable an account while its history import is in progress"`. This prevents the stale-guard logic from missing accounts mid-import.

**Response:**
```json
{
  "id": "...",
  "account_type": "personal",
  "is_active": true
}
```

**Errors:**
- `404` — account not found in household
- `403` — caller is not the account owner
- `409` — tried to disable while import is in progress

### `GET /bank-accounts` — updated response

**Remove the `is_active.is_(True)` filter.** Return all accounts (active and inactive) so the settings UI can render the toggle in its correct state and show dimmed inactive cards. The existing `is_active` column is already in the model.

Add `currency` and `is_active` to the serialized response dict:

```json
{
  "id": "...",
  "bank_name": "Banco de Chile",
  "account_type": "personal",
  "account_kind": "checking_account",
  "account_number": "****1234",
  "cardholder_name": null,
  "currency": "CLP",
  "is_active": true,
  "user_id": "...",
  "import_status": "done",
  "fintoc_account_id": "...",
  "last_synced_at": "2026-03-20T12:00:00Z"
}
```

Note: The stale-guard logic (marking stuck imports as `"failed"`) should still apply to all returned accounts regardless of `is_active`.

### `POST /bank-accounts/fintoc/connect` — store currency

`FintocAccountIn` model gains a `currency: str | None = None` field. When creating the `BankAccount` row, set `bank_account.currency = acct.currency`.

### `POST /bank-accounts/webhooks/fintoc-link` — store currency

When parsing the accounts array from the Fintoc webhook payload, read `acc.get("currency")` and set it on the new `BankAccount` row.

### Transaction queries — respect `is_active`

All three transaction endpoints must exclude transactions from inactive accounts:

1. **`GET /transactions/mine`** — add a join to `bank_accounts` and filter `bank_accounts.is_active = TRUE`.
2. **`GET /transactions/shared`** — same join + filter.
3. **`GET /transactions/monthly-summary`** — this endpoint uses a raw `text()` SQL query. Add an explicit `JOIN bank_accounts ba ON ba.id = t.bank_account_id WHERE ba.is_active = TRUE` clause to the raw SQL.

---

## Frontend

### `api.ts` changes

**`BankAccountRow` type** — add:
```ts
currency: string | null;
is_active: boolean;
```

**`UpdateBankAccountPayload` type** (new):
```ts
export interface UpdateBankAccountPayload {
  account_type?: "personal" | "partner" | "joint";
  is_active?: boolean;
}
```

**`api.updateBankAccount()`** (new):
```ts
updateBankAccount: (accountId: string, householdId: string, payload: UpdateBankAccountPayload) =>
  apiFetch<{ id: string; account_type: string; is_active: boolean }>(
    `/bank-accounts/${accountId}?household_id=${householdId}`,
    { method: "PATCH", body: JSON.stringify(payload) }
  )
```

**`SelectedFintocAccount`** — add `currency?: string` so the picker can pass it to `connectFintocAccounts`.

**`ConnectFintocPayload` accounts array** — each entry gains `currency?: string`.

### `FintocAccountPicker.tsx` (`frontend/app/(dashboard)/components/FintocAccountPicker.tsx`)

Pass `currency` through from the `FintocAccount` object (which already has `currency: string` typed) into each `SelectedFintocAccount` so it reaches the connect payload via `onConfirm`.

### `AccountCard` component (replaces `AccountRow` in `settings/page.tsx`)

**Header row:**
- Bank name (bold, `text-luka-dark`)
- Currency badge: `CLP` or `USD` pill (grayed out if inactive)
- Account kind tag: "Cuenta Corriente", "Tarjeta de Crédito", etc.

**Body row:**
- Masked account number with reveal toggle (existing logic)
- Last sync time (existing logic)
- Import status badges (existing: Sincronizando / Error al sincronizar)
- Partner indicator for accounts not owned by current user

**Footer row:**
- Left: Toggle switch — active/inactive (only shown for own accounts)
  - Active: blue, label "Activa"
  - Inactive: gray, label "Inactiva"
- Right: Edit icon (pencil) + Disconnect button (only for own accounts)

**Card inactive state:**
- Card is dimmed (`opacity-60`)
- All badges grayed out
- Toggle is in off position

**Edit mode (inline expand below footer):**
- Triggered by pencil icon
- Shows three pill buttons for account type: Personal / Pareja / Compartida
- Save and Cancel buttons
- On Save: calls `api.updateBankAccount()` with `account_type`; optimistically updates the account entry in `["bank-accounts", householdId]` query cache via `setQueryData`; collapses edit mode
- On Cancel: collapses with no changes
- On failure: reverts the optimistic update and shows inline error: "No se pudo guardar. Intenta de nuevo."

**Toggle behavior:**
- On toggle: calls `api.updateBankAccount()` with `is_active`
- Optimistic update: immediately flip `is_active` in cache via `setQueryData`
- On failure: revert and show inline error
- In-flight guard: disable toggle button while the PATCH request is in flight to prevent rapid double-toggling
- If backend returns `409` (import in progress): show inline message "Espera a que termine la sincronización antes de desactivar."

### `ConnectBankSection` in `settings/page.tsx`

No structural changes. The card list now renders `AccountCard` instead of `AccountRow`.

---

## Data Flow

```
Fintoc widget → link.created webhook → backend creates BankAccount (with currency)
                                     → enqueues import_fintoc_history

GET /bank-accounts → returns ALL accounts (active + inactive)
  → AccountCard list (inactive cards dimmed)
  → toggle is_active  → PATCH /bank-accounts/{id} → optimistic cache update
  → edit account_type → PATCH /bank-accounts/{id} → optimistic cache update
  → disconnect        → DELETE /bank-accounts/{id} → cache invalidation

GET /transactions/mine          → JOIN bank_accounts WHERE is_active = TRUE
GET /transactions/shared        → JOIN bank_accounts WHERE is_active = TRUE
GET /transactions/monthly-summary → raw SQL JOIN bank_accounts WHERE is_active = TRUE
```

---

## Testing

- Backend: `PATCH` updates `account_type` and `is_active`; 403 for non-owner; 404 for missing account; 409 when disabling mid-import
- Backend: `GET /bank-accounts` returns both active and inactive accounts with `currency` and `is_active` fields
- Backend: `GET /transactions/mine` excludes transactions from inactive accounts
- Backend: `GET /transactions/monthly-summary` excludes inactive account transactions
- Frontend: manual QA — connect account → verify currency badge; toggle inactive → verify transactions page excludes that account; edit type → verify badge updates; toggle during import → verify 409 message shown
