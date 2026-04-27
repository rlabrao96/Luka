# Merchant Card Classification UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the merchant review card with one-tap category + split-type editing, unify the category picker across surfaces, fix the joint-account split default, and cut `GET /merchant-review/{jobId}` latency by eliminating N+1.

**Architecture:** New `CategoryPicker` shared component (mobile bottom sheet / desktop popover) replaces `CategoryBottomSheet` and is reused from MerchantCard front, MerchantCard edit, and TransactionCard. Split-type becomes an editable pill on the merchant card and travels through `approveMerchant`. Backend rewrites `get_review_cards` into batched queries and adds joint-aware defaults at every transaction-creation site, plus an Alembic backfill.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 async / pytest (real DB) / Next.js 16 / React 19 / Tailwind 4 / shadcn-ui / TanStack Query 5.

**Spec:** `docs/superpowers/specs/2026-04-27-merchant-card-classification-ux-design.md`

---

## File Structure

### Backend
- **Modify** `backend/modules/merchant_review/service.py` — rewrite `get_review_cards` (4 batched queries); extend `approve_merchant` to accept `split_type`.
- **Modify** `backend/modules/merchant_review/schemas.py` — add `split_type` field on the approve request.
- **Modify** `backend/modules/merchant_review/router.py` — pass `split_type` through.
- **Modify** `backend/modules/merchant_review/schemas.py` — add `is_joint_account: bool` to the card response (set by Task 9).
- **Modify** `backend/modules/plaid/sync.py:225-231` — pass joint-aware default to `ensure_default_split`.
- **Modify** `backend/modules/bank_connect/router.py:393-397` — pass joint-aware default.
- **Create** `backend/alembic/versions/<rev>_backfill_joint_split_type.py` — backfill `transaction_splits.split_type='shared'` for transactions on joint accounts.
- **Create** `backend/tests/test_merchant_review_get_cards_batched.py`
- **Create** `backend/tests/test_merchant_review_approve_split_type.py`
- **Create** `backend/tests/test_joint_account_split_default.py`

### Frontend
- **Create** `frontend/app/(dashboard)/components/CategoryPicker.tsx` — new shared picker (sheet on mobile, popover on desktop, embeddable inline body).
- **Delete** `frontend/app/(dashboard)/components/CategoryBottomSheet.tsx` — replaced.
- **Modify** `frontend/app/(dashboard)/components/MerchantCard.tsx` — front pills + edit-mode picker integration.
- **Modify** `frontend/app/(dashboard)/transactions/page.tsx` (and any other CategoryBottomSheet importers) — swap to `CategoryPicker`.
- **Modify** `frontend/app/lib/api.ts` — `approveMerchant` accepts optional `split_type`.
- **Modify** `frontend/app/lib/hooks/useMerchantReview.ts` — pass `split_type` through optimistic update.
- **Modify** `frontend/app/(dashboard)/transactions/review/[jobId]/page.tsx` — pass `dominantSign` and route `split_type`.

---

## Conventions

- All backend tests hit a real DB (no mocks) per CLAUDE.md.
- Pytest with `asyncio_mode = auto`. Use existing fixtures from `backend/tests/fixtures/` and `backend/tests/helpers/`.
- Frontend has no test infra. Verification is via `/browser-use` (login as `rafaellabra96@gmail.com`).
- Commit after every task. Push immediately (per user preference).
- Pill palette: category=`bg-slate-100 text-slate-600`, Personal=`bg-blue-50 text-blue-600`, Shared=`bg-emerald-50 text-emerald-600`.

---

## Task 1: Test the joint-account split default bug

**Why first:** Pin down current behavior, reproduce the bug, then fix it (TDD).

**Files:**
- Create: `backend/tests/test_joint_account_split_default.py`

- [ ] **Step 1: Inspect existing test helpers and find ingestion entrypoints**

```bash
ls backend/tests/fixtures backend/tests/helpers
grep -rn "joint\|account_type" backend/tests/helpers backend/tests/fixtures 2>/dev/null | head
# Locate the actual Plaid ingestion function and the bank_connect routine that calls ensure_default_split:
grep -n "ensure_default_split\|^async def\|^def " backend/modules/plaid/sync.py | head -30
grep -n "ensure_default_split\|^async def\|^def " backend/modules/bank_connect/router.py | head -30
```

Identify (a) a fixture that creates a `BankAccount` with `account_type='joint'` (or build one in the test file), and (b) the exact function names you'll call into for Plaid sync and bank_connect ingestion. The plan's example uses `sync_plaid_transactions_for_item` as a placeholder — verify and adjust.

- [ ] **Step 2: Write failing test for Plaid sync path**

```python
# backend/tests/test_joint_account_split_default.py
import pytest
from sqlalchemy import select
from modules.transactions.models import TransactionSplit
# Import whatever Plaid sync entrypoint creates the txn — see modules/plaid/sync.py

async def test_plaid_sync_joint_account_defaults_to_shared(db_session, joint_bank_account, plaid_payload_factory):
    # Arrange: simulate one Plaid txn landing on the joint account
    payload = plaid_payload_factory(account_id=joint_bank_account.plaid_account_id, amount=-50.0, name="Costco")
    # Act: run the sync ingestion path
    await sync_plaid_transactions_for_item(db_session, item=joint_bank_account.plaid_item, payload=payload)
    # Assert: the resulting TransactionSplit has split_type='shared'
    split = (await db_session.execute(
        select(TransactionSplit).join_from(TransactionSplit, ...)
    )).scalar_one()
    assert split.split_type == "shared"
```

(Adapt fixture names to what already exists. If `joint_bank_account` doesn't exist, add it to `backend/tests/fixtures/accounts.py` or a similar location.)

- [ ] **Step 3: Add a parallel test for bank_connect path**

```python
async def test_bank_connect_joint_account_defaults_to_shared(db_session, joint_bank_account, ...):
    # Arrange: create a Transaction matching what bank_connect/router.py produces
    # Act: invoke the routine that calls ensure_default_split (router function or extracted helper)
    # Assert: split_type='shared'
```

- [ ] **Step 4: Run and confirm both tests fail**

```bash
cd backend && uv run pytest tests/test_joint_account_split_default.py -v
```

Expected: both fail (bug present — split_type='personal' instead of 'shared').

- [ ] **Step 5: Commit failing tests**

```bash
git add backend/tests/test_joint_account_split_default.py backend/tests/fixtures
git commit -m "test(joint-account): pin down split_type='shared' default at Plaid + bank_connect entry points"
git push
```

---

## Task 2: Fix joint-account split default at the entry points

**Files:**
- Modify: `backend/modules/plaid/sync.py:225-231`
- Modify: `backend/modules/bank_connect/router.py:393-397`

- [ ] **Step 1: Patch `plaid/sync.py`**

Replace lines 225–231 (the `ensure_default_split(session, new_tx)` call) with a joint-aware default. The bank account is already loaded in the surrounding scope — use it. Example:

```python
from modules.transactions.service import ensure_default_split
is_joint = account.account_type == "joint"  # `account` is the BankAccount in scope
await ensure_default_split(session, new_tx, default_split_type="shared" if is_joint else "personal")
```

If `account` isn't already in scope, look it up by `new_tx.bank_account_id` before this call.

- [ ] **Step 2: Patch `bank_connect/router.py`**

Same change at the matching call site (~line 397). The `txn` already has `bank_account_id`; if the account object isn't in scope, query it once outside the loop.

- [ ] **Step 3: Re-run the Task 1 tests**

```bash
cd backend && uv run pytest tests/test_joint_account_split_default.py -v
```

Expected: PASS.

- [ ] **Step 4: Run the full transactions + reconciliation test suites to catch regressions**

```bash
cd backend && uv run pytest tests/test_transactions.py tests/test_contribution_modes.py tests/test_reconciliation_dedup.py -v
```

Expected: PASS (or any failure must be unrelated to this change — confirm before continuing).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/plaid/sync.py backend/modules/bank_connect/router.py
git commit -m "fix(transactions): default split_type='shared' for joint accounts at Plaid + bank_connect ingestion"
git push
```

---

## Task 3: Backfill migration for existing wrongly-classified rows

**Files:**
- Create: `backend/alembic/versions/<auto-rev>_backfill_joint_split_type.py`

- [ ] **Step 1: Generate migration skeleton**

```bash
cd backend && uv run alembic revision -m "backfill joint split type"
```

Note the generated revision filename.

- [ ] **Step 2: Write the upgrade**

```python
def upgrade() -> None:
    # Set split_type='shared' on every TransactionSplit whose underlying
    # transaction belongs to a joint bank account, where it's currently 'personal'.
    op.execute("""
        UPDATE transaction_splits ts
        SET split_type = 'shared'
        FROM transactions t
        JOIN bank_accounts ba ON ba.id = t.bank_account_id
        WHERE ts.transaction_id = t.id
          AND ba.account_type = 'joint'
          AND ts.split_type = 'personal'
          AND t.transaction_type != 'transfer'
    """)
    # Note: transfers don't get TransactionSplit rows (ensure_default_split skips
    # them), so the transaction_type filter is belt-and-suspenders — preserves
    # invariant if any historic transfer accidentally got a split row.
    # Note: transaction_splits has no `updated_at` column (only created_at).
```

- [ ] **Step 3: Write the downgrade**

```python
def downgrade() -> None:
    # No-op: we cannot tell which rows were originally personal vs shared.
    pass
```

- [ ] **Step 4: Run the migration locally**

```bash
cd backend && uv run alembic upgrade head
```

Expected: succeeds, no errors.

- [ ] **Step 5: Add a migration test**

```python
# backend/tests/test_joint_split_backfill_migration.py
async def test_backfill_corrects_joint_personal_rows(db_session, joint_bank_account, personal_bank_account):
    # Seed: one txn on joint account with split_type='personal' (bug state),
    # one txn on personal account with split_type='personal' (correct).
    # Run the SQL from the migration directly.
    # Assert: joint row -> 'shared'; personal row -> still 'personal'.
```

- [ ] **Step 6: Run the migration test**

```bash
cd backend && uv run pytest tests/test_joint_split_backfill_migration.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions backend/tests/test_joint_split_backfill_migration.py
git commit -m "fix(transactions): backfill split_type='shared' for transactions on joint accounts"
git push
```

---

## Task 4: Test current `get_review_cards` correctness baseline

**Why:** Before refactoring to batched queries, lock down what the endpoint returns so the rewrite preserves it.

**Files:**
- Create: `backend/tests/test_merchant_review_get_cards_batched.py`

- [ ] **Step 1: Write a snapshot-style test**

```python
async def test_get_review_cards_returns_expected_shape(db_session, review_job_with_three_canonicals):
    cards = await get_review_cards(db_session, review_job_with_three_canonicals.id, user_id)
    assert len(cards) == 3
    for c in cards:
        assert {"canonical_merchant_id","display_name","default_category","llm_suggested_categories",
                "transactions","transaction_count","total_amount","currency","is_verified"} <= c.keys()
        assert c["transaction_count"] == len(c["transactions"]) or len(c["transactions"]) == 25  # cap
        assert c["currency"] in ("CLP","USD","COP","MXN","PEN","BRL")
    # Verify totals match the sum of transaction amounts shown
    for c in cards:
        if len(c["transactions"]) == c["transaction_count"]:
            assert c["total_amount"] == pytest.approx(sum(t["amount"] for t in c["transactions"]))
```

- [ ] **Step 2: Add a query-count test using SQLAlchemy event listener**

```python
async def test_get_review_cards_uses_at_most_4_queries(db_session, review_job_with_ten_canonicals):
    queries = []
    @event.listens_for(db_session.sync_session.bind, "before_cursor_execute")
    def collect(conn, cursor, statement, *args, **kwargs):
        queries.append(statement)
    await get_review_cards(db_session, review_job_with_ten_canonicals.id, user_id)
    # Note: this test asserts the post-refactor target. It will fail today (~30+ queries).
    assert len(queries) <= 4, f"Expected ≤4 queries, got {len(queries)}: {queries}"
```

- [ ] **Step 3: Run both**

```bash
cd backend && uv run pytest tests/test_merchant_review_get_cards_batched.py -v
```

Expected: shape test PASSES, query-count test FAILS (today does N+1).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_merchant_review_get_cards_batched.py
git commit -m "test(merchant-review): pin shape and target ≤4 queries for get_review_cards"
git push
```

---

## Task 5: Refactor `get_review_cards` into 4 batched queries

**Files:**
- Modify: `backend/modules/merchant_review/service.py:67-194`

- [ ] **Step 1: Implement the rewrite**

Replace the per-card loop with four batched queries:

1. **Canonicals + raw_names** — keep the existing first query (it returns one row per canonical with `array_agg(Merchant.raw_name)`).
2. **Stats per raw_name** — single query with `FILTER` clauses to fold scoped + unscoped into one pass (preserves the current "scoped first, fallback unscoped per merchant" semantics without a second roundtrip):

   ```sql
   SELECT t.raw_merchant_name, t.currency,
          COUNT(*) FILTER (WHERE :tx_id_uuids IS NULL OR t.id = ANY(:tx_id_uuids)) AS scoped_cnt,
          SUM(t.amount) FILTER (WHERE :tx_id_uuids IS NULL OR t.id = ANY(:tx_id_uuids)) AS scoped_total,
          COUNT(*) AS unscoped_cnt,
          SUM(t.amount) AS unscoped_total
   FROM transactions t
   WHERE t.user_id = :uid
     AND t.raw_merchant_name = ANY(:raw_names)
   GROUP BY t.raw_merchant_name, t.currency
   ```

   In Python, per merchant: use scoped values when `scoped_cnt > 0`, else fall back to unscoped.

3. **Transactions list (top 25 per merchant)** — windowed:

   ```sql
   SELECT raw_merchant_name, transaction_date, amount, currency
   FROM (
     SELECT raw_merchant_name, transaction_date, amount, currency,
            ROW_NUMBER() OVER (PARTITION BY raw_merchant_name
                               ORDER BY transaction_date DESC) AS rn
     FROM transactions
     WHERE user_id = :uid
       AND raw_merchant_name = ANY(:raw_names)
       AND (:tx_id_uuids IS NULL OR id = ANY(:tx_id_uuids))
   ) sub
   WHERE rn <= 25
   ```

   Then group rows by `raw_merchant_name` in Python.

4. **LLM suggestions** — single query: `SELECT raw_name, llm_suggested_categories FROM merchants WHERE raw_name = ANY(:raw_names)`. Build a dict.

Map every canonical row to its aggregated stats / transactions / suggestions in a single Python pass. Preserve the existing payload shape exactly.

- [ ] **Step 2: Run the Task 4 tests**

```bash
cd backend && uv run pytest tests/test_merchant_review_get_cards_batched.py -v
```

Expected: BOTH PASS (shape preserved + ≤4 queries).

- [ ] **Step 3: Run the wider merchant-review suite**

```bash
cd backend && uv run pytest tests/test_merchant_review*.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/modules/merchant_review/service.py
git commit -m "perf(merchant-review): batch get_review_cards into 4 queries (was N+1)"
git push
```

---

## Task 6: `approve_merchant` accepts `split_type`

**Files:**
- Modify: `backend/modules/merchant_review/schemas.py`
- Modify: `backend/modules/merchant_review/service.py` (`approve_merchant`)
- Modify: `backend/modules/merchant_review/router.py`
- Create: `backend/tests/test_merchant_review_approve_split_type.py`

- [ ] **Step 1: Write failing test**

```python
async def test_approve_merchant_applies_split_type_to_linked_transactions(db_session, review_job_personal_account):
    canonical_id = ...  # from fixture
    await approve_merchant(
        db_session, user_id, review_job_personal_account.id, canonical_id,
        display_name=None, category="Alimentación", split_type="shared",
    )
    splits = (await db_session.execute(
        select(TransactionSplit.split_type).join(Transaction).where(...)
    )).scalars().all()
    assert all(s == "shared" for s in splits)


async def test_approve_merchant_split_type_user_override_wins_on_joint(db_session, review_job_joint_account):
    # Default would be 'shared', user picks 'personal' — should persist as personal.
    await approve_merchant(..., split_type="personal")
    assert all(s == "personal" for s in splits)
```

- [ ] **Step 2: Run tests, confirm they fail**

```bash
cd backend && uv run pytest tests/test_merchant_review_approve_split_type.py -v
```

Expected: FAIL — `approve_merchant` doesn't accept `split_type` yet.

- [ ] **Step 3: Add `split_type` to schema**

In `backend/modules/merchant_review/schemas.py`, add to the approve request:

```python
class ApproveMerchantRequest(BaseModel):
    display_name: str | None = None
    category: str | None = None
    split_type: Literal["personal", "shared"] | None = None
```

- [ ] **Step 4: Extend `approve_merchant`**

In `service.py`, accept `split_type: str | None`. After the existing category-application block, when `split_type` is non-None, update `TransactionSplit.split_type` for every transaction linked to this canonical (same scope/`tx_id_uuids` filter as category). Use a single `UPDATE ... WHERE transaction_id IN (SELECT id FROM transactions WHERE ...)`.

- [ ] **Step 5: Plumb through router**

`router.py`: pass `body.split_type` into `service.approve_merchant`.

- [ ] **Step 6: Run tests**

```bash
cd backend && uv run pytest tests/test_merchant_review_approve_split_type.py tests/test_merchant_review*.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/modules/merchant_review
git commit -m "feat(merchant-review): approve accepts split_type and applies it to linked transactions"
git push
```

---

## Task 7: Build `CategoryPicker` component

**Files:**
- Create: `frontend/app/(dashboard)/components/CategoryPicker.tsx`

- [ ] **Step 1: Inspect existing primitives**

```bash
cat frontend/components/ui/bottom-sheet.tsx
ls frontend/components/ui/popover* 2>/dev/null
grep -rn "Popover" frontend/components/ui frontend/app | head
```

Confirm whether a Popover primitive exists. If yes, use it for desktop. If no, use a portal + click-outside hook (acceptable for a single-use surface).

- [ ] **Step 2: Build the picker body (renders inline OR inside sheet/popover)**

Component contract:

```tsx
export interface CategoryPickerProps {
  open: boolean;
  onClose: () => void;
  currentCategory: string | null;
  onSelect: (category: string | null) => void;
  suggestions?: string[];          // LLM picks; "Otros" stripped
  dominantSign?: "positive" | "negative";
  // When set, render the body inline — no sheet/popover shell.
  // Used by MerchantCard edit mode.
  inline?: boolean;
  anchorRef?: React.RefObject<HTMLElement>;  // desktop popover anchor
}
```

Body contents:
- If `currentCategory` is non-null, render a "Sin categoría" clear-row at the very top (calls `onSelect(null)` then `onClose()`).
- If `suggestions` is non-empty after filtering `"Otros"`, render the amber **Sugeridas** card with pills.
- Determine section order from `dominantSign`. Render Section A then Section B as `grid grid-cols-3 gap-1.5` icon tiles. Inside each tile: `<div class="w-7 h-7 bg-white rounded-md flex items-center justify-center">{icon}</div>` then `<span class="text-[10px] font-medium ...">{label}</span>`. Selected: `bg-luka-primary text-white`.
- Sort each section alphabetically with `Intl.Collator('es').compare`.
- Pull categories from `useCategories()` (same hook the deleted `CategoryBottomSheet` uses).
- Pull icons from `getCategoryIconOrInitial(category)` — already exists in `app/lib/category-icons.ts`.

Shells:
- Mobile: wrap body in `<BottomSheet open={open} onClose={onClose} title="Categoría">`.
- Desktop: render in a portal anchored under `anchorRef`. Click outside or `Escape` calls `onClose`.
- Inline: just render the body (no shell).

Use `useMediaQuery` (or a CSS-only `lg:hidden` / `hidden lg:block` split) to choose the shell.

- [ ] **Step 3: Visual smoke check**

Don't ship dead — render it temporarily on a throwaway page to eyeball spacing, then remove. Or just lean on Task 11 browser-use verification.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/components/CategoryPicker.tsx
git commit -m "feat(frontend): CategoryPicker shared component (sheet + popover + inline)"
git push
```

---

## Task 8: Migrate `TransactionCard` consumers off `CategoryBottomSheet`

**Files:**
- Modify: every importer of `CategoryBottomSheet` (start with `frontend/app/(dashboard)/transactions/page.tsx`)
- Delete: `frontend/app/(dashboard)/components/CategoryBottomSheet.tsx`

- [ ] **Step 1: Find importers**

```bash
grep -rn "CategoryBottomSheet" frontend/app frontend/components 2>/dev/null
```

- [ ] **Step 2: Swap each importer to `CategoryPicker`**

For each caller, replace the import and the JSX. Pass `dominantSign` from the row's amount sign (`amount > 0 ? "positive" : "negative"`). Don't pass `suggestions` (no LLM context here — Sugeridas section will be hidden).

- [ ] **Step 3: Delete `CategoryBottomSheet.tsx`**

```bash
rm "frontend/app/(dashboard)/components/CategoryBottomSheet.tsx"
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add -A frontend
git commit -m "refactor(frontend): swap CategoryBottomSheet for CategoryPicker on transactions page"
git push
```

---

## Task 9: Refactor `MerchantCard` (front + edit) and the review page

**Files:**
- Modify: `frontend/app/(dashboard)/components/MerchantCard.tsx`
- Modify: `frontend/app/(dashboard)/transactions/review/[jobId]/page.tsx`
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/lib/hooks/useMerchantReview.ts`

- [ ] **Step 1: Extend `approveMerchant` API + hook**

In `app/lib/api.ts`:

```ts
approveMerchant: (jobId: string, canonicalId: string, body: {
  display_name?: string;
  category?: string;
  split_type?: "personal" | "shared";
  action: "approve" | "skip";
}) => apiFetch<{ ok: boolean }>(...)
```

In `useMerchantReview.ts` (`useOptimisticReview`), pass `split_type` through.

- [ ] **Step 2: Front state — pills**

In `MerchantCard.tsx`, after the merchant name, render:

```tsx
<div className="mt-2 flex flex-col items-center gap-1.5">
  <button
    type="button"
    ref={categoryAnchorRef}
    onClick={() => setPickerOpen(true)}
    className="bg-slate-100 text-slate-600 text-sm font-medium px-3.5 py-1 rounded-full"
  >
    {selectedCategory || "Sin categoría"}
  </button>
  <button
    type="button"
    onClick={() => setSplitType(s => s === "personal" ? "shared" : "personal")}
    className={cn(
      "text-sm font-medium px-3.5 py-1 rounded-full",
      splitType === "shared"
        ? "bg-emerald-50 text-emerald-600"
        : "bg-blue-50 text-blue-600"
    )}
  >
    {splitType === "shared" ? "Compartido" : "Personal"}
  </button>
</div>
<CategoryPicker
  open={pickerOpen}
  onClose={() => setPickerOpen(false)}
  currentCategory={selectedCategory}
  suggestions={card.llm_suggested_categories?.filter(c => c !== "Otros")}
  dominantSign={(card.total_amount ?? 0) >= 0 ? "positive" : "negative"}
  anchorRef={categoryAnchorRef}
  onSelect={(cat) => { setSelectedCategory(cat ?? ""); setPickerOpen(false); }}
/>
```

State additions: `pickerOpen`, `splitType` (initial: `card.is_joint_account ? "shared" : "personal"` — see Step 3 about exposing this).

- [ ] **Step 3: Surface joint-account flag on the card**

The backend payload from `get_review_cards` doesn't currently include the joint flag. Add `is_joint_account: bool` to the card dict by joining `bank_accounts.account_type` in the canonical query (or the new stats query) — true if any of the linked transactions belong to a joint account. Update `ReviewCard` TS type and the schema. (This is a small backend change — make it part of this task.)

- [ ] **Step 4: Edit mode — inline picker**

In the `if (editing)` branch of `MerchantCard.tsx`, replace the entire flex-wrap pill section with:

```tsx
<CategoryPicker
  inline
  open
  onClose={() => {}}
  currentCategory={selectedCategory}
  suggestions={card.llm_suggested_categories?.filter(c => c !== "Otros")}
  dominantSign={(card.total_amount ?? 0) >= 0 ? "positive" : "negative"}
  onSelect={(cat) => setSelectedCategory(cat ?? "")}
/>
```

Drop `showAllCategories` state — no longer needed.

- [ ] **Step 5: Plumb `split_type` through approve**

Update `handleSaveApprove` and the front-state Approve to call `onApprove(displayName, selectedCategory, splitType)`. Update `Props.onApprove` signature. In `transactions/review/[jobId]/page.tsx`, pass `split_type` through `submit()` and `handleApprove`/`handleGridApprove`.

- [ ] **Step 6: Type-check + manual sanity**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add -A frontend backend/modules/merchant_review
git commit -m "feat(merchant-card): tappable pills + inline CategoryPicker + split_type on approve"
git push
```

---

## Task 10: Update `TransactionCard` pills to confirm palette consistency

**Files:**
- Modify (verify only): `frontend/app/(dashboard)/components/TransactionCard.tsx`

- [ ] **Step 1: Verify pills match the spec**

Per spec §4.6, `TransactionCard` already uses the right colors. Visual diff vs. `MerchantCard` pills (spacing, radius, weight). Adjust ONLY if there's a real inconsistency. Do not refactor for its own sake.

- [ ] **Step 2: Commit if anything changed; otherwise skip**

```bash
git diff frontend/app/\(dashboard\)/components/TransactionCard.tsx
# If empty, no commit. Otherwise:
git commit -am "style(transaction-card): align pill spacing with MerchantCard"
git push
```

---

## Task 11: End-to-end browser-use verification

**Files:** none (verification pass)

- [ ] **Step 1: Boot dev**

```bash
cd backend && uv run uvicorn app:app --reload &
cd frontend && npm run dev &
```

- [ ] **Step 2: Use `/browser-use` to walk the flow**

Login as `rafaellabra96@gmail.com`. Verify:

1. Open notifications → tap "Revisar comercios" → first card renders within ~1s.
2. Tap category pill on card front → CategoryPicker bottom sheet opens (mobile viewport) → Sugeridas section shows LLM picks (no "Otros") → tap a tile → pill updates, sheet closes.
3. Tap Personal pill → flips to Shared (emerald), tap again → back to Personal.
4. Tap Approve → next card. Verify the previous transactions on the transactions page reflect the chosen category and split type.
5. Hit pencil → edit mode opens with embedded picker, name editable, Save persists.
6. Switch to desktop viewport → tap pill → popover anchored under it.
7. On the transactions page, tap a category pill on a transaction row → CategoryPicker (no Sugeridas section) opens with section order matching the row's sign.
8. Make a transaction on a joint card via test data — confirm `split_type='shared'` lands in the DB.

- [ ] **Step 3: Document gaps**

Note any UX rough edges in `NEXT-STEPS.md` rather than fixing in this PR.

- [ ] **Step 4: Update README/ARCHITECTURE if surface contract changed**

`approveMerchant` now accepts `split_type` — note in `ARCHITECTURE.md` under the merchant review section.

- [ ] **Step 5: Commit doc updates**

```bash
git add ARCHITECTURE.md NEXT-STEPS.md
git commit -m "docs: note split_type on merchant approve + UX refresh"
git push
```

---

## Task 12: Run the requesting-code-review skill

- [ ] **Step 1: Invoke `requesting-code-review`** on the full diff range. Address findings in follow-up commits before merging.

---

## Out of scope (do not implement here)
- LLM batching / progressive notification creation.
- Frontend pagination on the review page.
- Settings → Categories page redesign.
- Income-aware WhatsApp flow.
