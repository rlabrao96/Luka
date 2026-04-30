# Viajes (Trips) — Splitwise-style Section

**Date:** 2026-04-30
**Status:** Draft — pending review
**Owner:** Rafael Labra
**Scope:** v1 design for a new top-level section that lets Luka users tie transactions to trips and split costs among attendees (Luka users + external name stubs).

---

## 1. Problem & Goals

Luka users routinely take group trips with friends or partners and need to track who paid what, settle balances afterwards, and avoid the disconnect between "the bank reality" (full charge on one card) and "the budget reality" (only my share is my actual spend). Today this happens off-platform (Splitwise, spreadsheets, mental math), creating leakage from Luka's value proposition as a one-stop personal finance tool.

**Goals (v1):**

1. Users can create a trip, invite Luka attendees, and add external (name-only) attendees.
2. Users can tag their own real Luka transactions to a trip and choose how to split each one.
3. Users can log expenses paid by other attendees as **trip-only stubs** that never touch their personal ledger, budget, or category totals.
4. Users see smart, currency-consistent balances inside each trip and a minimum-transactions settlement plan.
5. Settling up via Zelle/Venmo/bank transfer is auto-detected from real Luka transactions and surfaced as a one-tap confirm.
6. Multi-currency expenses are preserved natively but displayed in a single trip base currency.

**Non-goals (v2+):**

- Native mobile contact-picker integration.
- WhatsApp invites, WhatsApp expense-add or settlement actions.
- Itemized splits within a single transaction.
- Recurring trips (poker night).
- Receipt photo attachments.
- CSV/PDF export of trip ledger.
- External-attendee → real Luka user merge when an external signs up.
- Dual-split: a transaction that is both household-shared *and* trip-split simultaneously.
- Per-user currency display preference inside a trip.
- Frontend automated test infrastructure (separate ~2-day initiative; tracked in NEXT-STEPS).

---

## 2. Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Attendee model | Luka users + external name-only stubs | Most trip companions aren't on Luka. External merge is a v2 problem. |
| Tagging | Manual + date-range auto-suggest | Manual always works; suggestions reduce friction without false-tagging subscriptions/recurring bills. |
| Splits | Equal-by-default + per-expense override (custom amount or %) | Splitwise model. Equal covers ~80%; overrides handle "boat tour was just 3 of us". |
| Settle-up | Display + auto-detect + manual mark | Reuses Luka's transaction capture; closes the loop without payment integration. |
| Permissions | Flat: any Luka attendee can add/edit expenses; **creator-only** delete + remove-others; anyone can self-leave | Flat for daily use, anchored owner for destructive actions. |
| Multi-currency | Native amounts preserved; trip base currency for display, set at creation, applies to all attendees | Honest ledger + simple consistent UX (no per-user toggle). |
| Recording convention | Real transaction stays at its true amount; only the user's split share counts in their personal budget/categories; the rest is a trip receivable | Mirrors existing `transaction_splits` shared-expense pattern. |
| Linkage | One Luka transaction ↔ at most one trip expense | Itemized split (Costco "half trip groceries") deferred to v2. |
| Notifications | In-app only for v1 | WhatsApp triggers deferred to v2 for consistent scope. |
| Invites | Email/phone search + name stub + shareable join link with rotating token | Dodges WhatsApp-sender problem; user shares link via any channel. |
| Frontend tests | None for v1 (matches current project state); /browser-use verification | Test infra is a project-wide initiative, not a Trips deliverable. |

---

## 3. Data Model

All new tables live in the `public` schema, follow existing snake_case + UUID conventions, and have RLS enabled.

### 3.1 `trips`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| creator_user_id | uuid FK users(id) | Owner of destructive actions. |
| name | text | |
| start_date | date | |
| end_date | date | `>= start_date` (CHECK). |
| base_currency | char(3) | ISO 4217. |
| status | text | `active` \| `archived`. Default `active`. |
| invite_token_hash | text | **SHA-256 of the raw token; only the hash is stored.** Indexed unique. Nullable. The raw token is returned to the client exactly once at generation/rotation. |
| invite_token_expires_at | timestamptz | Nullable. Default 30 days from rotation. |
| created_at, updated_at | timestamptz | |

### 3.2 `trip_attendees`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trip_id | uuid FK trips(id) ON DELETE CASCADE | |
| user_id | uuid FK users(id) | NULL = external stub. |
| display_name | text | Always set; for externals, this is their name. For Luka users, snapshot of name at add time (display only). |
| left_at | timestamptz | NULL = active. |
| created_at | timestamptz | |

Constraints:
- Unique `(trip_id, user_id)` partial index where `user_id IS NOT NULL`.
- A user cannot be added more than once even if they previously left (re-adding clears `left_at` instead).

### 3.3 `trip_expenses`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trip_id | uuid FK trips(id) ON DELETE CASCADE | |
| payer_attendee_id | uuid FK trip_attendees(id) | |
| description | text | |
| amount | numeric(14,2) | **Always positive.** When created from a Luka transaction, `amount = abs(transaction.amount)` (Luka stores expenses negative; trip ledger is positive-only for clarity). |
| currency | char(3) | |
| expense_date | date | |
| transaction_id | uuid FK transactions(id) | NULL = manual stub. |
| fx_rate_to_base | numeric(20,10) | Multiplier from `currency` to trip `base_currency` **at expense creation time**. Frozen — never re-fetched. NULL when `currency = base_currency`. |
| created_by_user_id | uuid FK users(id) | |
| version | int NOT NULL DEFAULT 1 | Optimistic-concurrency token. PATCH must send `If-Match` header with current version; server increments on update; mismatch → 409. |
| created_at, updated_at | timestamptz | |
| deleted_at | timestamptz | Soft delete for audit. |

Constraints:
- Unique partial index on `transaction_id` where `transaction_id IS NOT NULL` and `deleted_at IS NULL` — enforces 1:1 transaction ↔ trip expense.
- CHECK: `amount > 0`.
- CHECK: `(currency = base_currency) OR (fx_rate_to_base IS NOT NULL)` (validated via trigger or app-level since cross-table CHECKs need a function).

### 3.4 `trip_expense_splits`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trip_expense_id | uuid FK trip_expenses(id) ON DELETE CASCADE | |
| attendee_id | uuid FK trip_attendees(id) | |
| share_amount | numeric(14,2) | **Positive.** In expense's currency. Sum across rows must equal expense.amount exactly (validated at write — see §3.9 for the rounding rule). |
| share_type | text | `equal` \| `custom_amount` \| `custom_percent`. Informational only; share_amount is authoritative. |

Constraints:
- Unique `(trip_expense_id, attendee_id)`.

### 3.5 `trip_settlements`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trip_id | uuid FK trips(id) ON DELETE CASCADE | |
| from_attendee_id | uuid FK trip_attendees(id) | Payer (debtor). |
| to_attendee_id | uuid FK trip_attendees(id) | Recipient (creditor). |
| amount | numeric(14,2) | **CHECK `amount > 0`.** |
| currency | char(3) | |
| fx_rate_to_base | numeric(20,10) | NULL if `currency = base_currency`. Frozen at settlement creation. |
| settled_at | timestamptz | |
| transaction_id | uuid FK transactions(id) | NULL = marked manually; set when auto-matched to Zelle/Venmo. |
| created_by_user_id | uuid FK users(id) | |
| write_off | boolean NOT NULL DEFAULT false | True when this settlement was created by the creator's force-remove action to zero out drift. Audit-only flag. |
| created_at | timestamptz | |

CHECK: `from_attendee_id <> to_attendee_id` AND `amount > 0`.

### 3.6 `trip_suggestion_dismissals`
| user_id, trip_id, transaction_id, dismissed_at |
PK `(user_id, trip_id, transaction_id)`. Suppresses an in-window transaction from re-appearing in the suggestions inbox.

### 3.7 `trip_settlement_dismissals`
| user_id, transaction_id, dismissed_at |
PK `(user_id, transaction_id)`. Suppresses an auto-detected settlement suggestion from re-firing.

### 3.7b `trip_base_currency_changes`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| trip_id | uuid FK trips(id) ON DELETE CASCADE | |
| old_currency | char(3) | |
| new_currency | char(3) | |
| cross_rate | numeric(20,10) | The `old_base → new_base` multiplier applied to every existing `fx_rate_to_base` at change time. |
| changed_by_user_id | uuid FK users(id) | |
| changed_at | timestamptz | |

Append-only audit. Used to verify the re-anchor math after the fact and to support a future "show base-currency history" UI.

### 3.8 Reused tables — additive constraint (mutual exclusivity)

- **`transactions`** — no schema change.
- **`transaction_splits`** — a `BEFORE INSERT/UPDATE` trigger on `transaction_splits` rejects rows whose `transaction_id` is already linked to a non-deleted `trip_expenses` row. Symmetric trigger on `trip_expenses` rejects creating a trip-expense link for a transaction that already has `transaction_splits`.
- **Joint-account interaction (v1):** Luka auto-creates `transaction_splits` rows for joint-account transactions. Tagging such a transaction to a trip therefore returns **409 `joint_account_dual_split_not_supported`** with a user-facing message: *"Esta transacción está en una cuenta conjunta. La división conjunta + viaje aún no está disponible."* Dual-split (household + trip on the same transaction) is explicitly v2.
- **Settlement linkage:** a `transactions` row linked to a `trip_settlements` row is *not* a "trip expense" — settlements never enter `trip_expenses` and therefore do not trigger mutual exclusivity. Their amount is also excluded from any user's category/budget totals (settlement transactions are flagged on the user's side via `trip_settlements.transaction_id`; the budget aggregator filters them out).

### 3.9 Invariants (app-enforced, validated at write)

- **Split sum equals expense amount, exactly.** When the user picks `equal` mode, the server divides `amount` by `n` attendees and assigns `floor(amount / n)` to each, with the **payer absorbing the remainder cents** (deterministic, single-rule). The persisted `share_amount` values therefore sum to `amount` to the cent — no ε tolerance for the sum (validation rejects mismatches outright). For `custom_amount` and `custom_percent` modes, the server normalizes percentages to amounts and again forces the payer to absorb any residual.
- The expense's `payer_attendee_id` must belong to the same `trip_id`.
- All split `attendee_id`s must belong to the expense's `trip_id`. Splits **may** include attendees with `left_at IS NOT NULL` *only* for historical edits — new expenses can only split among currently active attendees (`left_at IS NULL`). Historical splits referencing left attendees remain valid forever.
- An expense with `transaction_id` set: the caller must have RLS read access to the transaction (covers solo-owned and joint-account-shared transactions); the transaction must not already have a non-deleted `trip_expenses` link; if the transaction has any `transaction_splits` rows, the create is rejected (see §3.8 joint-account handling).
- **Removing an attendee with unsettled balances:** blocked by default (returns 409). Two escapes:
  1. Settle (any direction) until net is within ±$0.50 in trip base currency, then remove succeeds (small FX-drift tolerance).
  2. Creator-only **"force-remove with write-off"** action: discards their outstanding balance via an automatic `trip_settlements` zeroing entry tagged `write_off=true`. Logged for audit.
- **Settlement amount > 0 and `from ≠ to`** (DB CHECKs).
- **Sign conventions:** `trip_expenses.amount`, `trip_expense_splits.share_amount`, and `trip_settlements.amount` are all **positive numerics**. Luka's negative-expense convention applies only to `transactions`. The trip ledger uses positive amounts uniformly because directionality is conveyed by `payer_attendee_id` / `from_attendee_id`+`to_attendee_id`.

### 3.10 RLS

- Enable RLS on all six new tables (`trip_*`).
- **Membership predicate:** `is_trip_member(trip_id, user_id)` is a `SECURITY DEFINER` SQL function returning true when there is a `trip_attendees` row with the given `(trip_id, user_id)` regardless of `left_at`. **Left members retain read access to history** (they were part of it). Write paths additionally check `left_at IS NULL` at the application layer — RLS does not need to enforce this since writes are gated by application invariants and the unique constraint on attendees prevents re-insert collisions.
- `trip_attendees` SELECT: members (including left) can see all attendees. INSERT: members. DELETE/UPDATE (setting `left_at`): creator for arbitrary attendees; any member to set `left_at` on their own row.
- `trips` SELECT: members. UPDATE/DELETE: creator-only.
- `trip_expenses` / `trip_expense_splits` / `trip_settlements`: members read all; **only currently-active members** (`left_at IS NULL`) can INSERT/UPDATE/DELETE — enforced as a predicate `is_active_trip_member(trip_id, user_id)`.
- `trip_suggestion_dismissals` / `trip_settlement_dismissals`: per-user — only the row owner can read/write.
- Externals (no `user_id`) are invisible to RLS; they exist as data only.

### 3.11 Wording reconciliation

§4.1 `GET /trips` returns trips where the caller is **currently active** (`left_at IS NULL`) for the list view. The detail endpoint `GET /trips/{id}` is accessible to any member including left ones, so they can audit their historical involvement. This makes "active attendee" (list) and "member" (detail) two distinct concepts; the API uses the former, RLS uses the latter.

---

## 4. API

All endpoints under `/api/trips`, FastAPI router, async SQLAlchemy. Auth via existing Supabase JWT middleware. Response shape conventions match `/household` and `/subscriptions`.

### 4.1 Trips

- `GET /trips?status=active|archived|all` — list trips where the caller is an active attendee. Server groups into `active` (today ∈ [start, end]) / `upcoming` / `past`. Each item includes caller's net balance in trip base currency.
- `POST /trips` — body: `{name, start_date, end_date, base_currency, attendees: [{email|phone|display_name}]}`. Creator auto-added as Luka attendee. Attendees provided by email/phone are resolved to Luka users; non-matches become external stubs with the provided `display_name` (or a fallback derived from the email local-part).
- `GET /trips/{id}` — full detail: trip, attendees, expenses (with splits), settlements, computed balances + smart-settle plan.
- `PATCH /trips/{id}` — name / dates / base_currency. **Creator-only.** **Base-currency change is a re-anchor, not a historical rewrite:** the server multiplies each row's existing `fx_rate_to_base` by the cross-rate `(old_base → new_base)` taken at the moment of change, so internal ratios between expenses and settlements are preserved exactly. This means a previously-zeroed balance stays zeroed under the new base. The cross-rate used is logged in `trip_base_currency_changes (trip_id, old_currency, new_currency, cross_rate, changed_at, changed_by)` for audit.
- `DELETE /trips/{id}` — sets `status = archived`. **Creator-only.**

### 4.2 Attendees

- `POST /trips/{id}/attendees` — body: `{email?, phone?, display_name?}`. If email/phone matches a Luka user, adds them as Luka attendee. Otherwise creates external stub.
- `DELETE /trips/{id}/attendees/{attendee_id}` — sets `left_at`. **Creator-only**, *unless* `attendee_id` resolves to the caller (self-leave). Blocked with 409 if net balance > $0.50 in base currency. To bypass, creator can call `POST /trips/{id}/attendees/{attendee_id}/force-remove` which writes a zeroing `trip_settlements` row tagged `write_off=true` and then sets `left_at`.

### 4.3 Invite link

- `POST /trips/{id}/invite-link` — generate or rotate. Returns `{token, url, expires_at}` exactly once (token never readable again). Tokens are ≥128-bit (`secrets.token_urlsafe(32)` → 256 bits). Any Luka attendee can call (rotation invalidates the previous token by overwriting the hash).
- `DELETE /trips/{id}/invite-link` — revoke (sets `invite_token_hash` NULL).
- `POST /trips/join/{token}` — accept invite. Server hashes the supplied token and looks up the trip. Adds caller as Luka attendee if not already. Refreshes expiry. **Rate-limited:** 10 attempts/min/IP, 30 attempts/hour/user, with exponential backoff on misses to defeat token guessing.
- `GET /trips/preview/{token}` — auth-required preview returning trip name, dates, attendee count. Same rate-limit envelope as join.

### 4.4 Expenses

- `POST /trips/{id}/expenses` — body: `{payer_attendee_id, description, amount, currency, expense_date, transaction_id?, splits: [{attendee_id, share_amount, share_type}]}`. Server validates: sum of shares = amount (±0.01); transaction ownership; mutual exclusivity with `transaction_splits`; FX rate fetched/stored if currency ≠ base.
- `PATCH /trips/{id}/expenses/{expense_id}` — partial update of any field (any active Luka attendee). Requires `If-Match: <version>` header; server compares against the row's current `version`, increments on success, returns 409 on mismatch with the conflicting state. Re-validates all invariants on every PATCH.
- `DELETE /trips/{id}/expenses/{expense_id}` — soft-delete (sets `deleted_at`). Recomputes balances on read.

### 4.5 Settlements

- `POST /trips/{id}/settlements` — body: `{from_attendee_id, to_attendee_id, amount, currency, transaction_id?}`. Either party can record (any Luka attendee).
- `GET /trips/{id}/settle-suggestions` — returns smart-settle plan (minimum-transaction reduction) in trip base currency.

### 4.6 Suggestions inbox

- `GET /trips/{id}/suggested-transactions` — caller's own transactions where:
  - `transaction_date BETWEEN trip.start_date AND trip.end_date`,
  - `type = 'expense'`,
  - not linked to any `trip_expenses` (where not soft-deleted),
  - not in `trip_suggestion_dismissals` for this `(user, trip)`,
  - not a subscription (`subscription_id IS NULL`),
  - not an internal transfer.
- `POST /trips/{id}/suggested-transactions/{transaction_id}/dismiss` — adds to dismissals.
- `DELETE /trips/{id}/suggested-transactions/{transaction_id}/dismiss` — undoes a dismissal (transaction reappears in the inbox if it still meets the in-window criteria).

### 4.7 Settlement auto-detect

Hooked into existing post-insert pipeline on `transactions`. A transaction is a settlement candidate when **all** of:
- `type ∈ {expense, income}`.
- Counterparty (cleaned merchant name + person-detection) matches a Luka attendee on a trip the user is on, with non-zero net balance with that attendee.
- `transaction_date BETWEEN trip.start_date AND (trip.end_date + 30 days)`.
- `|amount − outstanding_balance|` ≤ **`min(5%, $5 in trip base currency)`** (after FX conversion to transaction currency). Tighter than the original 10% to avoid silent over/under-payments. Anything outside this window is shown as a "possible settlement, please confirm amount" rather than an auto-suggest.
- Not in `trip_settlement_dismissals` for that `(user, transaction)`.

Match action: writes a `notification` row of type `trip_settlement_suggestion` with trip + attendee + transaction context. UI surfaces it on the trip's Saldos tab and the global notifications inbox.

User actions:
- Confirm → `POST /trips/{id}/settlements` with `transaction_id` set.
- Dismiss → `POST /trips/settlement-suggestions/dismiss` with `transaction_id`.

### 4.8 Errors

- 409 on duplicate transaction link (returns existing trip name).
- 409 on attempting to remove attendee with unsettled balances (returns balance summary).
- 422 on split-sum mismatch (returns expected vs. actual sum).
- 403 on creator-only actions performed by non-creator.

---

## 5. Balance Computation

Server-side, in trip `base_currency`, recomputed on every read of `GET /trips/{id}` and `GET /trips/{id}/settle-suggestions`. Cached per-trip with a 30-second TTL keyed off `(trip_id, max(updated_at) across trip_*)` if observed cost becomes a concern; v1 ships uncached.

### 5.1 Algorithm

1. Fetch all non-deleted `trip_expenses` + their splits + all `trip_settlements`.
2. For each expense:
   - `paid_in_base = amount × fx_rate_to_base` (or `amount` if currency = base).
   - For each split: `share_in_base = share_amount × fx_rate_to_base`.
3. `attendee_net = Σ paid_in_base − Σ share_in_base` per attendee.
4. Apply settlements: `attendee_net[from] += amount_in_base`, `attendee_net[to] -= amount_in_base` (debtor's debt reduces; creditor's credit reduces).
5. Smart-settle plan (minimum-transaction reduction):
   - Sort attendees by `attendee_net` ascending.
   - While any `|net| > 0.01`:
     - Largest creditor (max net) and largest debtor (min net).
     - Emit transfer `min(|creditor|, |debtor|)` from debtor → creditor.
     - Reduce both; remove zeros.
   - Result: ≤ n−1 transfers for n attendees.

### 5.2 FX rate sourcing

- **Reuse** the existing FX service (powers Plaid + email parser).
- On expense create:
  - If linked transaction has a stored FX rate → use it.
  - Else → fetch the day's `currency → base_currency` rate, store on row.
  - Once stored, **never re-fetched** (rates frozen for stability).
- On manual stub create: fetch + store at creation.
- On trip `base_currency` change: recompute and overwrite all `fx_rate_to_base` in a single DB transaction (creator-only, idempotent).

### 5.3 Budget / category integration

A user's category totals already pull split shares for household-shared transactions. Trip extension:

- When a transaction has a linked `trip_expenses`, the user's contribution to category totals = the `share_amount` from `trip_expense_splits` for the row where the split's `attendee_id` resolves to that user's Luka identity on the trip.
- If a user has no split row on the linked trip expense (e.g., they paid for someone else and were excluded from the split), their personal category contribution is zero — the receivable is the entirety.
- Mutual exclusivity (Section 3.8): a transaction with a trip-expense link cannot have `transaction_splits` rows. Database trigger enforces.

---

## 6. Frontend

Stack: Next.js 16 App Router, React 19, Tailwind 4, shadcn/ui, Zustand 5 (per-trip ephemeral UI state), TanStack Query 5 (server state). Patterns mirror `/transactions` and `/household`.

### 6.1 Routes

```
app/(dashboard)/viajes/
  page.tsx                       # list
  [id]/page.tsx                  # detail with tabs
  join/[token]/page.tsx          # invite landing
  components/
    TripCard.tsx
    TripList.tsx
    TripHeader.tsx
    AddExpenseSheet.tsx
    ExpenseRow.tsx
    BalanceGrid.tsx
    SettleSuggestionList.tsx
    AttendeePicker.tsx
    AttendeeManager.tsx
    TripSuggestionsBanner.tsx
    ShareInviteDialog.tsx
    EmptyState.tsx
```

### 6.2 Navigation

- Sidebar (desktop) + bottom tab bar (mobile): add **Viajes** between *Suscripciones* and *Hogar*.
- Icon: `Plane` (lucide).

### 6.3 Trip list (`/viajes`)

- Sections: **Activos** (today ∈ window), **Próximos**, **Pasados**.
- Each card: name, dates, attendee avatars (max 4 + "+N"), trip total, caller's net balance with directional color (green = owed to you, red = you owe).
- CTA: `+ Nuevo viaje` → modal with name / dates / base currency / initial attendees.
- Empty state: simple "No tienes viajes todavía" + CTA.

### 6.4 Trip detail (`/viajes/[id]`)

Tabs: **Resumen | Gastos | Saldos | Asistentes**.

- **Resumen**: total spent (base currency), your share, your net balance, top 3 settlement suggestions, button to view full plan.
- **Gastos**: chronological list with filters (attendee, category, "only mine"). `ExpenseRow` shows description, payer avatar, amount in base currency, original currency in subtext if different, category chip. Tap row → expense detail sheet (edit/delete).
- **Saldos**: per-attendee balance grid + smart-settle plan + auto-detected settlement suggestions banner.
- **Asistentes**: list with role indicator (creator badge), add/remove (creator-only), invite-link panel with copy-to-clipboard, leave-trip button (self).

### 6.5 Add expense sheet

Bottom sheet (mobile) / dialog (desktop). Fields:

- Description, amount + currency picker (default = trip base currency), expense date.
- Payer dropdown (default = caller).
- "Vincular a transacción" picker — searches caller's untagged transactions in the trip date window. Hidden when payer ≠ caller. This is the manual tagging path.
- Split mode toggle: `Igual / Por monto / Por porcentaje`.
- Attendee chips (default all selected, multi-toggle).
- For custom modes: per-attendee numeric inputs with live sum validation (red border + helper text on mismatch).
- Category picker (optional; prefilled from linked transaction).

### 6.6 Suggestions inbox

- Banner inside `Resumen` and `Gastos` tabs: "N transacciones durante este viaje no agregadas". Expands inline to a list with three actions per row: `Agregar (división igual)`, `Personalizar`, `Descartar`.
- Inline chips on `/transactions` rows: when a row falls in any active trip's window, show `+ Agregar a [Trip name]` chip. Clicking opens the AddExpenseSheet pre-filled.

### 6.7 Settlement actions

- Each pair in the smart-settle plan has a row with `Marcar como pagado`. If a candidate Zelle/Venmo transaction exists, a `Auto-detectado` chip appears with a one-tap confirm.
- Manual settle dialog: amount, currency, date, optional "linked to transaction" picker.

### 6.8 Currency

- Always trip base currency in headers/totals/balances.
- Original currency shown in subtext on individual expense rows when different.
- No per-user toggle.

### 6.9 Mobile-first details

- All sheets bottom-sheet on mobile, dialogs on desktop (existing `Sheet`/`Dialog` pattern).
- Swipe-to-delete on `ExpenseRow`.
- Sticky bottom CTA on Trip Detail: `+ Agregar gasto`.

### 6.10 Data fetching

- `useTrips()` — list, 5min stale.
- `useTrip(id)` — detail; invalidated on any mutation.
- `useSuggestedTransactions(tripId)` — invalidated on add/dismiss.
- All mutations optimistic with rollback.

### 6.11 Empty state walkthrough

- Skipped for v1. Just list-empty copy.

---

## 7. Auto-detect & suggestions logic

See §4.6 (suggestions inbox) and §4.7 (settlement auto-detect). Both reuse existing post-insert hooks; suggestions are computed on demand for v1 (small N per user, indexed query). If observability shows the query is hot, a materialized `trip_suggestions` table is the v2 optimization.

---

## 8. Migrations & Rollout

### 8.1 Alembic migrations

1. `create_trips_tables` — seven new tables (`trips`, `trip_attendees`, `trip_expenses`, `trip_expense_splits`, `trip_settlements`, `trip_suggestion_dismissals`, `trip_settlement_dismissals`, `trip_base_currency_changes`), indexes, RLS enable, `is_trip_member` + `is_active_trip_member` SECURITY DEFINER functions, RLS policies, mutual-exclusivity triggers (both directions).
2. (Bundled in #1) — `invite_token_hash` unique index, `transaction_id` unique partial index on `trip_expenses` (where `deleted_at IS NULL`), attendee `(trip_id, user_id)` partial unique, all CHECKs.

### 8.2 Feature flag

`feature_trips_enabled` (per-user). Default off. Rollout phases:

1. Backend + migrations + tests deployed dark.
2. Frontend section deployed, flag off.
3. Founders enabled; dogfood on a real trip.
4. Beta cohort.
5. Broad rollout.

### 8.3 Backwards compatibility

All-additive. The only retroactive change to existing logic is the mutual-exclusivity trigger on `transaction_splits`, which only fires for transactions that get tagged to a trip — zero impact on existing data.

### 8.4 Observability

- Metrics: trips created/week, attendees/trip distribution, expenses/trip, % expenses backed by real transactions, suggestion accept vs. dismiss rates, settlement auto-confirm vs. manual rate, average days to first settlement.
- Errors via existing Sentry.
- Logs: invite-link generation, redemption, rotation, revoke (security audit trail).

---

## 9. Testing

Per CLAUDE.md: backend uses pytest with `asyncio_mode = auto`, hits real Supabase. Frontend has no test infra in v1.

### 9.1 Backend tests (real DB)

- `test_trips_crud.py` — create, list (active/upcoming/past grouping), update, archive, creator-only enforcement.
- `test_trip_attendees.py` — add by email match, by phone match, name-stub fallback; remove (creator vs. self-leave); blocked-on-unsettled-balance; re-add of left member.
- `test_trip_invite_link.py` — generate, rotate, revoke, expiry, redeem, refresh-on-redeem, idempotent re-join.
- `test_trip_expenses.py` — create with linked transaction, manual stub, sum validation, mutual exclusivity with `transaction_splits`, edit, soft-delete.
- `test_trip_balances.py` — single-currency, multi-currency with FX, smart-settle 3-attendee triangle, 5-attendee ring, exact zeroing within ε, settlements reduce balances. **Plus property-based tests (Hypothesis):** for any randomly generated set of expenses + splits, the smart-settle plan satisfies (a) `Σ transfers across all pairs = 0`, (b) `len(transfers) ≤ n − 1`, (c) applying the plan zeroes every attendee's net balance to ≤ $0.01 in base currency.
- `test_trip_base_currency_change.py` — switching base currency preserves zeroed balances exactly via the cross-rate re-anchor.
- `test_trip_concurrency.py` — concurrent PATCH with stale `If-Match` returns 409; force-remove + write-off zeroes a small unsettled drift.
- `test_trip_invite_security.py` — raw token never returned twice; lookup uses SHA-256; rate-limit triggers after threshold.
- `test_trip_suggestions.py` — in-window query: excludes subscriptions, transfers, already-linked, dismissed; per-user isolation.
- `test_trip_settlement_autodetect.py` — Zelle within tolerance + window matches; outside window does not; dismissed suppresses; externals never matched.
- `test_trips_rls.py` — non-member cannot read; removed member retains read on history but cannot write to future expenses; externals have no auth identity.
- `test_budget_integration.py` — trip-linked transaction contributes only the user's `share_amount` to category/budget totals; user with no split contributes zero.

Coverage target: ≥90% on new modules.

### 9.2 Frontend verification

`/browser-use` golden-path script:
1. Create trip with 2 Luka users + 1 external.
2. Add 3 expenses (one paid by external as a stub).
3. Confirm balances reconcile.
4. Settle one pair manually.
5. Link a real transaction via the suggestions banner.
6. Generate invite link; accept on a second account; confirm new attendee shows up.
7. Currency display: create expense in non-base currency; verify display shows base.

### 9.3 Frontend test infra

Out of scope for v1. Tracked in `NEXT-STEPS.md` as: *"Set up frontend test infrastructure (Vitest + RTL + Playwright); ~2 days; standardize testing posture across the app, backfill high-risk areas (CategoryPicker, household splits, multi-currency)."*

---

## 10. Documentation Updates (post-implementation)

- `README.md` — add Trips to the feature list and modules section.
- `ARCHITECTURE.md` — new tables, endpoints, balance algorithm, RLS policy, mutual-exclusivity rule, FX freeze convention, smart-settle reduction.
- `NEXT-STEPS.md` — move v2 items here:
  - WhatsApp invites + WhatsApp expense actions + WhatsApp settlement confirmations
  - Native mobile contact-picker integration
  - Itemized splits within a single transaction
  - Recurring trips
  - Receipt photo attachments
  - CSV / PDF export
  - External-attendee → real Luka user merge
  - Dual-split (household + trip on the same transaction)
  - Per-user currency display preference
  - Frontend test infrastructure (Vitest + RTL + Playwright)
- `CLAUDE.md` — add invariants:
  - Trip-tagged transactions and `transaction_splits` are mutually exclusive in v1.
  - Trip-only stubs (`trip_expenses` with `transaction_id IS NULL`) never appear in any user's personal ledger, budget, or category totals.
  - Trip FX rates are frozen at expense-creation time and never re-fetched (except when the trip's base currency is changed).

---

## 11. Open questions / risks

- **Counterparty matching for settlement auto-detect** depends on the existing merchant-cleaning + person-detection layer correctly identifying Zelle/Venmo counterparties. If those names don't resolve to a Luka attendee, the suggestion misses (silent — user can still settle manually). Pre-launch: spot-check person-to-person classification quality on the founder accounts.
- **Trip with attendees in materially different currencies** (CLP vs. USD vs. MXN) — the displayed-base-currency choice means some attendees see numbers far from their daily reality. Mitigation: trip creator picks the most representative currency. If this causes friction in dogfood, lift the v2 per-user view-currency override.
- **Concurrent edits** on the same expense are handled by the `version` column + `If-Match` header (no race window).
- **Trip base currency change** uses a single cross-rate multiplier — internal ratios are preserved exactly, so a previously-zeroed balance stays zeroed under the new base. The audit row in `trip_base_currency_changes` records the cross-rate used.

---

## 12. Out-of-scope confirmation

The following are explicitly **not in v1** and listed here so future contributors don't infer them from the design:

- Dual-split (household + trip simultaneously).
- Trip-only categories (e.g., "lodging," "transport" inside a trip, distinct from user categories).
- Receipt attachments.
- Itemized split.
- WhatsApp anything.
- Native mobile contact picker.
- Recurring trips.
- External → Luka user identity merge.
- Per-user currency display preference.
- Frontend automated test infrastructure.

All listed in NEXT-STEPS.md upon implementation.
