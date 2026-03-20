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

---

## Backend

### `PATCH /bank-accounts/{account_id}`

New endpoint. Updates `account_type` and/or `is_active` on a bank account.

**Auth:** Bearer token. Only the account owner can edit (same rule as DELETE).

**Request body:**
```json
{
  "account_type": "personal" | "partner" | "joint",   // optional
  "is_active": true | false                             // optional
}
```

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

### `GET /bank-accounts` — updated response

Add `currency` and `is_active` fields to each account row:

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

### `POST /bank-accounts/fintoc/connect` — store currency

`FintocAccountIn` model gains a `currency: str | None` field. When creating the `BankAccount` row, set `bank_account.currency = acct.currency`.

### `POST /bank-accounts/webhooks/fintoc-link` — store currency

When parsing the accounts array from the Fintoc webhook payload, read `acc.get("currency")` and set it on the new `BankAccount` row.

### Transaction queries — respect `is_active`

`GET /transactions/mine` and `GET /transactions/shared` must join `bank_accounts` and filter `bank_accounts.is_active = TRUE`. Inactive accounts' transactions are excluded from all results.

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

**`FintocAccountIn` in `SelectedFintocAccount`** — add `currency?: string` so the picker can pass it to `connectFintocAccounts`.

**`ConnectFintocPayload` accounts array** — each entry gains `currency?: string`.

### `FintocAccountPicker.tsx` changes

Pass `currency` through from the `FintocAccount` object into each `SelectedFintocAccount` so it reaches the connect payload.

### `AccountCard` component (replaces `AccountRow`)

New component in `settings/page.tsx`. Card layout:

**Header row:**
- Bank name (bold, `text-luka-dark`)
- Currency badge: `CLP` or `USD` pill (gray if inactive)
- Account kind tag: "Cuenta Corriente", "Tarjeta de Crédito", etc.

**Body row:**
- Masked account number with reveal toggle (existing logic)
- Last sync time (existing logic)
- Import status badges (existing: Sincronizando / Error al sincronizar)
- Partner indicator for accounts not owned by current user

**Footer row:**
- Left: Toggle switch — active/inactive (only shown for own accounts)
  - Active: blue, label "Activa"
  - Inactive: gray, label "Inactiva", card visually dimmed (opacity-50)
- Right: Edit icon (pencil) + Disconnect button (only for own accounts)

**Edit mode (inline expand):**
- Triggered by pencil icon
- Shows three pill buttons for account type: Personal / Pareja / Compartida
- Save and Cancel buttons
- On Save: calls `api.updateBankAccount()`, optimistically updates local query cache, collapses edit mode
- On Cancel: collapses with no changes

**Inactive account behavior:**
- Card is dimmed (opacity-60)
- Badges are grayed out
- Toggle is in off position

### `ConnectBankSection` in `settings/page.tsx`

No structural changes. The card list now renders `AccountCard` instead of `AccountRow`.

---

## Data Flow

```
Fintoc widget → link.created webhook → backend creates BankAccount (with currency)
                                     → enqueues import_fintoc_history

GET /bank-accounts → AccountCard list
  → toggle is_active → PATCH /bank-accounts/{id}  → cache update
  → edit account_type → PATCH /bank-accounts/{id} → cache update
  → disconnect       → DELETE /bank-accounts/{id} → cache invalidation

GET /transactions/mine → joins bank_accounts WHERE is_active = TRUE
```

---

## Error Handling

- Toggle/edit failures show a small inline error message below the card ("No se pudo guardar. Intenta de nuevo.")
- Optimistic update: revert on failure
- Disconnect confirm flow unchanged (¿Seguro? → Sí / No)

---

## Testing

- Backend unit test: `PATCH` endpoint updates `account_type` and `is_active`; 403 for non-owner; 404 for missing account
- Backend unit test: `GET /bank-accounts` returns `currency` and `is_active` fields
- Backend unit test: `GET /transactions/mine` excludes transactions from inactive accounts
- Frontend: manual QA — connect account, verify currency badge appears; toggle inactive, verify transactions page no longer shows that account's data; edit type, verify badge updates
