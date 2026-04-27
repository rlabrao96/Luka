# Merchant Classification Card — UX Refresh + Picker Unification + GET Speedup

**Date:** 2026-04-27
**Owner:** Rafael Labra
**Status:** Design proposed — pending user approval
**Related:** `frontend/app/(dashboard)/components/MerchantCard.tsx`, `frontend/app/(dashboard)/components/CategoryBottomSheet.tsx`, `frontend/app/(dashboard)/components/TransactionCard.tsx`, `backend/modules/merchant_review/service.py`, `backend/modules/settings/service.py`

---

## 1. Problem

The merchant review flow (`/transactions/review/[jobId]`) is the surface where users classify newly-imported merchants after a bank sync. Today it has four pain points that the user surfaced:

1. **Category change requires too many taps.** The category pill on the front of `MerchantCard` is decorative — to change it, the user must hit the pencil icon, enter a full edit mode (name field + entire category list + movements), tap the new category, then tap "Guardar". On mobile this is 3+ taps for what should be 1 tap → 1 pick.
2. **No personal/shared classification on the card.** Today the merchant review only sets the category. Split type is implicit (joint accounts → shared, everything else assumed personal). The user wants explicit, editable defaults: default `personal`, switchable to `shared` from the card.
3. **Edit-mode category list is unreadable.** Categories render as flex-wrap pills of varying widths, mixing expense and income with no separation, no ordering signal, and no visual differentiation for LLM suggestions. The user described it as "a mess and very difficult to read."
4. **Review page is slow to render after a bank sync.** When the user taps the notification, the review page takes several seconds to show the first card. The wait is the `GET /merchant-review/{jobId}` endpoint, which today executes 2–4 sequential DB queries per card (N+1).

Plus a separate bug surfaced during brainstorming:

5. **Joint-account `split_type` default is broken.** Per CLAUDE.md, joint bank accounts must auto-classify their transactions as `shared`. The user reports purchases on a joint card are landing as `personal`. The regression is somewhere in transaction creation, not display.

## 2. Goals

- One-tap category change from the merchant card front (no pencil, no save button for the common case).
- Make personal/shared explicit on the merchant card, default `personal`, one-tap toggle, default `shared` for joint accounts.
- Replace the current edit-mode category list with a structured, scannable picker: LLM suggestions on top, then expense/income sections, alphabetical, 3-column icon-tile grid.
- Reuse a single category picker component across merchant card front, merchant card edit mode, and the transactions row category tap. Same UX everywhere.
- Harmonize pill colors across the merchant review surface and the transactions page (gray category, blue Personal, emerald Shared).
- Cut `GET /merchant-review/{jobId}` latency by eliminating per-card N+1 queries.
- Fix the joint-account default at the source.

## 3. Non-goals

- Backend LLM batching or progressive notification creation. The user confirmed the wait between bank sync and notification is acceptable. Only the post-tap render is in scope.
- Frontend pagination or virtualization for the review page. Only attempted if the N+1 fix isn't enough.
- Settings → Categories management redesign. Out of scope.
- New icon set. Reuse `getCategoryIconOrInitial` and existing emoji mapping.
- WhatsApp / income-flow LLM behavior changes. Out of scope.
- Changes to the canonical-merchant model or LLM grouping logic.

## 4. Design overview

### 4.1 Pill palette (unified across surfaces)

| Pill | Background | Foreground | Used in |
|------|------------|------------|---------|
| Category | `bg-slate-100` | `text-slate-600` | MerchantCard front, MerchantCard edit, TransactionCard |
| Split = Personal | `bg-blue-50` | `text-blue-600` | MerchantCard front, TransactionCard |
| Split = Shared | `bg-emerald-50` | `text-emerald-600` | MerchantCard front, TransactionCard |
| Suggested category (in picker only) | `bg-amber-50` over a `linear-gradient(135deg,#FEF3C7,#FFFBEB)` framed card with `border-amber-200` | `text-amber-800` | CategoryPicker only |

`MerchantCard` today uses `bg-blue-50 text-luka-primary` for the category pill. Switch it to gray to match `TransactionCard` and reserve blue for the Personal split pill. `TransactionCard` already uses these split colors (`bg-blue-50 text-blue-600` / `bg-emerald-50 text-emerald-600`); the only change there is the category pill style remains gray (no change needed) and the existing split/category tap surfaces stay intact.

### 4.2 MerchantCard — front (read-only) state

Layout, top to bottom, centered:

1. Category icon box (existing, unchanged).
2. Merchant display name (existing, unchanged).
3. **Category pill** — gray, tappable. Tapping opens the CategoryPicker.
4. **Split pill** — Personal (blue) or Shared (emerald), tappable. Tapping toggles between the two values inline (no modal). Stacked directly below the category pill, same horizontal center.
5. Movements card (existing, unchanged).

Default value of the split pill on a freshly-presented card:

- `shared` if the underlying transactions belong to a joint bank account.
- `personal` otherwise.

(The card represents N transactions for one canonical merchant. They all share an account/joint status because they're the same merchant on the same user's accounts; if mixed, fall back to majority sign of the joint flag.)

The pencil button on the action row continues to open the existing edit mode (name + full picker + movements + Save/Cancel) for the cases where the user wants to rename the merchant or see the full transaction list. The skip and approve buttons are unchanged.

### 4.3 MerchantCard — edit mode

Replace the current flex-wrap of category pills with the new CategoryPicker rendered inline (same component used by the bottom sheet/popover, just embedded). The "Movimientos" card and Cancelar/Guardar buttons stay as they are. Name input stays as it is.

### 4.4 CategoryPicker — new shared component

**Location:** `frontend/app/(dashboard)/components/CategoryPicker.tsx`

**Replaces:** the existing `CategoryBottomSheet.tsx` (delete after migration).

**Interface:**

```ts
interface CategoryPickerProps {
  open: boolean;
  onClose: () => void;
  currentCategory: string | null;
  onSelect: (category: string | null) => void;

  // When provided, renders a "Sugeridas" section at the top.
  // Filtered to drop "Otros" before render.
  suggestions?: string[];

  // Drives section order: positive => Ingresos first; negative or 0 => Gastos first.
  // Both sections always rendered.
  dominantSign?: "positive" | "negative";
}
```

**Rendering shell:**

- Mobile (`<lg`): bottom sheet using existing `BottomSheet` primitive in `components/ui/bottom-sheet`. Title "Categoría". Drag handle visible.
- Desktop (`lg+`): anchored popover next to the trigger element. Implement with Radix `Popover` (already in shadcn dep set) or a small custom anchored portal — pick whichever the codebase already uses. Whichever we use, the merchant card edit-mode embed renders the picker body inline (no popover/sheet shell).

**Body, in order:**

1. **Sugeridas card** (only when `suggestions` non-empty after filtering "Otros"):
   - Amber-framed container (gradient bg, amber-200 border, rounded-xl).
   - Section label `✨ Sugeridas` in amber-800, uppercase, tracking-wider, 10–11px.
   - Suggestion pills inside the card: white pill, amber-200 border, amber-800 text. Selected state: amber-600 background, white text.
2. **Section A** (Gastos or Ingresos depending on `dominantSign`):
   - Section label `Gastos` / `Ingresos` in slate-600, uppercase, tracking-wider.
   - 3-column icon-tile grid (`grid-cols-3 gap-1.5`).
   - Tile: `bg-slate-50 border border-slate-100 rounded-lg p-2.5`, vertical stack of (icon box, label). Icon box `w-7 h-7 bg-white rounded-md`. Label two-line clamp, 10px, slate-600 medium.
   - Selected tile: `bg-luka-primary border-luka-primary`, label white.
3. **Section B** (the other of Gastos/Ingresos): same grid as A.

**Sorting:**

- Both sections: alphabetical by display name (locale-aware compare for accents — `Spanish` collation via `Intl.Collator('es')`).
- Suggestions retain LLM-provided order (already a ranked list).

**Section order rule:** `dominantSign === "positive"` → Ingresos first, Gastos below. Otherwise (negative or zero/missing) → Gastos first, Ingresos below. Both always rendered so reimbursements and mixed-sign merchants remain reachable.

**Data:**

- Reuse `useCategories()` hook output, which already returns `{ expense, income }` arrays from the user's preferences (backed by `_DEFAULT_CATEGORIES` in `backend/modules/settings/service.py` plus user customizations).
- Suggestions come from the caller (e.g., `card.llm_suggested_categories` on merchant card; `undefined` on transactions row).
- "Sin categoría" stays available — render as a muted clear-selection row at the very top of the body (above the Sugeridas card), only when `currentCategory` is non-null. Tapping it calls `onSelect(null)` and closes.

### 4.5 Personal/Shared toggle on the card front

Tapping the split pill flips between `personal` and `shared` and persists the choice. Persistence path:

- The merchant review flow operates on `CanonicalMerchant`, not on individual transactions. The split-type decision the user makes on the card needs to apply to all transactions linked to the canonical (the existing `approve_merchant` flow already does this for category — same scope for split type).
- Add an optional `split_type` parameter on `POST /merchant-review/{jobId}/merchants/{canonicalId}`. When present and `action="approve"`, server applies it to all linked transactions in the same way category is applied.
- For joint-account transactions: default is `shared`, but the pill is fully editable to `personal` if the user explicitly wants it (e.g., a personal expense paid from the joint card). The server respects whatever value the user picks. The "joint → auto-shared" rule only sets the default at creation time; user overrides win.

### 4.6 TransactionCard pill harmonization

Already uses the right colors per the audit:
- `personal` → `bg-blue-50 text-blue-600`
- `shared` → `bg-emerald-50 text-emerald-600`
- category → `bg-slate-100 text-slate-600`

No structural changes needed. Verify pill height/radius consistency with the new MerchantCard pills (5px vertical padding, `rounded-full` for emphasis pills on cards vs `rounded` for compact row pills — the difference is intentional and stays).

### 4.7 Joint-account default bug fix

Investigate where transactions on joint accounts are landing with `split_type='personal'`. Likely culprits, in order:

1. Bank sync ingestion path (Plaid / bank-connect / email) — does it look up the bank account and set `split_type` on insert?
2. Merchant review approval — when `approve_merchant` writes the category to linked transactions, does it touch `split_type`?
3. Transaction creation default in the model itself.

The user reports purchases on the shared card landing as personal, which most strongly suggests the ingestion paths are not honoring the joint flag. Concrete change: at every transaction creation site (bank sync, email parse, manual entry), look up `bank_accounts.account_type` and set `split_type='shared'` when joint, else `personal`. Add a backfill migration that updates existing wrongly-classified rows.

### 4.8 GET /merchant-review/{jobId} N+1 elimination

Current implementation in `backend/modules/merchant_review/service.py:67–194` runs:

- 1 query for canonical rows.
- For each canonical: 1 stats query (count + sum), optionally 1 fallback stats query, 1 transactions list query, 1 LLM-suggestions query on the linked merchant.

For ~20 merchants this is 60–80 sequential roundtrips. Refactor to:

1. **One query** for canonicals + raw_names (existing first query, unchanged).
2. **One query** for transaction stats grouped by `raw_merchant_name`: returns `(raw_name, count, sum, currency)`. Then map back to canonicals via the `raw_names` arrays we already have. The fallback path becomes a second pass on the same query result, no extra roundtrip.
3. **One query** for the transactions list, ordered by date desc, with a `LIMIT` per canonical via window function. Wrap `ROW_NUMBER() OVER (PARTITION BY raw_merchant_name ORDER BY transaction_date DESC)` in a subquery (window functions can't appear in `WHERE`) and filter `rn <= 25` in the outer query — keep the most recent 25 per merchant for the UI list. Group result back by canonical in Python.
4. **One query** for LLM suggestions: `SELECT raw_name, llm_suggested_categories FROM merchants WHERE raw_name IN (...)`. Index the join on the array we already have.

End state: 4 queries total regardless of card count. Expected response time on a 20-card payload drops from multi-second to sub-500ms (most rows being trivial counts).

If the response is still perceptibly slow after the refactor, add `?limit=N&offset=M` and load 3 first, then the rest. This is conditional on measurement, not committed up front.

## 5. Components touched

### Frontend

- **Edit:** `MerchantCard.tsx` — front layout (split pill added, category pill becomes a button), edit mode embeds CategoryPicker.
- **New:** `CategoryPicker.tsx` — described in §4.4.
- **Delete:** `CategoryBottomSheet.tsx` — replaced by `CategoryPicker`. Update all importers (transactions page row tap, anywhere else it's used).
- **No structural change:** `TransactionCard.tsx` — colors already align; verify visually.
- **Edit:** `transactions/review/[jobId]/page.tsx` — pass `dominantSign` and `suggestions` to `MerchantCard`/`CategoryPicker` as appropriate.
- **Edit:** `app/lib/api.ts` and `useMerchantReview.ts` — extend `approveMerchant` API call to include `split_type`.

### Backend

- **Edit:** `backend/modules/merchant_review/service.py` — `get_review_cards` rewrite for batched queries; `approve_merchant` accepts `split_type` and applies to linked transactions (with joint-account override).
- **Edit:** `backend/modules/merchant_review/schemas.py` — add `split_type` to the approve request schema.
- **Edit:** transaction creation paths (bank sync, email parser, Plaid ingestion) — look up `bank_accounts.account_type` and set `split_type` correctly. Specific files identified during planning.
- **New:** Alembic migration — backfill `transactions.split_type='shared'` for any row whose `bank_account_id` points to a joint account. Idempotent; safe to re-run.

## 6. Data flow

### Tap category pill on MerchantCard front

1. User taps gray category pill.
2. CategoryPicker opens (mobile sheet / desktop popover) with:
   - `currentCategory` = current selected category on the card.
   - `suggestions` = `card.llm_suggested_categories` (filtered to drop "Otros").
   - `dominantSign` = sign of the sum of `card.transactions` amounts.
3. User taps a tile or suggestion pill.
4. `onSelect` fires → MerchantCard updates local state, picker closes.
5. User then taps the green Approve button → `approveMerchant({ category, split_type, display_name })` posts. (Same as today; no new auto-save.)

### Tap split pill on MerchantCard front

1. User taps the Personal/Shared pill.
2. Local state flips. Visual update is immediate.
3. On Approve, `split_type` posts with the rest.
4. If the account is joint, server enforces `shared` regardless.

### Tap category pill on TransactionCard

Existing flow: `onCategoryTap` opens the picker. After this work, the picker is the new `CategoryPicker` (not `CategoryBottomSheet`). `suggestions` is `undefined` here — the Sugeridas section is hidden. `dominantSign` derived from the row's amount.

## 7. Error handling

- CategoryPicker render: if `useCategories()` returns empty (new user before defaults seed), render an empty-state message in each section. No crash.
- Approve with missing category: existing behavior — server falls back to canonical's `default_category`. No change.
- Joint-account split-type override: server returns the corrected row; client trusts the response.
- Slow GET: with batched queries the failure mode becomes a single failed query rather than partial cards. Existing `isLoading` UX covers it.
- Backfill migration: dry-run mode for inspection, then transactional update. If it fails, rolls back; no partial updates.

## 8. Testing

### Backend (pytest, real DB per CLAUDE.md)

- `test_get_review_cards_batched.py` — verify a multi-canonical job returns equivalent payload to the old implementation, including transaction counts, totals, currency, LLM suggestions. Compare query count (use SQLAlchemy event listener) — assert ≤4 queries regardless of N cards.
- `test_approve_merchant_split_type.py` — approve with `split_type='shared'` on a non-joint account; verify all linked transactions update. Approve with `split_type='personal'` on a joint account; verify the user override wins (rows persist as `personal`).
- `test_joint_account_default.py` — ingest a transaction on a joint account via each entry path (bank sync, email, Plaid); verify `split_type='shared'`. Same on personal account → `personal`.
- Migration test — seed mixed accounts, run backfill, assert the joint-account rows get corrected and personal-account rows are untouched.

### Frontend

No unit tests (no infra per CLAUDE.md). Manual verification via `/browser-use`:
- Tap category pill on merchant card front → picker opens with suggestions visible.
- Tap suggestion → pill updates, picker closes.
- Tap split pill → toggles Personal ↔ Shared.
- Approve → both values persist (verify via transactions page).
- Pencil button → edit mode opens with embedded picker, name editable, Save works.
- Transactions row category tap → same picker (no Sugeridas section), section order matches sign.
- Test on mobile viewport (bottom sheet) and desktop (popover).
- Sync a fresh bank account, time the wait between tapping the notification and seeing the first card. Confirm <1s.

## 9. Migration

- The old `CategoryBottomSheet.tsx` is deleted after `CategoryPicker` is in place. Single-shot migration in one commit since it's a frontend-only swap.
- The Alembic migration for `split_type` backfill runs once on deploy. It's data-only — no schema change.
- No feature flag. The new picker is strictly better; rollback is git revert.

## 10. Open questions

All resolved during brainstorm. Recorded for traceability:

1. **Joint-account split tap UX:** Resolved — pill is fully editable both ways; the joint rule only sets the default, user overrides win (see §4.5).
2. **"Sin categoría" surfacing:** Resolved — render it as a clear-selection row at the top of the picker body, only when `currentCategory` is non-null. Matches the existing `CategoryBottomSheet` behavior the picker is replacing.
3. **Pagination fallback:** Resolved — strictly out of scope. Measurement-driven follow-up only if post-fix latency is still poor.
