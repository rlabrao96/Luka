# Shared-Card Charge Classification — Design

**Date:** 2026-07-12
**Status:** Approved direction (Approach A), pending implementation plan
**Author:** Rafael + Camila + Claude
**Builds on:** `2026-07-12-partner-card-charge-attribution-design.md` (the attribution feature this extends)

---

## Problem

An authorized-user card shares **one** Plaid account between two partners (Rafael's Amex Platinum, with Camila's additional card on it). Because Plaid rolls authorized-user cards into a single account and exposes **no per-transaction card identifier** (verified against the Plaid SDK), that one Luka account holds a mix of: Rafael's own charges, Camila's charges, and genuinely-shared expenses — with no automatic way to tell them apart.

The shipped per-transaction attribution ("De mi pareja") only represents **"the partner's personal expense."** It cannot represent a **shared expense the partner paid**: marking it `shared` credits the account owner (`Transaction.user_id`) as payer in settlement (`contribution_service.py:105`), and marking it `De mi pareja` makes it the partner's *personal* expense (out of the shared pot). So a shared cost Camila pays on her card lands correctly nowhere.

Forcing a who-paid decision on every card would be overwhelming. The couple wants the rich workflow **scoped to this shared card only**; normal accounts must stay simple.

## Goal

A card the owner flags **"shared with my partner"** (`shared_card`). Every charge on it starts **pending** (counts for nobody) and appears in **both** partners' Luka. Either partner sorts each charge — **first to sort wins** — into one of four outcomes:

| Outcome | Split | Counts as | Settlement effect |
|---|---|---|---|
| **Owner — personal** | personal | owner's personal expense | none |
| **Partner — personal** | partner | partner's personal expense (in their Luka) | none |
| **Owner — shared** | shared | shared household expense | credits **owner** as payer |
| **Partner — shared** | shared | shared household expense | credits **partner** as payer |

**Invariant the couple insists on:** *personal* (either person's) never counts for the other and never moves the couple's balance — even though one partner pays the whole card bill. Only the two *shared* outcomes touch settlement, each crediting the **actual payer**. This upholds Luka's no-debt-between-partners philosophy.

A **daily notification** nudges each partner about pending charges awaiting sort.

## Non-Goals

- Auto-detecting which physical card made a charge (Plaid can't).
- Changing behavior of non-`shared_card` accounts (personal/partner/joint) — untouched.
- Retroactively re-sorting already-classified history.
- Multi-person (>2) household ergonomics beyond correctness (the picker/queue must not corrupt data, but a full N-party UX is deferred).

---

## Design (Approach A — extend the attribution feature)

### 1. Card flag

`bank_accounts.account_type` gains a value **`shared_card`** (alongside `personal` / `partner` / `joint`). Set in Settings → Cuentas Bancarias by the account owner. Only `shared_card` accounts trigger the pending + four-way workflow.

### 2. Pending state — a DEDICATED signal, NOT the `status` column

`transactions.status` already encodes the **bank posting state** (`pending`/`settled`/`orphan`) and is overwritten unconditionally on every Plaid sync (`plaid/sync.py:308`: `tx.status = "pending" if plaid_tx.pending else "settled"`), independent of `user_edited_fields`. Overloading a `pending_classification` value onto it would (a) conflict with a charge that is simultaneously bank-pending, and (b) get silently clobbered to `settled` on the next sync — marking an unsorted charge as classified. These two dimensions are orthogonal.

Therefore classification-pending is a **new dedicated boolean column `transactions.needs_classification`** (default `false`):

- Set `true` at ingestion for a **non-transfer** charge whose target account is `shared_card`. (Transfers / CC bill payments are never pending — already excluded from totals, no who-paid sort needed.)
- Added to the single totals-exclusion rule in `modules/transactions/totals.py`, so a `needs_classification=true` charge counts for **nobody** — not either partner's dashboard, not any budget, not category breakdowns, not settlement — until sorted.
- **Survives re-sync** precisely because it is NOT the `status` column: Plaid/Connect syncs update `status` (bank state) but never touch `needs_classification`, so a bank pending→settled transition proceeds normally while the classification flag persists until a human sorts it.
- Sorting the charge sets `needs_classification=false` (and writes the split/attribution). It remains a single `transactions` row — no duplication.
- Also exclude `needs_classification=true` from `attribution.account_person_balances` (the per-person card balance view, which currently filters only `status notin (pending, orphan)`), so unsorted charges don't leak there.

Centralize the "is this account `shared_card` and this a non-transfer? → needs_classification=true" decision so all creation sites (Plaid `modules/plaid/sync.py`, Luka Connect `modules/bank_connect/router.py`, email pipeline, manual/WhatsApp) agree.

### 3. Shared review surface (both accounts)

Charges with `needs_classification=true` on the household's `shared_card` accounts are visible to **both active members**, regardless of `Transaction.user_id`. A new **"Por clasificar"** list (endpoint + UI) returns them. This is the one place the transaction becomes cross-member visible; it is scoped strictly to `needs_classification=true` shared-card rows (a partner never gains visibility into the owner's other transactions).

### 4. Four-way sort action

A single classify endpoint, callable by either active member, takes a `transaction_id` + one of the four outcomes and writes:

- **owner-personal:** `split_type='personal'`, no attribution. `needs_classification → false`.
- **partner-personal:** `split_type='partner'` + attribution `attributed_to = partner`, `attributed_by = actor`. `needs_classification → false`. (Identical to the shipped "De mi pareja" result — the partner's personal expense.)
- **owner-shared:** `split_type='shared'`, no attribution. `needs_classification → false`.
- **partner-shared:** `split_type='shared'` + attribution `attributed_to = partner` (recording the **payer**), `attributed_by = actor`. `needs_classification → false`.

The attribution row's meaning is disambiguated by the row's `split_type`: with `split_type='partner'` it means "partner's personal expense" (→ effective **owner** = partner); with `split_type='shared'` it means "partner paid this shared expense" (→ effective **payer** = partner). No new column beyond `needs_classification` — `attributed_to_user_id` + `split_type` encode all four outcomes.

**First-to-sort wins (optimistic concurrency):** the classify endpoint only acts on a row still `needs_classification=true`. If it was already sorted (flag now false), it returns `409 already_classified` with the actor who sorted it; the UI removes the row and shows "ya lo clasificó {name}". Mirrors the Trips optimistic-concurrency pattern.

Either partner may also **re-open / re-sort** a mistakenly-sorted charge (a "volver a clasificar" affordance) — out of v1 scope unless trivial; note as a follow-up.

### 5. Effective-payer in settlement — and the precise predicate guard

**Where the payer is credited:** NOT `contribution_service.py` (that only handles income). The shared-expense payer crediting lives in **`modules/households/service.py`** — the raw-SQL settlement / per-person / category-breakdown blocks (~lines 462, 539, 656, 735, 809) that `JOIN users u ON u.id = t.user_id`, `GROUP BY t.user_id`, `FILTER (WHERE ts.split_type='shared')`. Each must become `LEFT JOIN transaction_attributions a ON a.transaction_id = t.id AND a.status='active'` and group/credit by **`COALESCE(a.attributed_to_user_id, t.user_id)`** for shared rows. So a **partner-shared** charge credits the partner; an **owner-shared** charge credits the owner.

**Single helper:** add **`effective_payer_id(owner_user_id, attribution)`** (Python) alongside `effective_owner_id` in `modules/transactions/attribution.py`, and a matching SQL `COALESCE(...)` expression used by every `service.py` shared-paid query so they cannot drift.

**The precise predicate guard (reviewer-critical).** A partner-shared charge must count in the shared pot (via effective-payer), NOT as the partner's *personal* expense — but the paying partner must still SEE it. `attributed_to_clause` is reused in three predicates; the guard goes on exactly one:
- **`personal_scope_clause` (personal budget) — ADD the guard:** include an attributed row only when it is NOT `split_type='shared'`. Otherwise a partner-shared charge would wrongly appear in the partner's personal budget.
- **`list_visible_clause` (the partner's transaction list) — NO guard:** the partner who *paid* must still see the charge in their list (labeled shared). Keep including attributed rows.
- **`owned_by_caller_clause` (dashboard totals) — NO guard:** a partner-shared charge appears in the *payer's* dashboard cash-flow (consistent with how a member's own shared expense already shows), and is excluded from the *owner's* dashboard because it is attributed away. Exactly-one dashboard, no double-count; settlement handles the shared split separately.

**Personal rows** remain routed by the shipped exactly-one-owner predicates (attributed → partner's personal; else owner's), with no settlement effect. This §5 interaction is the highest-correctness-risk part of the feature — every case gets a test (see Testing).

### 6. Daily notification

A daily cron (fast worker, alongside the existing daily notification crons) sends each active member of a household with a `shared_card` a **`pending_card_classification`** notification when there are pending charges: "Tienes N cargos por clasificar en {card}." Deduped per day (idempotent per user/day). The notification deep-links to the "Por clasificar" surface. No notification when the pending count is zero.

### 7. Scoping / interaction with existing features

- Only `shared_card` accounts get pending + four-way. `personal`/`partner`/`joint` accounts are unchanged.
- The shipped per-transaction "De mi pareja" split option remains for non-`shared_card` accounts; on a `shared_card`, the four-way sort supersedes it (the split editor on a pending shared-card row shows the four-way action, not the plain split dropdown).
- Changing an account TO `shared_card` does not retroactively re-pend settled history (only new charges pend). Changing AWAY from `shared_card`: existing pending rows must resolve (default to owner-personal, or keep them in the queue until sorted) — decide in the plan; prefer resolving to owner-personal to avoid orphaned pending rows.

---

## Edge cases

- **Transfers / CC bill payments** on a shared_card: never pending; excluded from totals as today.
- **Refund / reversal** of a pending charge: if a pending charge is later removed/refunded by the bank, drop it from the queue (no classification needed).
- **Member leaves the household:** pending shared-card rows and any partner attributions revert per the shipped leave-household hook (`revert_attributions_for_member`) — extend it to also resolve pending rows to owner-personal.
- **Re-sync / dedup:** `needs_classification` survives re-sync by construction (syncs touch `status`, never this flag); a sorted row (`needs_classification=false`) is never re-pended. The `split_type`/attribution written by a sort are protected via the existing `mark_user_edited(txn, "split_type")` path.
- **Exactly-one-owner still holds:** a sorted charge counts for exactly one person (personal) or the shared pot with one payer (shared); a pending charge counts for nobody. No double-count, no silent drop after sort.
- **Concurrency:** two members sorting the same row — first wins (status guard); second gets 409.

## Testing (pytest, real DB)

- Pending charge on a shared_card counts for nobody (owner dashboard, partner dashboard, both budgets, settlement all exclude it).
- Each of the four sort outcomes: correct split, correct attribution, correct settlement effect (owner-personal/partner-personal → no settlement; owner-shared → owner credited; partner-shared → partner credited).
- **partner-shared does NOT leak into the partner's personal budget** (the personal-view exclusion of attributed-shared rows).
- Effective-payer: settlement credits the partner for a partner-shared charge; the owner for an owner-shared charge.
- First-to-sort wins: second classify on an already-sorted row → 409.
- Dual visibility: both members see a pending shared-card charge in "Por clasificar"; neither sees the owner's non-shared-card transactions there.
- Daily notification: fires once per member/day when pending>0; not when 0.
- Non-`shared_card` accounts: unchanged (no pending, no four-way).
- Ingestion: a charge on a shared_card via Plaid AND via Connect both land `pending_classification`.

## Build order (for the plan)

1. Card flag + pending status + totals-exclusion + ingestion sets pending. (Foundation; charges start pending and count for nobody.)
2. "Por clasificar" dual-visibility surface (endpoint + UI list).
3. Four-way sort action (endpoint + the split/attribution writes + first-wins guard) + split-editor wiring on shared-card rows.
4. Effective-payer in settlement/contribution + personal-view exclusion of attributed-shared rows.
5. Daily notification cron + card.
6. Edge cases (leave-household, re-sync, change-away-from-shared_card) + full verification.

## Touch points (reference)

- Backend: `modules/households/models.py` (`shared_card` account_type value), `modules/transactions/models.py` (new `needs_classification` column), `modules/transactions/totals.py` (exclude `needs_classification`), `modules/transactions/attribution.py` (`effective_payer_id` helper + SQL expr, classify ops, first-wins guard, `account_person_balances` exclusion), `modules/budgets/v2_queries.py` (`personal_scope_clause` attributed-shared guard — NOT the other predicates), **`modules/households/service.py`** (the ~5 raw-SQL shared-payer blocks → `LEFT JOIN transaction_attributions` + `COALESCE(attributed_to, t.user_id)`), `modules/plaid/sync.py` + `modules/bank_connect/router.py` (set `needs_classification` on ingest for shared_card), a new classify + "por clasificar" router, a daily-notification cron job (fast worker), a new Alembic migration (column + account_type). The `bank_accounts` PATCH endpoint accepts `shared_card`.
- Frontend: bank-account type selector (`shared_card` option), a "Por clasificar" review surface, the four-way sort control on shared-card rows, notification rendering for `pending_card_classification`, `app/lib/api.ts` types.
</content>
