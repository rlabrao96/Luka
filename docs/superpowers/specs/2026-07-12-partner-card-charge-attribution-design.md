# Partner-Card Charge Attribution — Design

**Date:** 2026-07-12
**Status:** Approved (design), pending implementation plan
**Author:** Rafael + Claude

---

## Problem

Rafael and Camila are a couple; both are active Luka users in the same household, each tracking their own personal spending. Camila is an **authorized user** on Rafael's Amex Platinum. On the Amex/Plaid side an authorized-user card is **not** a separate account — Plaid returns a single "Platinum Card®" account whose transactions (both people's) all land in **Rafael's** Luka, because the Plaid item belongs to him.

Two consequences today:

1. **Camila's charges count as Rafael's.** The existing `split_type='partner'` per-transaction tag ("De mi pareja") removes a charge from Rafael's totals, but it does **not** move that charge into Camila's own Luka — it counts for nobody. Camila, who tracks her own spending, never sees her purchase.
2. **Camila also *pays* the shared card.** Her payments toward the bill appear on the Amex too, and there's no way to attribute them to her or to see a per-person balance on the shared card.

Plaid cannot help disambiguate: its transaction object carries no card-number, card-ending, or reliably-populated cardholder field (verified against the Plaid SDK `Transaction` schema — only `account_id`, shared across authorized-user cards, and `account_owner`, "not typically populated"). So attribution must be **user-driven**, initiated by Rafael (the only one who can see the shared card's transactions).

## Goal

Let Rafael **hand off** individual transactions on the shared card to Camila. A handed-off:

- **charge** becomes Camila's **personal expense** in her own Luka, and leaves Rafael's expense totals (settlement math untouched);
- **payment** becomes Camila's card payment (a transfer) in her Luka **and** feeds a per-person balance view on the shared card.

Camila is notified and may **reject** (bounce it back to Rafael); ignoring leaves it hers.

## Non-Goals

- Auto-detecting whose card made a charge (Plaid can't; email alerts are unavailable for this user).
- Routing Camila's charges through the couple's **shared / settlement** math — handed-off charges are her **personal** expenses only.
- Changing the account-level `account_type='partner'` behavior (a *separate* partner card that is entirely the partner's). That remains exclude-only and is out of scope here.
- Dual-split / joint-account interactions (unchanged).

---

## Design

### 1. Data model

New table **`transaction_attributions`** — one row per handed-off transaction:

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid pk | |
| `transaction_id` | uuid fk → transactions, **unique** | one attribution per transaction |
| `attributed_to_user_id` | uuid fk → users | the partner receiving it (Camila) |
| `attributed_by_user_id` | uuid fk → users | who handed it off (Rafael) |
| `status` | text | `active` (counts for the recipient) or `rejected` (bounced back) |
| `acknowledged_at` | timestamptz null | set when recipient taps "Confirmar"; UI-only, does not affect counting |
| `created_at` / `updated_at` | timestamptz | |

`attributed_to_user_id` and `attributed_by_user_id` must both be **active members of the same household** at write time.

A dedicated table (rather than columns on `transactions`) keeps the lifecycle self-contained, makes "recipient's incoming" and "sender's bounced-back" trivial to query, and survives re-syncs because it is keyed to the stable transaction row.

### 2. Lifecycle / state machine

```
Rafael tags a transaction "De mi pareja (tarjeta adicional)"
      │
      ├─ transaction_splits.split_type → 'partner'  (excluded from Rafael's totals —
      │                                              reuses the shipped mechanism;
      │                                              marked user-edited so re-sync won't revert)
      ├─ transaction_attributions row: attributed_to=Camila, status='active'
      └─ notification → Camila  (type 'charge_attributed')
                          │
            ┌─────────────┼──────────────────┐
        Confirmar        No es mío           Ignore
        (sets            status='rejected'   (no change)
        acknowledged_at) split_type reverts  stays 'active'
        counts for her   to 'personal'       counts for her
                         notify Rafael
                         (type 'attribution_rejected')
```

- **On tag it is immediately hers** (optimistic). Only an explicit **reject** pulls it back; ignore leaves it with her. This matches the intent: Rafael knows whose charge it is, so the notification is a heads-up + veto, not a gate.
- **Un-tag by Rafael** (he made the mistake): delete the attribution row and revert `split_type` to `personal`. No notification to Camila needed (it never mattered to her totals meaningfully, but if already acknowledged, send an informational note — see Edge cases).
- **Reject by Camila** reverts the split to `personal` (back in Rafael's totals) and notifies Rafael.

### 3. Query changes — "exactly one owner" invariant

A transaction counts toward **exactly one** person's personal totals: Rafael when not attributed-active, Camila when attributed-active — never both, never neither (while pending it is already `active` = hers).

**Rafael's side (already shipped, no change):**
- `get_dashboard_summary`, budgets v2, and `modules/transactions/totals.py` already exclude `split_type='partner'`. An attributed charge drops out automatically.
- `get_my_transactions` does **not** filter `partner`, so the charge stays visible in Rafael's list, labeled "De mi pareja".

**Camila's side (new work):**
- Her `get_my_transactions` and `get_dashboard_summary` (and budgets, category breakdown) change their owner predicate from
  `Transaction.user_id == caller`
  to
  `Transaction.user_id == caller  OR  (attributed to caller AND status='active')`.
- Attributed transactions are treated as her **personal** expenses (never shared).
- This predicate is defined **once** (a shared helper / query fragment) so the two sides cannot drift. It is the single complement of Rafael's exclusion.

**Effective-owner helper:** a single function `effective_owner(txn, attribution)` → `attributed_to_user_id if status='active' else txn.user_id`, used by both the totals predicate and the balance view so they agree by construction.

### 4. Privacy

Camila gains visibility into **specific rows** from Rafael's Amex — only the ones he attributed to her (her own purchases). She never sees the rest of the card, its balance, or its other transactions. Enforced by the attribution join (`attributed_to = caller AND status='active'`), not by exposing the `BankAccount`. Existing partner-privacy rules (a partner never sees the other's personal/`partner` rows) are otherwise unchanged.

### 5. Notifications

Reuse the `notifications` table + `create_notification` + the `merchant_review` approve/reject UI pattern.

- **On tag → Camila** — type `charge_attributed`, payload `{transaction_id, attribution_id, merchant, amount, currency, from_user_name}`. Card renders **Confirmar** / **No es mío**.
  - Confirmar → sets `acknowledged_at` (no counting change).
  - No es mío → `status='rejected'`, revert split, notify Rafael.
- **On reject → Rafael** — type `attribution_rejected`, payload `{transaction_id, merchant, amount, currency}` — "Cami dice que este cargo no es suyo — vuelve a tus gastos."

Frontend: add both types to `notifications/page.tsx` (icon + detail +, for `charge_attributed`, the two action buttons), mirroring the `new_account_detected` pattern already in place.

### 6. Taxonomy / UI

- The per-transaction `SplitTypeEditor` gains a third target: **Personal / Compartido / De mi pareja (tarjeta adicional)**. Selecting the third fires the hand-off (creates the attribution + notification) rather than only flipping the local split.
- Note this differs from the existing plain `partner` split (exclude-only): on the shared card, choosing "De mi pareja" now *also* creates an attribution to the household partner. The editor resolves the recipient as the other active household member (couples/2-member case; if >1 other member, prompt for which — see Edge cases).
- Camila's transaction list labels an attributed row as coming from the shared card (e.g. "de la tarjeta compartida"), read-only for her except the Confirmar / No es mío actions.

### 7. Per-person card balance view

On the shared Amex account detail (Rafael's side), show a per-person breakdown:

```
Platinum ••4012
  Rafael:  gastos $2,300 · pagos $2,300 · saldo $0
  Camila:  gastos $1,200 · pagos $1,000 · saldo $200
```

- Scope: transactions on that `bank_account_id`, grouped by **effective owner** (attributed_to when active, else account owner).
- **Gastos** = expense-type rows (abs of negative amounts). **Pagos** = payment/transfer rows toward the card (positive/credit). **Saldo** = gastos − pagos (what that person still owes on the card).
- Payments are attributed with the **same** "De mi pareja" tag (a payment is a transfer-type row on the card); an attributed payment never hits Camila's expense total, only her card-balance `pagos`.
- This view is pure reporting over the attribution data and can ship **after** the core hand-off.

---

## Edge cases

- **Re-sync:** attribution persists (separate row keyed to the stable transaction); the `split_type` flip is marked user-edited via the existing `mark_user_edited(txn, "split_type")`, so the merge pipeline will not revert it.
- **Refund / reversal of an attributed charge:** the attribution rides with the transaction; refund pairs / reimbursement groups are already excluded from totals on both sides.
- **Recipient ambiguity:** in a 2-member couple the recipient is unambiguous (the other member). If the household has >1 other active member, the editor prompts which member to hand it to. (Couples is the primary case; the prompt is the general fallback.)
- **Camila leaves the household:** her `active` attributions revert — `status` cleared and `split_type` back to `personal` on Rafael's rows — so nothing is "owned" by a non-member.
- **Un-tag after acknowledgment:** allowed; deletes the attribution and reverts the split. If `acknowledged_at` was set, send Camila an informational notification that the charge was removed from her account.
- **Currency:** attribution does not change a transaction's currency; Camila sees it in the transaction's own currency (multi-currency safe).
- **Double-count safety:** guaranteed structurally by the single `effective_owner` predicate — a row is in exactly one person's personal totals. Household **shared/settlement** aggregates are unaffected because attributed charges are personal, never `shared`.

## Testing (pytest, real DB, `asyncio_mode=auto`)

- Lifecycle: tag → `active` → reject → bounce (split reverts, Rafael notified); ignore stays `active` (hers).
- Exactly-one-owner: Rafael's totals drop the charge, Camila's gain it, never both; un-tag returns it to Rafael.
- Camila's dashboard/budget/category include her attributed charges as personal.
- Per-person balance math (gastos − pagos), including an attributed payment.
- Re-sync preserves attribution and the `partner` split.
- Privacy: Camila's queries return only her attributed rows from Rafael's card, nothing else on that account.
- Recipient guard: attribution requires both users to be active members of the same household.

## Build order

1. **Core hand-off** — table + migration, tag action (create attribution + split flip + notification), Camila's inclusion predicate, reject/bounce + un-tag, both notification types, `SplitTypeEditor` third option. Ship + verify.
2. **Per-person card balance view** — reporting over the attribution data on the shared-account detail.

## Touch points (reference)

- Backend: `modules/transactions/models.py` (+ new `transaction_attributions`), `modules/transactions/service.py` (`get_my_transactions`, `get_dashboard_summary`, `update_split_type`, new attribution service + `effective_owner`), `modules/transactions/totals.py`, `modules/budgets/v2_queries.py`, `modules/notifications/service.py`, a new Alembic migration.
- Frontend: `app/(dashboard)/components/SplitTypeEditor.tsx`, `app/(dashboard)/notifications/page.tsx`, the shared-account detail in `settings/components/BankAccountsSection.tsx` (balance view), `app/lib/api.ts` types.
</content>
</invoke>
