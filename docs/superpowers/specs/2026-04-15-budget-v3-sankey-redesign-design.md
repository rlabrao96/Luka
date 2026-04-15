# Budget v3 — Sankey redesign (hogar allocation flow + income source breakdown)

**Date:** 2026-04-15
**Status:** design — approved, ready for plan
**Supersedes/extends:** `docs/superpowers/specs/2026-04-14-budget-page-redesign-design.md`
**Endpoint:** `GET /budgets/v2/{household_id}` (in-place update, no new v3 endpoint)

---

## 1. Motivation

The 2026-04-14 sprint shipped a 2-level Sankey on `/budgets/v2`:

- Level 0: single `income` node
- Level 1: `known_bills` / `cuotas` / `savings_target` / `spendable`
- Level 2: per-category `spent_*`

Two problems surfaced in UAT on March 2026 USD:

1. **Flat attribution on the left side** — `income` is one undifferentiated lump, so the user can't see where household money actually came from (Sueldo vs. Bonus vs. Transferencia).
2. **Gastos fijos visually "crosses" the diagram** — because Recharts orders by amount and there's no structural separation between "direct outflow from income" and "outflow from spendable", the `Gastos fijos` link renders in the middle of the right-side stack, making it look like discretionary spending.

This design replaces `_build_sankey` with two dedicated multi-level builders that:

- Expose **income sources** per caller (Level 0) while preserving the existing privacy invariant
- Keep **`Gastos fijos`** as a direct child of a new income-hub node, structurally separated from discretionary spend
- Introduce a new **`Gasto personal`** allocation node wired to a new per-user setting
- Re-use the existing subscription split_type data — with an explicit user-facing override — to correctly split household vs. personal bills
- Ship as an **in-place update on `/budgets/v2`** (no v3 endpoint). The Pydantic contract shapes stay identical; `SankeyNode` gets three optional additive fields (`level`, `kind`, `member_id`) so the frontend can render multi-level without breaking older consumers.

---

## 2. Target Sankey structure

### 2.1 Hogar view (4 levels)

```
Level 0            Level 1         Level 2                  Level 3
───────────        ───────────     ────────────────         ─────────────────
Sueldo ─┐                          Meta de ahorro
Bonus ──┤                          Gastos fijos
Inv. ───┼─> Ingresos Hogar ──┬──>  Gasto personal
Transf.─┤                    │
Otros ──┘                    └──>  Disponible hogar ──┬──> spent_<cat1>
Ingresos Cami                                          ├──> spent_<cat2>
(or Contrib. fija Cami)                                ├──> spent_other
                                                       └──> spent_remaining
```

**Level 0 — income sources (caller-relative):**
- Caller's own income is broken out into nodes, one per category that appears in `user_category_preferences` with `category_type='income'` for that user, filtered to categories with sum > 0 for the month
- Node ordering follows the user's `sort_order` from `user_category_preferences` — the drag-and-drop order in `/settings/categories` decides left-to-right positioning in the Sankey
- Any transaction whose `category` does not match any of the caller's configured income categories falls into the user's existing `"Otros ingresos"` bucket (the fallback category, guaranteed to exist via the default seed)
- Other members (full or fixed, with `left_at IS NULL`) appear as **exactly one aggregated node per member**. Member label is sourced from `User.full_name` via a join on `HouseholdMember.user_id → users.id`:
  - Full-mode member → `Ingresos {User.full_name}` sized to that member's total real income for the month/currency
  - Fixed-mode member → `Contribución fija {User.full_name}` sized to `fixed_contribution_amount` (only if `fixed_contribution_currency == currency`)
  - Reimbursement member → absent from Level 0 (they contribute $0 to the pot)

**Level 1 — `Ingresos Hogar` hub:**
- Single node, value = sum of all Level 0 sources (= the existing `total` from `income_for_household_view`)
- Exists as an explicit intermediate so Level 2 nodes have a clean single parent to flow from

**Level 2 — top-level allocation (4 nodes):**
- `meta_ahorro_hogar` — `Meta de ahorro` — household savings target from `get_household_savings_target` (existing)
- `gastos_fijos_hogar` — `Gastos fijos` — household-scoped known bills after filtering by effective `split_type='shared'` (new filter — see §5)
- `gasto_personal_hogar` — `Gasto personal` — **new**; sum of `personal_allocation_amount` across members whose `contribution_mode ∈ {full, fixed}` and whose `personal_allocation_currency == currency`
- `disponible_hogar` — `Disponible hogar` — residual after the other three; computed by `spendable_ceiling` with `personal_allocation` added as a fixed outflow

**Level 3 — disponible hogar breakdown (existing risk-category behavior, scoped to `disponible_hogar` instead of `spendable`):**
- Per-risk-category `spent_<category>` nodes (same `select_risk_categories` logic as today)
- `spent_other` residual
- `spent_remaining` unused portion

### 2.2 Personal view (3 levels)

```
Level 0            Level 1                           Level 2
───────────        ─────────────────────────         ─────────────────
Sueldo ─┐          Meta de ahorro (mía)
Bonus ──┤          Gastos fijos personales
Inv. ───┼─>        Disponible personal ──┬──> spent_<cat1>
Transf.─┤                                 ├──> spent_<cat2>
Otros ──┘                                 ├──> spent_other
                                          └──> spent_remaining
```

- **Level 0** — caller's own real income sources. Grouped directly by `Transaction.category` against the caller's `user_category_preferences` (same logic as hogar Level 0, single-member scope). No "other members" in the personal view.
- **Level 1** — three allocation nodes (NOT four): `meta_ahorro_personal` / `gastos_fijos_personal` / `disponible_personal`. The personal view does **not** have a `gasto_personal` node — `personal_allocation_amount` is a **hogar-view-only** concept (it defines the `Gasto personal` node in the hogar Sankey by summing the member settings). It is **not** used to cap or define the personal view's income. The personal view preserves the v2 semantic where income = caller's real income. `disponible_personal = real_income − meta_ahorro_personal − gastos_fijos_personal` (clamped + `otras_fuentes` fallback for overspent months, same as v2).
- **Level 2** — `disponible_personal` breaks down into per-risk-category `spent_*` nodes (same `select_risk_categories` logic as today), plus `spent_other` and `spent_remaining`.
- **Known limitation (inherited from v2):** for a full-mode caller, the personal view's `disponible_personal` will appear large because the Sankey does not subtract the caller's implicit household contribution. Fixing this cleanly requires either (i) adding an `aporte_hogar` Level-1 outflow node, or (ii) capping the personal view's income at `personal_allocation_amount` when set. Neither ships in v3 — see §9.

### 2.3 Structural invariants

- **Flow conservation** (preserved from v2):
  - Every source-only node: outflow == value
  - Every intermediate node: inflow == outflow == value
  - Every terminal node: inflow == value
- **Overspent-month `otras_fuentes` fallback** (preserved from v2): when the fixed outflows (known_bills + cuotas + savings_target + personal_allocation + sankey_spendable) exceed income, a synthetic `otras_fuentes` source node feeds the shortfall. In the v3 structure, `otras_fuentes` sits alongside Level 0 income sources and flows into `Ingresos Hogar` (Level 1), preserving the invariant that Level 2 nodes have a clean single parent.
- **Caller-relative privacy** (see §4): the source breakdown at Level 0 only reads the caller's own income transactions. Other members are aggregated into per-member nodes via existing already-visible values.

---

## 3. Data model

### 3.1 New migrations (additive)

**Migration 036 — `subscription_overrides.split_type`** *(prerequisite chunk)*

```sql
ALTER TABLE subscription_overrides
  ADD COLUMN split_type TEXT CHECK (split_type IN ('personal', 'shared'));
```

- `NULL` means "inherit inferred classification from the underlying transaction's `transaction_splits.split_type`"
- Non-`NULL` means the user has explicitly classified this subscription
- Only two valid values — `partner` is not offered for subscriptions (doesn't fit the recurring-bill model)
- Downgrade: `DROP COLUMN split_type`

**Migration 037 — `user_budget_settings.personal_allocation_amount`**

```sql
ALTER TABLE user_budget_settings
  ADD COLUMN personal_allocation_amount NUMERIC(14, 2),
  ADD COLUMN personal_allocation_currency TEXT;
```

- Mirrors the existing `savings_target_amount` / `savings_target_currency` pattern for consistency
- `NULL` → user hasn't configured; `gasto_personal_hogar` node is hidden from the Sankey and that budget line does not enter `spendable_ceiling` as a fixed outflow
- Currency-scoped so CLP / USD targets are independent
- Downgrade: `DROP COLUMN personal_allocation_amount, DROP COLUMN personal_allocation_currency`

### 3.2 No changes to

- `transactions` — still stores `category` as an LLM-populated nullable string; new income source breakdown reads directly from this column
- `user_category_preferences` — existing per-user categories table from migration 027 is the source of truth for Level 0 labeling and ordering; no schema changes needed
- `household_members`, `contribution_mode`, `fixed_contribution_amount/currency` — unchanged; privacy invariant stays in `contribution_service`
- `household_budget_allocations` — **not touched.** This legacy table (`hogar_pct` / `ahorro_pct` / `personal_pct`) from the pre-v2 era is intentionally NOT used as the source for `gasto_personal`. The new per-user `personal_allocation_amount` replaces it for this purpose.

### 3.3 Additive Pydantic contract changes — `v2_schemas.py`

```python
class SankeyNode(BaseModel):
    id: str
    label: str
    value: Decimal
    risk: bool | None = None
    # New fields — all optional, default None. Frontend opts in.
    level: int | None = None          # 0..3 for hogar, 0..2 for personal
    kind: str | None = None           # "source" | "hub" | "allocation" | "spent"
    member_id: str | None = None      # set on per-member aggregated nodes only
```

- `level`: rank in the Sankey (0 = leftmost sources). Drives frontend label placement.
- `kind`: semantic category for tooltip and styling. `"source"` = Level 0 income source, `"hub"` = Level 1 income hub, `"allocation"` = Level 2 top-level allocation, `"spent"` = Level 3 risk-category or residual.
- `member_id`: set on per-member aggregated nodes (`Ingresos {Name}`, `Contribución fija {Name}`) to support tooltip display and potential future click-through. Never set on caller's own source nodes.
- All three fields default to `None`, so the existing `test_contract_fixture_matches_pydantic_schema` keeps passing as long as the fixture is updated in parallel.

`SankeyLink` and `SankeyBlock` stay unchanged.

---

## 4. Privacy invariant

### 4.1 Rule (unchanged from v2, re-stated)

> When `view="household"` and any member has `contribution_mode="fixed"`, that member's real income transactions are NEVER read. Only `fixed_contribution_amount` counts toward household income.

### 4.2 Extension for v3 — caller-relative source breakdown

> The Level 0 income source breakdown is built **only** from the caller's own real income transactions. Other members — regardless of contribution mode — appear as one aggregated node per member, sized to values that are already visible to the household under the current v2 contract:
>
> - **Full-mode other member** → total real income (already visible under full mode)
> - **Fixed-mode other member** → `fixed_contribution_amount` (already visible in household settings)
> - **Reimbursement other member** → absent from Level 0 entirely (they contribute $0)

### 4.3 Enforcement point

Single enforcement point remains `modules.households.contribution_service`. The existing `income_for_household_view` returns a scalar `Decimal`. It gains a sibling:

```python
async def income_breakdown_for_household_view(
    db: AsyncSession,
    *,
    caller_id: uuid.UUID,
    household_id: uuid.UUID,
    month: date,
    currency: str,
) -> HouseholdIncomeBreakdown:
    ...
```

where:

```python
@dataclass
class OtherMemberContribution:
    user_id: uuid.UUID
    display_name: str
    amount: Decimal
    mode: str  # "full" | "fixed"

@dataclass
class HouseholdIncomeBreakdown:
    total: Decimal                                   # same number as income_for_household_view
    caller_sources: dict[str, Decimal]               # {income_category: amount} for caller only
    caller_other_income: Decimal                     # caller's income txns whose category isn't in their preferences
    other_members: list[OtherMemberContribution]     # one per active non-caller member contributing > 0
```

Construction rules, enforced by construction:

1. **Caller sources** — `SELECT category, SUM(amount) FROM transactions WHERE user_id = caller_id AND household_id = :hid AND transaction_type = 'income' AND currency = :ccy AND transaction_date >= :first AND transaction_date < :first_next GROUP BY category`. Result is bucketed against the caller's `user_category_preferences` rows with `category_type='income'`; matches go into `caller_sources`, misses aggregate into `caller_other_income`.
2. **Other members** — iterate `HouseholdMember WHERE household_id = :hid AND left_at IS NULL AND user_id <> caller_id`. For each:
   - `mode == 'full'` → call existing `income_for_personal_view(user_id=member.user_id, ...)` to get the scalar total. This is legal because the full-mode contract already exposes real income in the household view — the pre-v2 invariant is not weakened.
   - `mode == 'fixed'` → read `fixed_contribution_amount` only if `fixed_contribution_currency == currency`. **Never** read the member's transaction rows.
   - `mode == 'reimbursement'` → skip (not appended to `other_members`).
3. **Total** — `total = sum(caller_sources.values()) + caller_other_income + sum(m.amount for m in other_members)`. This is algebraically identical to the existing `income_for_household_view` output and the existing test matrix remains valid.

The privacy property is maintained **by construction**: the only code path that reads transaction rows for a non-caller member gates on `mode == 'full'`. A `fixed` or `reimbursement` member cannot fall through to a real-income query.

The old `income_for_household_view` is retained as a thin wrapper that calls the new function and returns `breakdown.total` so any unrelated caller of the scalar API keeps working.

### 4.4 Privacy regression tests

New / expanded tests in `tests/test_budget_v2_endpoint.py` and `tests/test_contribution_modes.py`:

- **`test_caller_relative_hogar_sankey`** (new) — fixture: full+full household with distinct income category mixes. Caller A request → response shows A's own categories at Level 0 and exactly one aggregated node per other member. Caller B request → mirror.
- **`test_hogar_fixed_privacy_recursive_walk`** (expand existing) — fixture: mixed full+fixed household. Walk every node and link in the full response JSON; assert no node value equals the fixed member's real income, and that the fixed member's node value equals their `fixed_contribution_amount`.
- **`test_hogar_source_breakdown_fixed_member_collapses`** (new) — in the same mixed fixture, assert the fixed member's Level 0 node exists and is sized to `fixed_contribution_amount`, labeled `Contribución fija {name}`.
- **`test_personal_sankey_uses_caller_real_income`** (new) — for a fixed-mode caller requesting `view=personal`, assert Level 0 shows their real income sources (personal view is the one place fixed members see their own income; this is unchanged from v2).
- **`test_flow_conservation_v3_all_seeds`** (new) — runs against all four seeded households (`rafa-full`, `rafa-fixed`, `rafa-reimb`, `rafa-solo`) for CLP and USD and asserts flow conservation on every non-source / non-terminal node.

---

## 5. Subscription classification toggle (prerequisite chunk)

Ships as a **separate PR** before the v3 Sankey sprint starts. Required because the current `get_household_known_bills` sums all detected subscriptions regardless of `split_type`, which means personal subs (e.g., one member's Netflix) currently count toward the household pot. The v3 `gastos_fijos_hogar` node needs clean data.

### 5.1 Backend

**Service: `modules/subscriptions/service.py` (additions)**

```python
async def reclassify_subscription_split(
    db: AsyncSession,
    user_id: uuid.UUID,
    merchant_key: str,
    new_split_type: str,  # "personal" | "shared"
    window_months: int = 3,
) -> int:
    """Reclassify a subscription's split_type and cascade to the last N months
    of underlying transactions. Returns the count of transactions affected."""
```

Steps:

1. Validate `new_split_type in {"personal", "shared"}`, else `ValueError`
2. Compute window: `threshold = NOW() - INTERVAL '{window_months} months'`
3. Find candidate transactions:
   ```sql
   SELECT t.id
   FROM transactions t
   LEFT JOIN merchants m ON m.id = t.merchant_id
   WHERE t.user_id = :uid
     AND COALESCE(m.normalized_name, t.raw_merchant_name) = :merchant_key
     AND t.transaction_date >= :threshold
   ```
4. For each candidate: UPDATE `transaction_splits SET split_type = :new, decided_by_user_id = :uid, decided_at = NOW()` WHERE `transaction_id = :tid`. If no row is affected, INSERT a new split row `(transaction_id, split_type, decided_by_user_id, decided_at)`.
5. UPSERT `subscription_overrides (user_id, merchant_key, split_type, ...)` — existing `upsert_override` is extended to accept `split_type` and `ON CONFLICT` updates it.
6. Invalidate `detected_subscriptions_cache` for `user_id` so next read recomputes with new data.
7. Return count of transactions touched.

**Read-side updates:**

- `detect_from_rows` already pulls `split_type` from the LEFT JOIN to `transaction_splits` defaulting to `'personal'`. That already reflects the cascade after the next cache recompute.
- `_merge_overrides` extended to apply `subscription_overrides.split_type` on top of the raw detected value.
- `get_household_known_bills` adds a filter `if item.get("split_type") == "shared"` before summing per member.
- New read-only helper `get_user_personal_known_bills(db, user_id, currency)` — filters to `item.get("split_type") == "personal"` for the user-scoped personal view Sankey.

**Router: `modules/subscriptions/router.py`**

```
POST /subscriptions/{merchant_key}/classify
body: { "split_type": "shared" | "personal" }
returns: { "ok": true, "transactions_updated": int }
```

### 5.2 Frontend

- `frontend/app/(dashboard)/subscriptions/components/SubscriptionsTable.tsx` (or equivalent — the detail table shown in the user's screenshot): add a column `Clasificación` between `Categoría` and `Editar`. Cell renders a small pill:
  - `Personal` — blue-tinted
  - `Compartido` — green-tinted
- Click the pill → toggles to the other value → POSTs to `/subscriptions/{merchant_key}/classify` → optimistic re-render → on success, triggers a `/budgets/v2` refetch in the shared budget query cache so the Sankey re-renders with the new classification.
- No modal needed for the toggle — click-to-flip keeps friction low.

### 5.3 Tests

- `test_reclassify_cascade_3_months` — fixture with 5 months of Netflix transactions; call reclassify; assert only last 3 months' `transaction_splits` are updated.
- `test_reclassify_inserts_missing_splits` — transactions with no existing `transaction_splits` row get one inserted.
- `test_reclassify_updates_override_row` — after call, `subscription_overrides` row has `split_type = new_value`.
- `test_reclassify_invalidates_cache` — after call, `detected_subscriptions_cache` row for user is gone (or marked stale).
- `test_override_wins_over_inferred_split_type` — when both an inferred value and an override exist, override wins in the read path.
- `test_household_known_bills_filters_by_split_type` — personal subs drop out of the household total, shared subs stay in.
- `test_personal_known_bills_filters_by_split_type` — personal subs stay in, shared drop out.

---

## 6. v3 Sankey sprint — file-by-file impact

### 6.1 New files

- `docs/superpowers/specs/2026-04-15-budget-v3-sankey-redesign-design.md` — this file
- `docs/superpowers/plans/2026-04-15-budget-v3-sankey-redesign-plan.md` — the implementation plan (to be generated by `writing-plans` skill)
- `backend/alembic/versions/036_subscription_overrides_split_type.py` — migration (prerequisite chunk)
- `backend/alembic/versions/037_user_budget_settings_personal_allocation.py` — migration
- `backend/tests/test_budget_v3_sankey.py` — new v3-specific tests (flow conservation on 4-level structure, caller-relative privacy, personal allocation wiring)
- `backend/tests/test_subscription_reclassify.py` — prerequisite chunk tests

### 6.2 Modified files

**Backend (v3 sprint):**
- `backend/modules/households/contribution_service.py` — add `HouseholdIncomeBreakdown` + `income_breakdown_for_household_view`; `income_for_household_view` becomes a thin wrapper
- `backend/modules/budgets/v2_schemas.py` — additive fields on `SankeyNode`
- `backend/modules/budgets/v2_service.py` — `_build_sankey` replaced by `_build_hogar_sankey` + `_build_personal_sankey` + shared `_pay_first_fit` helper; `get_budget_v2` wires the new breakdown structure and personal allocation into the builders
- `backend/modules/budgets/forecast.py` — `spendable_ceiling` adds `personal_allocation` as a new fixed-outflow parameter (default `Decimal("0")` for back-compat)
- `backend/modules/budgets/user_budget_settings_service.py` — new `get_personal_allocation(user_id, currency)` + `get_household_personal_allocation(household_id, currency)` mirrors of the existing savings-target helpers
- `backend/tests/fixtures/budget_v2_sample_response.json` — updated to reflect the new multi-level Sankey structure

**Backend (prerequisite chunk):**
- `backend/modules/subscriptions/service.py` — add `reclassify_subscription_split`, extend `_merge_overrides` to apply `split_type` override, extend `upsert_override` to accept `split_type`
- `backend/modules/subscriptions/read.py` — `get_household_known_bills` filters by effective `split_type='shared'`; new `get_user_personal_known_bills` filters by `split_type='personal'`
- `backend/modules/subscriptions/router.py` — new `POST /subscriptions/{merchant_key}/classify` endpoint
- `backend/modules/subscriptions/schemas.py` — new `ClassifySubscriptionRequest` pydantic model

**Frontend (v3 sprint):**
- `frontend/app/(dashboard)/components/BudgetSankey.tsx` — rank-based label renderer reading new `level` / `kind` / `member_id` fields; fallback to current terminal-detection when fields absent
- `frontend/app/(dashboard)/budgets/page.tsx` — container sizing for wider 4-level layout
- `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx` — new input for `personal_allocation_amount`, mirrors the existing `savings_target` UI

**Frontend (prerequisite chunk):**
- `frontend/app/(dashboard)/subscriptions/components/SubscriptionsTable.tsx` (or whichever file renders the detail table) — new `Clasificación` column with click-to-flip pill
- `frontend/lib/api/subscriptions.ts` — new `classifySubscription(merchantKey, splitType)` client function

---

## 7. Chunking plan (for writing-plans)

### 7.1 Prerequisite PR (ships first)

**Chunk 0 — Subscription classification toggle**

| Area | Scope |
|---|---|
| Migration | 036 adds `split_type` to `subscription_overrides` |
| Backend service | `reclassify_subscription_split`, extended `_merge_overrides` and `upsert_override`, updated read helpers, new `get_user_personal_known_bills` |
| Router | `POST /subscriptions/{merchant_key}/classify` |
| Frontend | New column with click-to-flip pill, optimistic update, budget refetch |
| Tests | `test_subscription_reclassify.py` (all 7 tests from §5.3) |

**Merge gate:** prerequisite PR must be merged to main before v3 sprint PR opens.

### 7.2 v3 Sankey sprint PR (bundled, parallel chunks)

| Chunk | Depends on | Area |
|---|---|---|
| **A** — `personal_allocation_amount` wiring | none | Migration 037, `user_budget_settings_service` helpers, `BudgetSettingsSection.tsx` UI |
| **B** — `HouseholdIncomeBreakdown` + builder | none | Dataclass, `income_breakdown_for_household_view`, unit tests (caller-relative, privacy) |
| **C** — `_build_hogar_sankey` + `_build_personal_sankey` | B (interface lock) | Pure functions, shared `_pay_first_fit`, unit-tested against fixtures |
| **D** — `get_budget_v2` glue | A + B + C | Additive `SankeyNode` fields, wiring between breakdown + builders + personal allocation, fixture update, forecast `spendable_ceiling` signature update |
| **E** — `BudgetSankey.tsx` multi-level renderer | D (needs real payloads) | Rank-based labels, container sizing, tooltip update, `budgets/page.tsx` grid adjustment |
| **F** — Integration & verification | all | Run full test matrix, update fixture if needed, code-level UX audit, manual verification against user's real household, final review doc |

B and A can start in parallel. C starts as soon as the dataclass interface from B is committed. D merges the three together. E starts after D merges (needs real API payloads to render against). F is the integration gate.

---

## 8. Verification gates

Same gates as the 2026-04-14 sprint, updated for v3:

- **Backend tests** — 48/48 existing tests still pass, plus all new tests from §4.4 and §5.3 and §6.2 pass
- **Privacy regression** — `test_hogar_fixed_privacy_recursive_walk` passes on the new multi-level structure; `test_caller_relative_hogar_sankey` passes for both callers in a full+full household
- **Flow conservation** — `test_flow_conservation_v3_all_seeds` passes for all four seeded households (`rafa-full`, `rafa-fixed`, `rafa-reimb`, `rafa-solo`) in both CLP and USD
- **Frontend type check** — `npm run build` clean, no TypeScript errors
- **Real household smoke test** — current month CLP renders a flow-conserving 4-level Sankey for household `8737617e-37a2-40bb-9dcc-f1c592db7b49` without falling back to the overspent banner unless data genuinely is overspent
- **Code-level UX audit** — reviewer walks `budgets/page.tsx` + `BudgetSankey.tsx` + API response for the real household and confirms: (i) Level 0 sources match user's configured income categories from `/settings/categories`, (ii) `Gastos fijos` is a direct child of `Ingresos Hogar` and not mixed with discretionary, (iii) `Gasto personal` node is present only if the caller has set `personal_allocation_amount`, (iv) per-member aggregated nodes render with display names in tooltips
- **Browser-based UAT is out of scope** — Google OAuth automation-detection blocks chrome-devtools-mcp and browser-use from signing into Luka. Documented in the 2026-04-14 Task I integration report as a standing constraint.

---

## 9. Out of scope for v3 (deferred)

- **Income source alias map / normalization layer** — the initial approach was a curated dict collapsing LLM drift (`"Salario"` → `"Sueldo"`). Replaced by direct use of `user_category_preferences`. If LLM drift becomes a problem, we can revisit — likely by tightening the LLM categorization prompt to pick from the user's configured list rather than adding a new aliasing step.
- **New `income_source` enum column on `Transaction`** — not needed; the user-configured categories are sufficient.
- **Per-member breakdown of fixed contributions** — Level 0 shows one node per other member, even if that member's contribution is split into multiple sources behind the scenes.
- **Historical "fallback to last month's personal spending actuals"** for users who haven't set `personal_allocation_amount` — considered as a v1.1 enhancement during brainstorming. Not shipping in v3; the node is simply hidden when the setting is null.
- **`is_shared` overrides per-transaction** (rather than per-subscription) — a user might want to override a one-off transaction without touching the subscription rule. Not shipping; out of scope.
- **Switching the Sankey library** — Recharts 3.8 stays. Custom node renderer updates handle the multi-level layout.
- **New `/budgets/v3` endpoint** — the Pydantic contract stays backward-compatible with additive fields. In-place on `/budgets/v2`.
- **Personal view `aporte_hogar` outflow node** — a full-mode caller's personal view currently shows their full real income flowing into `disponible_personal` (via residual math), with no explicit acknowledgement that most of it went to the household pot. The clean fix is a new Level-1 `aporte_hogar` node absorbing the delta between real income and the caller's personal-pot allocation. Deferred because (a) it requires a second round of caller-relative logic for the personal view, (b) the semantics overlap with `personal_allocation_amount` in a way that needs its own brainstorming session, and (c) the v2 behavior is already "working enough" for personal view users.
- **Personal view income capping at `personal_allocation_amount`** — alternative framing to `aporte_hogar`: cap the personal view's income at the setting value and show a single source node instead of breakdown. Rejected because it loses the source breakdown story, which was the motivating feature of v3.

---

## 10. Open questions resolved during brainstorming (for posterity)

| Q | Resolved direction |
|---|---|
| How to size `Gasto personal`? | **(D)** New per-user `personal_allocation_amount` field, default null (node hidden). Hybrid with last-month actuals noted as v1.1 fallback. |
| How to categorize income sources? | Use **`user_category_preferences`** directly (user's configured income categories with `sort_order`). No alias map. No new enum. |
| How to split household vs. personal bills? | New **subscription classification toggle** (override on `subscription_overrides`) + cascade to last 3 months of `transaction_splits`. Shipped as prerequisite chunk. |
| Privacy under source breakdown? | **Caller-relative** model — caller's own sources broken out; other members appear as one aggregated node per member (existing visible values only). Fixed members show as `Contribución fija {Name}`. |
| Endpoint versioning? | **In-place on `/budgets/v2`** — additive Pydantic fields, no new endpoint, fixture updated in-sprint. |
