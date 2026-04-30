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
| invite_token | text | Random opaque token. Indexed unique. Nullable. |
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
| amount | numeric(14,2) | Always positive. Sign convention applied at consumption. |
| currency | char(3) | |
| expense_date | date | |
| transaction_id | uuid FK transactions(id) | NULL = manual stub. |
| fx_rate_to_base | numeric(20,10) | Multiplier from `currency` to trip `base_currency`. NULL when `currency = base_currency`. |
| created_by_user_id | uuid FK users(id) | |
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
| share_amount | numeric(14,2) | In expense's currency. Sum across rows must equal expense.amount (validated at write). |
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
| amount | numeric(14,2) | |
| currency | char(3) | |
| fx_rate_to_base | numeric(20,10) | NULL if `currency = base_currency`. |
| settled_at | timestamptz | |
| transaction_id | uuid FK transactions(id) | NULL = marked manually; set when auto-matched to Zelle/Venmo. |
| created_by_user_id | uuid FK users(id) | |
| created_at | timestamptz | |

### 3.6 `trip_suggestion_dismissals`
| user_id, trip_id, transaction_id, dismissed_at |
PK `(user_id, trip_id, transaction_id)`. Suppresses an in-window transaction from re-appearing in the suggestions inbox.

### 3.7 `trip_settlement_dismissals`
| user_id, transaction_id, dismissed_at |
PK `(user_id, transaction_id)`. Suppresses an auto-detected settlement suggestion from re-firing.

### 3.8 Reused tables — additive constraint

- **`transactions`** — no schema change.
- **`transaction_splits`** — add a CHECK or trigger preventing rows where the same `transaction_id` appears in `trip_expenses` (mutual exclusivity). Implementation: a `BEFORE INSERT/UPDATE` trigger on `transaction_splits` raising on conflict, plus the symmetric trigger on `trip_expenses`.

### 3.9 Invariants (app-enforced, validated at write)

- Sum of `trip_expense_splits.share_amount` for an expense = `trip_expenses.amount`, within ε = 0.01.
- The expense's `payer_attendee_id` must belong to the same `trip_id`.
- All split `attendee_id`s must belong to the expense's `trip_id` and have `left_at IS NULL` at the time of the expense's creation (historical splits remain valid even after a member leaves).
- An expense with `transaction_id` set: the underlying transaction must be owned by the `created_by_user_id`, and the transaction must not already have `transaction_splits` rows.
- A user cannot be removed from a trip while they have unsettled balances; they must settle first or have their expenses reassigned.

### 3.10 RLS

- Enable RLS on all six new tables (`trip_*`).
- Membership predicate, parameterized: `auth.uid() IN (SELECT user_id FROM trip_attendees WHERE trip_id = <row.trip_id> AND user_id IS NOT NULL)`. Implemented as a `SECURITY DEFINER` SQL function `is_trip_member(trip_id, user_id)` to avoid RLS recursion on `trip_attendees` itself.
- `trip_attendees` SELECT: members can see all attendees of their trip. INSERT/UPDATE/DELETE: members for additive ops; creator-only for removing other members.
- `trips` UPDATE/DELETE: creator-only.
- `trip_expenses` / `trip_expense_splits` / `trip_settlements`: members can read all; members can insert; for edits/soft-delete, any member can edit any expense (per flat permissions).
- `trip_suggestion_dismissals` / `trip_settlement_dismissals`: per-user — only the row owner can read/write their own.
- Externals (no `user_id`) are invisible to RLS; they exist as data only.

---

## 4. API

All endpoints under `/api/trips`, FastAPI router, async SQLAlchemy. Auth via existing Supabase JWT middleware. Response shape conventions match `/household` and `/subscriptions`.

### 4.1 Trips

- `GET /trips?status=active|archived|all` — list trips where the caller is an active attendee. Server groups into `active` (today ∈ [start, end]) / `upcoming` / `past`. Each item includes caller's net balance in trip base currency.
- `POST /trips` — body: `{name, start_date, end_date, base_currency, attendees: [{email|phone|display_name}]}`. Creator auto-added as Luka attendee. Attendees provided by email/phone are resolved to Luka users; non-matches become external stubs with the provided `display_name` (or a fallback derived from the email local-part).
- `GET /trips/{id}` — full detail: trip, attendees, expenses (with splits), settlements, computed balances + smart-settle plan.
- `PATCH /trips/{id}` — name / dates / base_currency. **Creator-only.** If `base_currency` changes, server recomputes `fx_rate_to_base` for every expense and settlement in a single transaction.
- `DELETE /trips/{id}` — sets `status = archived`. **Creator-only.**

### 4.2 Attendees

- `POST /trips/{id}/attendees` — body: `{email?, phone?, display_name?}`. If email/phone matches a Luka user, adds them as Luka attendee. Otherwise creates external stub.
- `DELETE /trips/{id}/attendees/{attendee_id}` — sets `left_at`. **Creator-only**, *unless* `attendee_id` resolves to the caller (self-leave). Blocked with 409 if attendee has unsettled balances.

### 4.3 Invite link

- `POST /trips/{id}/invite-link` — generate or rotate. Returns `{token, url, expires_at}`. Any Luka attendee can call (rotation invalidates the previous token).
- `DELETE /trips/{id}/invite-link` — revoke (sets token NULL).
- `POST /trips/join/{token}` — accept invite. Adds caller as Luka attendee if not already. Refreshes expiry.
- `GET /trips/preview/{token}` — public-ish endpoint (still requires auth) returning trip name, dates, attendee count for the join landing page.

### 4.4 Expenses

- `POST /trips/{id}/expenses` — body: `{payer_attendee_id, description, amount, currency, expense_date, transaction_id?, splits: [{attendee_id, share_amount, share_type}]}`. Server validates: sum of shares = amount (±0.01); transaction ownership; mutual exclusivity with `transaction_splits`; FX rate fetched/stored if currency ≠ base.
- `PATCH /trips/{id}/expenses/{expense_id}` — partial update of any field (any Luka attendee). Re-validates invariants. Soft conflict-detection: if a different user has edited it within the last 5 seconds, return 409 with their edit.
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

### 4.7 Settlement auto-detect

Hooked into existing post-insert pipeline on `transactions`. A transaction is a settlement candidate when **all** of:
- `type ∈ {expense, income}`.
- Counterparty (cleaned merchant name + person-detection) matches a Luka attendee on a trip the user is on, with non-zero net balance with that attendee.
- `transaction_date BETWEEN trip.start_date AND (trip.end_date + 30 days)`.
- `|amount − outstanding_balance|` ≤ 10% of outstanding (after FX conversion to transaction currency).
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

1. `create_trips_tables` — six new tables, indexes, RLS enable, `is_trip_member` SECURITY DEFINER function, RLS policies, mutual-exclusivity triggers.
2. (Bundled in #1) — invite-token unique index, transaction-link unique partial index, attendee `(trip_id, user_id)` partial unique.

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
- `test_trip_balances.py` — single-currency, multi-currency with FX, smart-settle 3-attendee triangle, 5-attendee ring, exact zeroing within ε, settlements reduce balances.
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
- **Concurrent edits** on the same expense by two Luka attendees: 5-second soft-conflict window returns 409. If we see this in practice, move to a proper row-version field.
- **Trip base currency change** recomputes FX for every row, which can drift balances slightly if rates moved between original storage and recompute. Documented behavior: a base-currency change is a re-anchor, not a historical rewrite of payments made.

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
