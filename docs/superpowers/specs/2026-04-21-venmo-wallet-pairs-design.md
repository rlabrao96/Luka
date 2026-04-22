# Venmo / Wallet Funding-Pair Detection

**Date:** 2026-04-21
**Owner:** Rafael Labra
**Status:** Design proposed — pending user approval
**Related:** `backend/modules/reconciliation/transfers.py`, `docs/superpowers/specs/2026-04-20-transaction-consolidation-fix-design.md`

---

## 1. Problem

When a user connects Venmo (or any similar pass-through wallet), payments that exceed the Venmo balance are funded by the linked bank account. Luka currently records the same economic event twice:

- **Venmo row** — e.g. `Nicolas Celasco −$30.90` on Feb 6 (the real expense, with the counterparty's name).
- **BofA row** — e.g. `Venmo −$30.90` on Feb 9 (the funding leg, 3 calendar days later).

Both legs are **negative** (same sign), so the existing `detect_transfers()` routine — which requires opposite signs — never pairs them. The result is double-counted expenses in totals, budgets, and Sankey flows.

Symmetric issue exists for cash-outs (Venmo → BofA): opposite signs, but the existing ±2-day window misses ACH settlements that take 3–5 calendar days across a weekend.

## 2. Goals

- Stop double-counting Venmo (and other connected wallets') payments funded by a linked bank account.
- Correctly pair slow wallet cash-outs that settle beyond the current ±2-day window.
- Preserve the canonical expense row with the richest information (the Venmo side, which carries the counterparty's name).
- Retroactively fix Rafael's existing 3 months of data via a previewable backfill script.
- Run detection automatically going forward on the existing reconciliation tick — no new cron.

## 3. Non-goals

- Detecting pairs when the amount differs (e.g., BofA tops up $50 but Venmo spends $30.90, leaving $19.10 balance). User can still link manually.
- Inferring wallet pairs from merchant name alone when no matching wallet account is connected. This is explicit by design — a BofA "PAYPAL" row without PayPal connected stays as a real expense.
- New UI for the paired state. Existing transfer rendering applies.
- Support for Zelle/CashApp beyond what falls out naturally; the rule is data-driven off connected accounts, so any wallet added later works with no code change.

## 4. Core model

**A connected wallet account is a user-owned account, not a pass-through.** A BofA → Venmo top-up is conceptually a transfer between two places the user owns (same semantic as checking → savings). The Venmo-side row remains the canonical expense/income because it carries the counterparty name.

The existing detector handles **opposite-sign** pairs (money out of A, into B). We extend it to also handle **same-sign pairs** when at least one leg is on a connected wallet account.

## 5. Data model changes

**None.** We reuse:

- `transactions.transfer_pair_id` — shared UUID linking the two legs.
- `transactions.transaction_type` — re-typed to `transfer` on the bank leg only.

We add one identifier: an `is_wallet(bank_account)` predicate (see §6.1). No new columns, no migrations.

## 6. Detection rule

### 6.1 Wallet identification

A `BankAccount` is a **wallet** if any of:

1. `account_kind == 'wallet'` — new value added to `ACCOUNT_KIND_MAP` in `plaid/mapper.py`:
   - `("depository", "paypal") → "wallet"` (Plaid's subtype for Venmo and PayPal).
2. `lower(bank_name)` matches any of: `venmo`, `paypal`, `cash app`, `cashapp` (safety net for manually-added accounts or Plaid returning a non-paypal subtype).

The predicate lives in `backend/modules/reconciliation/wallets.py` as `is_wallet_account(ba: BankAccount) -> bool`. Called by the pairing routine only — it does not change how accounts are displayed or how budgets roll up elsewhere.

### 6.2 Pairing predicate

When scanning a household's recent transactions, for every unpaired transaction `tx_bank` **on a non-wallet bank account** whose merchant name contains the name of a connected wallet account in the same household (case-insensitive substring), search for a twin `tx_wallet` satisfying all of:

1. `tx_wallet.bank_account` is a wallet account (§6.1).
2. Same `household_id`, same `user_id`, same `currency`.
3. `abs(amount)` equal to the cent.
4. **Same sign** as `tx_bank` (funding direction) **OR** opposite sign (cash-out direction).
5. `|tx_wallet.date − tx_bank.date| ≤ 5 days`.
6. Neither leg has `transfer_pair_id` or `refund_pair_id` set.

On match:

- Allocate a fresh `transfer_pair_id` (uuid4) and assign to both rows.
- Re-type **only `tx_bank`** to `transaction_type='transfer'`.
- Leave `tx_wallet` with its existing type (`expense` if negative, `income` if positive) — it remains the canonical row.

### 6.3 Safety properties

| Situation | Outcome |
|---|---|
| Venmo balance covers payment, no BofA leg | Nothing to pair. Venmo row stays as expense. |
| BofA funds Venmo payment, both rows exist | BofA row becomes `transfer`; Venmo row stays as expense. |
| PayPal row on BofA, **PayPal not connected** | No wallet candidates. BofA PayPal row stays as real expense. |
| Amounts differ (partial top-up) | No match. Rows stay as-is. User can `Vincular` manually. |
| Venmo cash-out to BofA (opposite sign, 3-day ACH) | Paired via the wider ±5-day wallet window. BofA leg becomes `transfer`. |
| Two unrelated BofA rows of same amount within 5 days | Never paired against each other — at least one leg must be on a wallet account. |

### 6.4 Merchant-name gating

Gate the lookup on `tx_bank.merchant ILIKE '%<wallet_bank_name>%'` (for each connected wallet in the household). Without the gate, every BofA transaction would trigger a DB scan for twins; with it, we only look when the merchant name actually references a connected wallet. This is an optimization, not a correctness requirement — the wallet-account check in §6.2 already prevents false pairs.

## 7. Integration point

Add a new pass to `backend/modules/reconciliation/tick.py::reconciliation_tick_for_household`, between the existing transfer pass and the refund pass:

```
1. Email-after-Plaid rematch       (existing)
2. Transfer detection              (existing, unchanged: ±2 days, opposite-sign only)
3. Wallet-pair detection           (NEW: ±5 days, same- or opposite-sign, wallet-gated)
4. Refund detection                (existing)
5. Aging                            (existing)
```

Return dict gains one key: `wallet_pairs: int`.

Implementation lives in `backend/modules/reconciliation/wallets.py` with signature:

```python
async def detect_wallet_pairs(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 30,
) -> int:
    ...
```

`lookback_days=30` default (larger than the ±5 pair window so we catch pairs discovered after one leg ages past the existing 7-day transfer window). The pair window itself remains ±5.

## 8. Backfill

One-time script: `backend/scripts/backfill_wallet_pairs.py`.

- Runs `detect_wallet_pairs` across **all** transactions for a given household (no lookback cap) in **dry-run** by default.
- Prints a table: `bank_date | wallet_date | amount | bank_merchant | wallet_counterparty | bank_account_id | wallet_account_id`.
- Re-run with `--apply` to commit the re-typing + pairing.
- Idempotent: skips rows already paired.

CLI delivery (not an admin UI) because this is a one-time operation over 3 months of data and Rafael is the only affected user.

Usage:
```
python backend/scripts/backfill_wallet_pairs.py --household <uuid>
python backend/scripts/backfill_wallet_pairs.py --household <uuid> --apply
```

## 9. Tests

Add `backend/tests/test_reconciliation_wallet_pairs.py`:

1. **Same-sign funding pair matches.** BofA −$30.90 Feb 9 + Venmo −$30.90 Feb 6 → BofA becomes `transfer`, Venmo stays `expense`, both share `transfer_pair_id`.
2. **Opposite-sign cash-out within ±5 days matches.** Venmo −$50 Feb 1 + BofA +$50 Feb 5 → paired; BofA leg becomes `transfer`.
3. **No wallet connected, merchant name alone does not pair.** Two BofA rows ("PAYPAL" −$20 and an unrelated −$20) → no pair created.
4. **Partial top-up does not pair.** BofA −$50 + Venmo −$30.90 → no pair.
5. **Venmo-only payment (no BofA leg) stays as expense.** Single Venmo −$10 → no change.
6. **Already-paired rows are skipped.** Pre-set `transfer_pair_id` → detector leaves row untouched.
7. **Cross-household isolation.** Matching amounts in different households → no pair.
8. **Cross-currency isolation.** USD Venmo + CLP BofA of same numeric amount → no pair.

Reuse the existing pytest fixtures from `test_reconciliation_transfers.py`.

## 10. Rollout

1. Ship code behind no feature flag — the wallet-gated predicate makes it a no-op for any household without a connected wallet.
2. Run backfill dry-run on Rafael's household, review output.
3. Run backfill `--apply`.
4. Verify dashboard totals for Feb drop by the double-counted amount.

## 11. Open questions

None known — all decisions locked during brainstorming:

- Model: treat wallets as user-owned accounts (locked).
- Window: ±5 days for wallet pairs, ±2 for normal transfers (locked).
- Retroactive scope: full 3-month history with dry-run preview (locked).
- Backfill delivery: CLI, not admin UI (assumed — confirm at review).
- Widen window also applies to opposite-sign cash-outs when a wallet is involved (locked).
