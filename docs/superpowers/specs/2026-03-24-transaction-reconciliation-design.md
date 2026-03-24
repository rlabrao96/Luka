# Transaction Reconciliation + Pending Block

**Date:** 2026-03-24
**Status:** Approved

## Overview

Add a visible reconciliation layer between email-captured transactions and Fintoc-settled transactions. A "Pendientes" block on the Transactions page surfaces 3 cases:

1. **Awaiting reconciliation** — email transaction waiting for next Fintoc sync
2. **Needs classification** — Fintoc transaction with no category
3. **Unmatched email** — email transaction that survived a Fintoc sync without a match

Also: cross-sender dedup for Banco de Chile (compra + comprobante pairs), and a hard delete endpoint for unmatched transactions.

## 1. Backend — New Endpoint: `GET /transactions/pending`

### Logic per case

| Case | Label | Query condition |
|------|-------|-----------------|
| Awaiting reconciliation | `awaiting_reconciliation` | `source IN ('gmail','outlook')` AND `status='pending'` AND (`bank_account.last_synced_at IS NULL` OR `bank_account.last_synced_at < txn.created_at`) |
| Needs classification | `needs_classification` | `source='fintoc'` AND `category IS NULL` AND `status='settled'` |
| Unmatched email | `unmatched_email` | `source IN ('gmail','outlook')` AND `status='pending'` AND `bank_account.last_synced_at >= txn.created_at` |

**For users without Fintoc** (no bank account): All email transactions go through the WhatsApp flow and become settled. No pending block needed — the endpoint returns empty lists.

**For awaiting_reconciliation vs unmatched_email:** The distinction is whether a Fintoc sync has run since the transaction was created. If `bank_account.last_synced_at >= txn.created_at`, at least one sync ran and didn't match it → it's unmatched. If no sync ran yet → still awaiting.

**Note:** Users may have multiple bank accounts. Check `last_synced_at` across all active bank accounts for the user — if ANY account has synced after the transaction's `created_at`, the transaction has had a chance to be matched.

### Response shape

```json
{
  "awaiting_reconciliation": [TransactionResponse, ...],
  "needs_classification": [TransactionResponse, ...],
  "unmatched_email": [TransactionResponse, ...]
}
```

Uses existing `TransactionResponse` schema. Auth: current user only.

### Endpoint: `DELETE /transactions/{id}`

Hard delete. Validates before deleting:
- Transaction belongs to current user
- `source IN ('gmail', 'outlook')` (only email transactions can be deleted)
- `status = 'pending'` (only pending transactions)

Returns 204 on success, 404 if not found, 403 if validation fails.

## 2. Backend — Cross-Sender Dedup

Banco de Chile sends pairs for the same purchase:
- `enviodigital@bancochile.cl` → "Compra con Tarjeta de Crédito"
- `serviciodetransferencias@bancochile.cl` → "Comprobante de Pago"

**Dedup logic:** In `process_email`, after parsing, before creating the transaction:

1. Query existing pending transactions for the same user where:
   - `amount` matches exactly
   - `transaction_date` is within 5 minutes
   - `status = 'pending'`
2. If a match exists → skip (don't create duplicate)

This is a simple pre-insert check, not a separate reconciliation pass.

## 3. Backend — Filter Pending from Main List

`GET /transactions/mine` currently returns all transactions. Change it to **exclude `status='pending'`** so pending email transactions don't appear in both the pending block and the main list.

Reconciled transactions (`status='reconciled'`) continue to appear in the main list — they're settled and confirmed.

## 4. Frontend — Pending Block Component

### Page layout order

```
TransactionsPage
  └── Filters (search, month, bank, category — top)
  └── SummaryBar (Fintoc balances only, filtered)
  └── PendingBlock (new — unfiltered, always shows all pending)
  └── Tabs: Todos / Personales / Compartidas
  └── RecentTransactions (settled + reconciled only)
```

### PendingBlock behavior

- **Hides entirely** when all 3 groups are empty
- Each sub-section hides individually when its group is empty
- **Not affected by filters** — always shows all pending items
- Orange background (`#FFF7ED`), orange border (`#FDBA74`), rounded corners

### Sub-sections

**"Esperando confirmación bancaria"** (Case 1)
- Informational only — no action buttons
- Shows source badge ("Email"), split type, category, amount, time
- These will auto-resolve when Fintoc syncs tonight

**"Necesitan categoría"** (Case 2)
- Blue "Clasificar" button on each row
- Opens existing `CategoryBottomSheet` component
- On save: `PATCH /transactions/{id}/category` → refetch pending

**"Sin match bancario"** (Case 3)
- Red outlined "Eliminar" button on each row
- Yellow left border (`#F59E0B`) for extra visibility
- Shows "X días sin match" age label
- On click: confirmation dialog → `DELETE /transactions/{id}` → refetch pending

### Header

```
Pendientes [5]     (no emoji, badge count)
```

## 5. Frontend — New Hook

`usePendingTransactions()` — calls `GET /transactions/pending`
- `staleTime: 30_000` (30 seconds, matches other hooks)
- Returns `{ awaiting_reconciliation, needs_classification, unmatched_email }`
- Total count for badge: sum of all 3 arrays

## 6. Reconciliation Status Transitions

```
Email arrives → Transaction(status="pending", source="gmail")
                    │
                    ├── Fintoc sync → match found → status="reconciled", fintoc_id set
                    │                                (appears in main list)
                    │
                    ├── Fintoc sync → no match → stays "pending"
                    │                             (appears in "Sin match bancario")
                    │                             User can delete (hard delete)
                    │
                    └── No Fintoc account → WhatsApp classifies → stays in pending block
                                            as "awaiting_reconciliation" (no sync to compare against)

Fintoc sync → new transaction, no email match → Transaction(status="settled", source="fintoc")
              │
              ├── Has category (from reconciled email) → appears in main list
              └── No category → appears in "Necesitan categoría"
                                User classifies via dashboard → appears in main list
```

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/modules/transactions/router.py` | Modified | Add `GET /pending`, `DELETE /{id}` |
| `backend/modules/transactions/service.py` | Modified | Add `get_pending_transactions()`, `delete_transaction()` |
| `backend/modules/transactions/router.py` | Modified | Filter `status='pending'` from `/mine` |
| `backend/jobs/tasks.py` | Modified | Add cross-sender dedup check before transaction insert |
| `frontend/app/(dashboard)/transactions/page.tsx` | Modified | Add PendingBlock between SummaryBar and Tabs |
| `frontend/app/(dashboard)/components/PendingBlock.tsx` | New | Pending block component with 3 sub-sections |
| `frontend/app/lib/hooks/useTransactions.ts` | Modified | Add `usePendingTransactions()` hook |
| `frontend/app/lib/api.ts` | Modified | Add `getPendingTransactions()`, `deleteTransaction()` |

## Testing

| Test | What it covers |
|------|---------------|
| `backend/tests/test_pending_transactions.py` (new) | 3 cases returned correctly, empty when no pending |
| `backend/tests/test_delete_transaction.py` (new) | Hard delete works, validates source/status, rejects Fintoc deletions |
| `backend/tests/test_cross_sender_dedup.py` (new) | BChile compra+comprobante pair creates only 1 transaction |
| `backend/tests/test_transactions_mine_filter.py` (new) | `/mine` excludes pending transactions |
