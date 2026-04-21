# Budget Page — Luka Ultrareview

**Date:** 2026-04-21
**Scope reviewed:** 22 files, ~4,245 LOC
- Frontend (5 files, 1,076 LOC): `frontend/app/(dashboard)/budgets/page.tsx`, `frontend/app/(dashboard)/components/BudgetSankey.tsx`, `frontend/app/(dashboard)/components/BudgetConfigModal/{index,PersonalAllocationRow,CategoryCapsEditor}.tsx`
- Backend (17 files, 3,169 LOC): all of `backend/modules/budgets/`

**Agents run:** Security, Logic, Performance, Style, Frontend — all five completed.

---

## Executive summary

1. **Three sign-convention bugs in `personal_service.py` make the waterfall household personal block numerically wrong** (Logic F1–F3). Ceiling is inflated by deposits instead of reduced, `deposited`/`available` render as `None` for real outflows, and `percent_used` goes negative. Inconsistent with `v2_service.py` which uses `abs()`. **Critical, fix first.**
2. **Currency regex `^(CLP|USD)$` blocks LATAM expansion** (Logic F6 + Security F6). Users in CO/MX/PE/BR cannot save cuotas or budget settings. Same hardcoded `"CLP"` default in `v2_service.py:886`. Directly violates CLAUDE.md's multi-currency rule.
3. **Sankey overlap + invisible right-side labels confirmed in code** (Frontend F1–F2). Fixed 360px height squashes many nodes; labels at `x+width+6` clip outside the SVG because no right `margin` is set on `<Sankey>`. Both user-reported symptoms are real and fixable in one small patch.
4. **Two IDOR gaps on write paths** (Security F1–F2). `set_monthly_budget` doesn't verify `bank_account_id` belongs to the household; `create_cuota` doesn't verify `origin_transaction_id` ownership. Both accept user-supplied UUIDs with only per-endpoint membership checks.
5. **Frontend `SectionFlowBody` looks up v2 Sankey node ids (`income`, `known_bills`) that the v3 backend never emits** (Logic F13 + Style F15/F16). The "Déficit" banner always shows `Ingreso: $0`. `NODE_COLOR` fallback branch is dead. The v2→v3 migration left orphan code on both sides.
6. **`v2_service.py` is 1,168 lines** (Style F1) mixing helpers, two near-duplicate Sankey builders, and the orchestrator; carries dead imports (`_ = HouseholdBudgetAllocation`) and "Chunk C/E/F" planning debris. Tech-debt, not a bug, but blocks future bug-fixes in the Sankey math.

---

## Findings by severity

### CRITICAL

**[Logic F1]** `backend/modules/budgets/personal_service.py:22,249` — `compute_personal_ceiling` returns `income - user_deposited`, but transfers are stored negative. Real deposits inflate the ceiling instead of reducing it.
→ Fix: `ceiling = income + user_deposited` (or `income - abs(user_deposited)`). Add unit test with a real outgoing transfer.

**[Logic F2]** `backend/modules/budgets/personal_service.py:164-210` — `total_deposited` is negative (outflow) but code gates on `if total_deposited > 0`, so `deposited`/`available`/`percent_used` render as `None` for actual deposits. `available = total_deposited - household_spent` is also inverted.
→ Fix: normalize with `abs()` or flip sign once at the aggregate boundary.

**[Logic F3]** `backend/modules/budgets/personal_service.py:213-255` — `breakdown_household + breakdown_personal` are summed without `abs()`, passed as `spent` to `build_personal_block`, so `available = ceiling - spent` adds instead of subtracts. Entire personal block is sign-inverted. `v2_service.py:1023` already uses `abs(Decimal(str(t.amount)))` — v1 and v2 diverge.
→ Fix: wrap aggregates in `func.abs(...)` to match v2 convention.

### HIGH

**[Security F1]** `service.py:64-92` — `set_monthly_budget` accepts `bank_account_id` from client without verifying it belongs to `household_id`. IDOR on write.
→ Fix: validate `BankAccount.household_id == household_id` before upsert.

**[Security F2]** `cuota_service.py:120-170` — `create_cuota` doesn't verify `origin_transaction_id` is owned by caller.
→ Fix: `SELECT id WHERE id = :tx_id AND user_id = :uid` before insert.

**[Security F3]** `cuota_router.py:33-47` — `_user_active_household_id` silently picks "first active membership" for users in multiple households. Non-deterministic + cross-household cuota leak.
→ Fix: require `household_id` explicitly; delete the helper.

**[Logic F4]** `allocation_service.py:30-32` — `hogar_spent / income` with negative expense sums produces negative percentages; `ahorro_pct = 100 - avg_hogar - avg_personal` can exceed 100. No clamp on final `personal`.
→ Fix: `abs()` the sums; `personal = max(0, 100 - hogar - ahorro)`.

**[Logic F5]** `service.py:39-52` — `get_budget_status` sums transactions with no `transaction_type` filter, lumping income + transfers + expenses.
→ Fix: add `transaction_type == 'expense'` and `abs()`.

**[Logic F6 / Security F6]** `cuota_schemas.py:25`, `user_budget_settings_router.py:29,32`, `v2_service.py:886` — currency hardcoded to `^(CLP|USD)$` or `"CLP"` fallback. Blocks CO/MX/PE/BR/US users.
→ Fix: broaden to `^(CLP|USD|COP|MXN|PEN|BRL)$` (or drop the regex); replace CLP fallback with country-derived default.

**[Frontend F1]** `BudgetSankey.tsx:98-99` — fixed `h-[360px]` regardless of node count forces Recharts to squash many nodes → the user-reported overlap.
→ Fix: dynamic height = `max(360, maxColumnNodeCount * 56 + 80)`, bump `nodePadding` to 32, `iterations` to 64.

**[Frontend F2]** `BudgetSankey.tsx:135-139` — level-2/3 labels placed at `labelX = x + width + 6` but `<Sankey>` has no right `margin`, so labels are clipped outside the SVG — the user-reported invisible category names.
→ Fix: add `margin={{ top: 20, right: 140, bottom: 20, left: 20 }}` to `<Sankey>`.

**[Frontend F3]** `BudgetSankey.tsx` — no `role="img"`, no `<title>`/`<desc>`, no table fallback. WCAG 1.1.1 fail.
→ Fix: wrap in `<figure role="img" aria-labelledby aria-describedby>` + `sr-only` summary + "Ver como tabla" toggle.

**[Perf F1]** `user_budget_settings_service.py:106-126` — `get_household_savings_target` runs N+1 per member; each `get_or_create` also side-effect-inserts rows for partners on a read path.
→ Fix: single JOIN query mirroring `get_household_personal_allocation`; make `get_savings_target` read-only.

**[Perf F2]** `v2_service.py:128-152` — `_reimbursement_members_known_bills` fans out per-member queries serially.
→ Fix: single SQL with subtraction, or `asyncio.gather` (careful: `AsyncSession` is not concurrency-safe — use per-task connections).

**[Perf F3]** `v2_service.py:185-231` — `_three_month_category_stats` = 3 sequential queries instead of one `GROUP BY (category, month)`.

**[Perf F4]** `v2_service.py:258-288` — `_daily_burn_14d` hydrates full ORM rows to sum; push `SUM(ABS(amount))` + savings-category exclusion into SQL.

**[Perf F5]** `allocation_service.py:73-141` — 9+ sequential queries inside monthly loop; `personal_acc_result` re-queried 3× identically.

**[Style F1]** `v2_service.py` — 1,168 lines, two near-duplicate Sankey builders, mixes orchestration/SQL/helpers.
→ Fix: split into `v2_service.py` + `v2_sankey.py` + `v2_queries.py`; merge the two Sankey builders behind a `view` parameter.

### MEDIUM

**[Logic F7]** `v2_service.py:1070` — `caps.get(name) or (mean + std)`: a user cap of `0` is falsy and silently replaced by historical mean+std.
→ Fix: explicit `None` check.

**[Logic F8]** `v2_service.py:258-288` — `_daily_burn_14d` uses `now()` even when viewing a historical month; runway alert for past months reflects live burn.

**[Logic F9]** `cuota_service.py:149` — `monthly_amount.quantize(0.01)` drifts from `total_amount` by cents; no residual on final installment.

**[Logic F13]** `budgets/page.tsx:52-54` — `SectionFlowBody` looks up node ids `"income"`/`"known_bills"` that the v3 Sankey never emits (it emits `ingresos_hogar`, `gastos_fijos`). The "Déficit" banner permanently shows `Ingreso: $0`.
→ Fix: drive banner from explicit response fields, not Sankey node scraping.

**[Security F4]** `category_service.py` — `CategoryBudgetItem.category` unbounded `str`; no dedup; no cap on list length.
→ Fix: `Field(min_length=1, max_length=64)`, dedupe, cap list at 200.

**[Security F5]** `user_budget_settings_router.py` — `savings_target_amount`/`personal_allocation_amount` unbounded Decimal; one member can corrupt household aggregates.
→ Fix: `ge=0, le=1_000_000_000`.

**[Security F7]** `v2_service.py:862-1161` (household view) — `_fetch_month_transactions` doesn't filter `split_type == 'shared'`, so per-category household totals include partners' personal expenses. Deviates from v1 convention; may or may not be intentional.
→ Confirm with product; if unintentional, add `JOIN TransactionSplit WHERE split_type='shared'`.

**[Frontend F4]** `BudgetSankey.tsx:149` — `fill-slate-400` at `text-[10px]` for money values = ~3.4:1 contrast, below WCAG AA.
→ Fix: `fill-slate-600`, min `text-[11px]`, `font-medium`.

**[Frontend F5]** `BudgetSankey.tsx:97-98` — `min-w-[720px]` forces horizontal scroll on every mobile device. Violates mobile-first.
→ Fix: `hidden md:block` + stacked-bar alternative below `md`.

**[Frontend F6]** `BudgetSankey.tsx:167-173` — Tooltip formatter falls back to `"Valor"` on link hovers (no source/target rendering).
→ Fix: detect link vs node via `payload.source/target`; render `"{src} → {tgt}: {money}"`.

**[Frontend F7]** `budgets/page.tsx:259` — `toLocaleDateString("es-CL", ...)` hardcoded. Violates LATAM rule.
→ Fix: derive locale from `me.country`.

**[Frontend F8]** `budgets/page.tsx:307-321` — `sameAsHogar` uses floating-point equality + `nodes.length` heuristic. False positives.
→ Fix: tolerance + backend-provided `personal_same_as_household` boolean.

**[Frontend F9]** `PersonalAllocationRow.tsx:82-89` + `CategoryCapsEditor.tsx:163-172` — `<input type="number">` rejects LATAM thousands separators (`200.000`), exposes spinner on mobile.
→ Fix: `inputMode="decimal"` with text type + parser.

**[Frontend F10]** `BudgetConfigModal/index.tsx` — accordion likely lacks `aria-expanded`/`aria-controls`; audit `AccordionRow`.

**[Frontend F11]** `CategoryCapsEditor.tsx:163-172` — input relies on placeholder, no `aria-labelledby` to the visible category name.

**[Frontend F12]** `CategoryCapsEditor.tsx:143-145` — rigid `grid-cols-[32px_1fr_130px_26px]` truncates long LATAM category names on narrow viewports.

**[Frontend F13]** `BudgetConfigModal/index.tsx:93-99` — cosmetic drag handle on bottom sheet, no swipe-to-dismiss.

**[Perf F6–F9]** `v2_service.py` hydrates ORM rows instead of using SQL aggregates; `get_budget_v2` runs 12+ serial queries; `GET /settings/budget` is a write path.

**[Style F2–F11]** Dead imports (`_ = HouseholdBudgetAllocation`), "Chunk C/E/F" planning comments, duplicated `_slugify`/`_normalize` Spanish-accent logic, duplicated month-bounds math across 5 files, raw `text()` SQL where ORM models exist, unused tuple return in `_pay_first_fit`, v1 `AllocationCard` + v2 absolute-amounts living side-by-side (deprecation decision needed).

### LOW / NIT

Rounding drift on last installment, unbounded `SELECT DISTINCT currency`, raw `text()` for pace query, `assert` used for input validation, missing unit tests for the two Sankey builders, dead `NODE_COLOR` v2 fallback, three `as any` Recharts casts, cross-coupled currency inference between savings target and personal allocation, "Guardado" badge not announced to screen readers, "Esc para cerrar" hint rendered on mobile.

---

## Cross-cutting observations

1. **v2 → v3 Sankey migration is incomplete on both sides.** Backend emits new node ids (`ingresos_hogar`, `gastos_fijos`, `disponible_hogar`); frontend `SectionFlowBody` and `NODE_COLOR` still look up the v2 ids (`income`, `known_bills`, `spendable`). This showed up in Logic F13, Style F15, Style F16 independently. A 10-minute cleanup unblocks the overspent banner and removes three dead branches.

2. **Amount-sign convention inconsistently applied.** `v2_service.py` uses `abs()` everywhere. `personal_service.py` and `allocation_service.py` and `service.py` forget it, producing negative percentages, inflated ceilings, and inverted "available" math. Logic F1–F5 are five instances of the same bug. A `SUPPORTED_SIGNED_EXPENSE_SUM()` helper or consistent `abs()` at SQL level would prevent recurrence.

3. **Hardcoded Chilean defaults in ≥4 places.** Currency regex (cuota_schemas + settings_router), CLP fallback (v2_service:886), `es-CL` locale (page.tsx:259). Pattern suggests no central `DEFAULT_CURRENCY_FOR(country)` / `LOCALE_FOR(country)` helper exists — creating one and replacing call sites would eliminate this class of bug.

4. **Read paths that write.** `get_or_create` side-effect-inserts rows in `get_savings_target`, `GET /settings/budget`, and transitively in `get_household_savings_target`. Partner rows created on caller's read. Surfaced by Perf F1, Logic F11, Style F10. Convert to read-only selects.

5. **v1 and v2 budget abstractions coexist.** `HouseholdBudgetAllocation` + `AllocationCard` (v1) still wired, but the new budgets page uses `user_budget_settings` (v2). Style F6 flags the deprecation decision; users may see two different "allocation" UIs driven by different data models.

---

## What looked good

- `v2_service._build_hogar_sankey` flow-conservation is carefully implemented; the `_pay_first_fit` routing is a thoughtful solution for partial coverage.
- Partner privacy via `income_breakdown_for_household_view` is a real abstraction, not a comment.
- `BudgetSankey` empty-state guards (zero-sum flow → friendly message instead of NaN crash) are well thought-out.
- Frontend v2 modal has a nicely consistent "guardado" autosave pattern across PersonalAllocationRow and CategoryCapsEditor.

---

## Sankey redesign plan (ui-ux-pro-max)

The Sankey is the right chart type for money-flow visualization (confirmed by ui-ux-pro-max chart guidance: "Flow/Process Data → Sankey Diagram, gradient source→target, opacity 0.4–0.6"). The two user-reported issues are both fixable in-place without swapping the chart library.

**Root causes:**
1. **Overlap:** fixed 360px height + many terminal nodes in the right column → Recharts compresses rectangles and curved links collapse onto each other.
2. **Invisible right labels:** labels placed at `x + width + 6` but `<Sankey>` has no right `margin`, so labels render past the SVG's right edge and get clipped.

**Minimal patch (keeps current component, no new dependencies):**
1. Add `margin={{ top: 20, right: 140, bottom: 20, left: 20 }}` to the `<Sankey>` component — reserves 140px for right-edge labels.
2. Compute `chartHeight = max(360, maxColumnNodes * 56 + 80)` and set that on the wrapper div (not the 360 fixed).
3. Bump `nodePadding` from 24 → 32 and `iterations` from 32 → 64 for better layout settling.
4. Upgrade label typography: `fill-slate-700` → keep; value text `fill-slate-400 text-[10px]` → `fill-slate-600 text-[11px] font-medium` (4.5:1 contrast).
5. Mobile: `hidden md:block` wrapper + a compact stacked-bar/waterfall variant for `md:hidden`.
6. Accessibility: wrap in `<figure role="img" aria-labelledby aria-describedby>` with `sr-only` summary text including the main totals.
7. Memoize: `useMemo` the `safeNodes`/`safeLinks`/`data` derivations; `useCallback` the node renderer.
8. Cleanup: delete `NODE_COLOR` v2 fallback (dead), delete unused `idToIndex` (line 60), type the Recharts props instead of three `as any`.
9. Tooltip fix: detect link vs node in the formatter; render `"{src} → {tgt}: {money}"` on link hover.

**Optional polish (pairs well with the Sankey fixes):**
- Legend below the chart (source / hub / allocation / spent / risk) so color isn't the only encoding (WCAG 1.4.1).
- Stripe fill or dashed outline for `risk === true` nodes (currently relies on red alone).
- Hover highlight: reduce opacity of non-focused flows on mouseover to 0.15 so the active path stands out.

---

## Next step

Want me to implement the Sankey patch now (items 1–9 above, scoped to `BudgetSankey.tsx` + the v3 node-id cleanup in `budgets/page.tsx`)? Or tackle the three critical `personal_service.py` sign bugs first? Both are short — happy to do either order.
