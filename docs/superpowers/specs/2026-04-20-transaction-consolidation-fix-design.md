# Transaction Consolidation — End-to-End Fix

**Date:** 2026-04-20
**Owner:** Rafael Labra
**Status:** Design approved, ready for implementation plan
**Related:** `docs/reviews/luka-review-2026-04-20-transaction-consolidation.md`

---

## 1. Problem

The transaction consolidation workflow — how Luka reconciles email-sourced pending transactions with bank-confirmed Plaid transactions, detects own-account transfers, and detects refund/reimbursement pairs — is broken in three visible ways:

1. **Pending backlog never drains.** 31 email-sourced pending transactions observed in production, some 6+ days old. Root cause: reconciliation only fires when a new Plaid transaction arrives. If Plaid posted before the email arrived (common for Zelle / BoA alerts), the email row is orphaned forever. No periodic retry, no aging, no orphan bucket.
2. **Credit-card bill payments are not recognized as transfers.** The `Pago Tarjeta ****3100` email-side pending row and the `American Express $2,000` + `Online Payment +$2,000` Plaid-side pair render as three independent items categorized as "Servicios" personal expense/income. `detect_transfers()` exists in the codebase but is **never called**; the CC counterpart lookup in `plaid/sync.py` is also inverted; `card_last_four` is extracted by the LLM but never persisted.
3. **Same-account refunds/reimbursements are not reconciled.** `Uber Eats ±$27.43` on a single AmEx card on the same day renders as an expense + an income with no link. The transfer detector explicitly excludes same-account pairs; no dedicated refund detector exists.

All three compound into a trust problem: dashboard totals are wrong, phantom activity appears, and the user has no UI tool to unblock themselves.

## 2. Goals

- Reconcile email → Plaid in both directions and on an ongoing basis, not one-shot.
- Correctly type CC bill payments as `transfer`, both legs linked via `transfer_pair_id`.
- Detect same-account refund pairs and link via `refund_pair_id`; exclude from spend/income math.
- Give the user explicit UI actions: manually link, dismiss (orphan), or delete any pending row, including in bulk.
- Canonical `status` vocabulary with `orphan` as a first-class state.
- One-time cleanup of Rafael's current 31-item backlog.

## 3. Non-goals

- Full P2P payment reconciliation (Zelle, Venmo, Chilean transferencias between different people) — out of scope; those remain `expense`/`income`.
- Cross-currency matching (USD email ↔ CLP Plaid with FX conversion) — out of scope.
- Automatic merchant normalization / enrichment beyond what's already in place.
- Changing the email parser layering (template → Gemini → regex) or the LLM waterfall.
- Background job observability / alerting infra.

## 4. Data model changes

### 4.1 New columns on `transactions`

| Column | Type | Nullable | Purpose |
|---|---|---|---|
| `card_last_four` | `VARCHAR(4)` | yes | Raw card suffix parsed from email body (LLM already extracts it; persist it). Used by reconciliation to resolve a `BankAccount`. |
| `refund_pair_id` | `UUID` | yes | Mirrors `transfer_pair_id`. Links a same-account refund pair. |
| `orphaned_at` | `TIMESTAMPTZ` | yes | Set when aging worker or user `dismiss` moves a pending row to orphan. |
| `dismissed_by_user` | `BOOLEAN` | default `false` | Distinguishes user-driven orphan from auto-aged orphan (for UX copy and analytics). |

### 4.2 Status vocabulary migration

- CHECK constraint: `status IN ('pending', 'settled', 'orphan')`.
- Data migration: `UPDATE transactions SET status='settled' WHERE status='confirmed'`.
- `plaid/sync.py`, `plaid/mapper.py`, and service queries updated to use `'settled'`.

### 4.3 Indexes

- `CREATE INDEX ... ON transactions (household_id, transaction_date DESC)`.
- `CREATE INDEX ... ON transactions (user_id) WHERE status='pending'` (partial).
- `CREATE INDEX ... ON transactions (transfer_pair_id) WHERE transfer_pair_id IS NOT NULL` (partial).
- `CREATE INDEX ... ON transactions (refund_pair_id) WHERE refund_pair_id IS NOT NULL` (partial).
- `CREATE EXTENSION IF NOT EXISTS pg_trgm;` + GIN on `raw_merchant_name gin_trgm_ops` (enables non-leading-wildcard merchant search).

### 4.4 Dashboard aggregation invariant

Every query that sums for a total (spend, income, budget, charts, runway) **must filter out**:
- `status = 'orphan'`
- `transfer_pair_id IS NOT NULL`
- `refund_pair_id IS NOT NULL`

Codify as a reusable `exclude_from_totals()` SQLAlchemy helper, applied uniformly in `transactions/service.py`.

## 5. Backend reconciliation pipeline

### 5.1 Fix CC counterpart detection (`plaid/sync.py`)

Replace `is_plaid_transfer`'s broken `bank_name.contains(merchant_name)` with a two-tier match executed at Plaid-sync time:

1. **Last-4 match:** if the Plaid tx is a credit-card payment (Plaid `category` includes `CREDIT_CARD` or `TRANSFER`) AND the household has a `BankAccount` whose `account_mask` matches a 4-digit suffix parsed from `plaid_tx.name` → link.
2. **Name match fallback:** `lower(merchant_name) LIKE '%' || lower(bank_name) || '%'` (corrected direction).

When either matches: set `tx.transaction_type='transfer'`, `tx.category=NULL`, `tx.transfer_to_account_id=<matched id>`.

### 5.2 Persist `card_last_four` on email ingest

- `email/llm_parser.py`: `ParsedEmail.card_last_four` already extracted → thread into `Transaction` row at ingest.
- `email/parser.py`: `_parse_cc_payment` captures `****NNNN` → extract the 4 digits.
- At insert: eager resolution — if a household `BankAccount.account_mask` matches, set `transfer_to_account_id` immediately. Otherwise leave null for the reconciliation tick to retry.

### 5.3 Wire `detect_transfers()` into the live pipeline

- Call at the end of `run_plaid_sync` (before commit) with `lookback_days=7`.
- Add inside the function: `user_id` equality (security), `currency` equality (logic), prefer smallest date delta when multiple candidates sum correctly.
- Continue to exclude same-account pairs — that's the refund detector's job.

### 5.4 Same-account refund detector (`reconciliation/refunds.py`)

New module. Detection rules (all required):

- same `bank_account_id`
- same `currency`
- same normalized `raw_merchant_name` (lowercased, whitespace-collapsed)
- same `abs(amount)`
- opposite signs
- refund's `transaction_date` is 0–90 days after the charge's
- neither already in a pair (`transfer_pair_id IS NULL AND refund_pair_id IS NULL`)

Writes a shared UUID into `refund_pair_id` on both rows. Does not change `transaction_type` (it stays `expense`/`income` for the historical narrative).

### 5.5 `reconciliation_tick` ARQ job (slow worker)

Registered with ARQ cron, runs every 15 minutes, per household:

1. **Email-after-Plaid pass.** For each email-source `status='pending'` row created >5 min ago, re-run `find_email_match` against existing Plaid rows in the same account/window. On match: `apply_match_and_delete_emails`.
2. **Transfer pass.** `detect_transfers(session, household_id, lookback_days=7)`.
3. **Refund pass.** `detect_refunds(session, household_id, lookback_days=90)`.
4. **Aging pass.** Email-source `pending` rows with `created_at < now - 14d` AND ≥1 Plaid sync has run for a linked `PlaidItem` since that tx's `created_at` → set `status='orphan'`, `orphaned_at=now()`. (The "≥1 sync since" check is important: if the bank was down, don't orphan.)

Idempotent; safe to run concurrently with email/Plaid webhooks because each operation is guarded by `WHERE transfer_pair_id IS NULL / refund_pair_id IS NULL / status='pending'`.

### 5.6 Reconciliation correctness patches (from review)

- `dedup.py _find_single_match`: add `currency` equality, skip merchant ILIKE when email `transaction_type='transfer'`, add `bank_account_id` match when both sides have one.
- `dedup.py apply_match_and_delete_emails`: add `user_id` guard on both delete and update queries; always propagate `transaction_type='transfer'` + null `category` when email had transfer type.
- `plaid/sync.py:140-145` modify-branch: route through `map_plaid_transaction` (fixes CLP 100× scaling bug).
- `transfers.py`: require `tx_a.user_id == tx_b.user_id`, require `currency` equality.
- `is_duplicate_transaction`: add `currency` equality, add `source_bank_name` equality in Tier 1.

## 6. API endpoints

All on `transactions/router.py`, authorized by `current_user.id` with an explicit `user_id` check in every query.

### 6.1 `GET /transactions/{pending_id}/match-candidates?window_days=7`

Returns up to 20 candidate bank txns for manual matching. Filters:
- same household, same currency
- `status='settled'`, `source='plaid'`
- `abs(amount)` within 2% of the pending row
- `transaction_date` within `window_days` of the pending row
- no existing `transfer_pair_id` / `refund_pair_id`

Ranked by `(date_proximity, merchant_token_overlap, amount_match_tightness)`.

### 6.2 `POST /transactions/{pending_id}/link` `{bank_transaction_id}`

Enforces both rows belong to `current_user.id`. Runs `apply_match_and_delete_emails` on the pair. Returns the enriched bank txn.

### 6.3 `POST /transactions/{pending_id}/dismiss`

Sets `status='orphan'`, `orphaned_at=now()`, `dismissed_by_user=true`. Row preserved for audit.

### 6.4 `POST /transactions/bulk-action` `{transaction_ids: [...], action: 'dismiss' | 'delete'}`

Caps at 100 IDs. Single-query ownership check first (`WHERE id IN (...) AND user_id = ?` count == len(ids)); otherwise 403. Then bulk UPDATE or DELETE.

## 7. Frontend changes

### 7.1 `PendingBlock.tsx`

- Render **three buckets** with counts: `awaiting_reconciliation`, `unmatched_email` (now populated by the aging pass), `needs_classification`.
- **Row action menu** (shadcn `DropdownMenu`): **Vincular…** → opens `LinkMatchDialog`; **Marcar como resuelta** → `/dismiss`; **Eliminar** → existing delete, now wrapped in shadcn `AlertDialog`. Fixes the currently-missing delete on `awaiting_reconciliation`.
- **Age badge** beside date: compute `daysOld` from `created_at`. Green `<3d`, amber `3–7d`, red `≥8d`. Text "hace N días". Sort `awaiting_reconciliation` oldest-first.
- **Bulk-select mode:** top-right "Seleccionar" toggle → row checkboxes → floating toolbar with "Marcar como resueltas (N)" / "Eliminar (N)". Designed for clearing Rafael's 31-item backlog in a few taps.
- Skeleton loader while `isLoading`; error card with retry on fetch failure.
- Collapsible header gets `aria-expanded` + `aria-controls`; all interactive pills get `aria-haspopup` + keyboard nav (migrate to shadcn `DropdownMenu`).

### 7.2 New `LinkMatchDialog.tsx`

- shadcn `Dialog`. Fetches `/match-candidates` for the selected pending row.
- Ranked candidate list (date, amount, merchant, account). Click to link.
- On success: optimistic update, invalidate `['transactions']` + `['transactions','pending']`.
- Empty state: "No hay coincidencias. ¿Marcar como resuelta?" CTA → fires `/dismiss`.

### 7.3 Pair-linked rendering (transfers + refunds)

In `TransactionCard.tsx` and list renderers:

- **Grouping pass** (client-side, once per query result): collect txns sharing the same `transfer_pair_id` or `refund_pair_id` into a single visual card keyed by the pair id.
- **Transfer pair card:** title `Pago tarjeta · US$2.000`, subtitle `Checking → American Express`, `⇄` icon, tap expands both legs.
- **Refund pair card:** title `Uber Eats · US$27,43 · reembolsado`, struck-through amount, muted color, `↺` icon, tap expands.
- Server-side totals endpoints already exclude these (see §4.4); the card rendering is purely visual consolidation.

### 7.4 Cross-cutting frontend cleanups

- **Unified `formatStoredAmount`** in `@/app/lib/currency.ts` driven by ISO 4217 decimals map. Delete the three duplicate helpers.
- **Negative amount a11y:** `aria-label="menos ${formatted}"` on negatives.
- **Locale** derived from user profile / `Intl.DateTimeFormat().resolvedOptions().locale`, not hardcoded `es-CL`.

## 8. One-time cleanup for Rafael's account

`backend/scripts/cleanup_rafael_pending.py` — idempotent, supports `--dry-run`:

1. Resolve Rafael's `user_id` via the email in memory (`rafaellabra96@gmail.com`).
2. Pass 1 — retry `find_email_match` for every pending email row against Rafael's current Plaid history.
3. Pass 2 — run `detect_transfers` + `detect_refunds` over his last 90 days.
4. Pass 3 — for remaining pending rows with `created_at < now - 7d`, set `status='orphan'` so they drop out of the pending block but remain in `unmatched_email` (user can then bulk-dismiss or manually link via the new UI).
5. Print summary: `re_matched=N, paired_transfer=N, paired_refund=N, orphaned=N`.

Run manually after Phase 2 ships.

## 9. Rollout phases

Each phase is independently shippable and verifiable.

- **Phase 1 — Data model.** Alembic migration for new columns, status CHECK, pg_trgm + indexes, `confirmed → settled` update. Deploy, smoke-test existing flows.
- **Phase 2 — Backend pipeline.** Fixes 5.1–5.6 + `reconciliation_tick` ARQ job. Deploy, observe backlog drain. Then run Rafael's cleanup script.
- **Phase 3 — API endpoints.** `/link`, `/dismiss`, `/bulk-action`, `/match-candidates` + service layer. Deploy.
- **Phase 4 — Frontend.** PendingBlock overhaul, `LinkMatchDialog`, pair-linked rendering, unified formatter, a11y fixes. Ship via Vercel.

Verification per phase:
- Backend — pytest with real DB (per CLAUDE.md). Add targeted tests in `backend/tests/reconciliation/` for: CC counterpart matching by last-4, refund detector rules, aging pass, bulk action authorization.
- Frontend — manual pass on the live dashboard with Rafael's account via browser-use; verify 31-item backlog reaches single digits after Phase 2, UI actions work end-to-end after Phase 4.

## 10. Risks & mitigations

- **Aging pass too aggressive →** legitimate bank-outage pendings get orphaned. Mitigation: require "≥1 Plaid sync has run since row's `created_at`" before orphaning.
- **Refund detector false positives** (two legitimate same-merchant same-amount expenses on the same card within 90d) → false "refund" pairing. Mitigation: require exact merchant string equality after normalization, opposite signs (one must be positive), and log every pairing for the first month so we can audit.
- **`confirmed → settled` migration** on a busy table. Mitigation: single-statement UPDATE with a partial index on `status='confirmed'` first; ran inside Alembic in a transaction; <1M rows expected near-term.
- **Bulk action abuse** (user sends 10k IDs). Mitigation: hard cap at 100 IDs server-side; UI doesn't expose larger selection.
- **Status vocabulary rollout** — if backend is mid-deploy and writes `'settled'` while frontend still filters `'confirmed'`, pending list flashes empty. Mitigation: Phase 1 migration does not change any code paths yet; Phase 2 ships the code changes atomically with the ARQ job registration.

## 11. Open questions (none blocking — flag if answers change)

- Should orphan auto-expiry exist (e.g. auto-delete orphans after 180d)? Not in scope; punt until we see real orphan volume.
- Should refund pairs get a user-override ("this is not a refund")? Not in scope; UI can show a menu later if users complain.
