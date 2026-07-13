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

### 2. Pending state

New charges landing on a `shared_card` account are created with **`status = 'pending_classification'`** (a new status value). This status is added to the single totals-exclusion rule in `modules/transactions/totals.py`, so a pending charge counts for **nobody** — not the owner's or partner's dashboard, not any budget, not category breakdowns, not settlement — until it is sorted. It remains a single `transactions` row (no duplication); the classification writes onto that row + an attribution row.

Ingestion sites that must set `pending_classification` when the target account is `shared_card`: Plaid sync (`modules/plaid/sync.py`), Luka Connect (`modules/bank_connect/router.py`), email pipeline, and any manual/WhatsApp path. Centralize the "is this a shared_card? → pending" decision so all creation sites agree.

Transfers (CC payments) on a `shared_card` are NOT pending — a bill payment is a transfer and already excluded from totals; it needs no who-paid sort.

### 3. Shared review surface (both accounts)

Pending `shared_card` charges are visible to **both active members** of the account's household, regardless of `Transaction.user_id`. A new **"Por clasificar"** list (endpoint + UI) returns pending charges on the caller's household's `shared_card` accounts. This is the one place the transaction becomes cross-member visible; it is scoped strictly to pending shared-card rows (a partner never gains visibility into the owner's other transactions).

### 4. Four-way sort action

A single classify endpoint, callable by either active member, takes a `transaction_id` + one of the four outcomes and writes:

- **owner-personal:** `split_type='personal'`, no attribution. `status → settled`.
- **partner-personal:** `split_type='partner'` + attribution `attributed_to = partner`, `attributed_by = actor`. `status → settled`. (Identical to the shipped "De mi pareja" result — the partner's personal expense.)
- **owner-shared:** `split_type='shared'`, no attribution. `status → settled`.
- **partner-shared:** `split_type='shared'` + attribution `attributed_to = partner` (recording the **payer**), `attributed_by = actor`. `status → settled`.

The attribution row's meaning is disambiguated by the row's `split_type`: with `split_type='partner'` it means "partner's personal expense" (→ effective **owner**); with `split_type='shared'` it means "partner paid this shared expense" (→ effective **payer**). No new column is required — `attributed_to_user_id` + `split_type` encode all four outcomes.

**First-to-sort wins (optimistic concurrency):** the classify endpoint only acts on a row still in `pending_classification`. If it has already been sorted (status advanced), it returns `409 already_classified` with the actor who sorted it; the UI removes the row from the queue and shows "ya lo clasificó {name}". Mirrors the Trips optimistic-concurrency pattern.

Either partner may also **re-open / re-sort** a mistakenly-sorted charge (a "volver a clasificar" affordance) — out of v1 scope unless trivial; note as a follow-up.

### 5. Effective-payer in settlement/contribution

Today `contribution_service` credits a shared expense's payment to `Transaction.user_id`. Add an **effective-payer** expression — for a `shared` row, payer = `attributed_to_user_id` when an active attribution exists, else `Transaction.user_id` — mirroring the `effective_owner` helper built for personal rows. Apply it in the household contribution/settlement/breakdown queries so a **partner-shared** charge credits the partner, not the account owner.

**Personal rows** are already routed correctly by the shipped exactly-one-owner predicates (attributed → partner's personal; else owner's), with no settlement effect. The one adjustment: the **personal-view predicates must not swallow attributed-SHARED rows** — `attributed_to_clause` (used in personal totals/list/budget) must additionally require the row is NOT `split_type='shared'`, so a partner-shared charge counts in the shared pot (via effective-payer) and NOT as the partner's personal expense. This is the key interaction to get right and test.

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
- **Re-sync / dedup:** the `pending_classification` status must survive re-sync; a user-sorted row must not be re-pended (respect `user_edited_fields` / the settled status).
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

- Backend: `modules/households/models.py` (account_type value), `modules/transactions/models.py` (status), `modules/transactions/totals.py` (exclude pending), `modules/transactions/attribution.py` (effective_payer, classify ops), `modules/transactions/service.py` + `modules/budgets/v2_queries.py` (personal-view attributed-shared exclusion), `modules/households/contribution_service.py` (effective-payer), `modules/plaid/sync.py` + `modules/bank_connect/router.py` (pending on ingest), a new classify + "por clasificar" router, a daily-notification job, a new Alembic migration.
- Frontend: bank-account type selector (`shared_card` option), a "Por clasificar" review surface, the four-way sort control on shared-card rows, notification rendering for `pending_card_classification`, `app/lib/api.ts` types.
</content>
