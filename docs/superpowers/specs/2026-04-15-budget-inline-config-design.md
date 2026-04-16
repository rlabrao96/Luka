# Budget inline config — accordion modal on `/budgets` with smart category caps picker

**Date:** 2026-04-15
**Status:** design — approved, ready for plan
**Scope:** frontend-only (no backend/API/schema changes)
**Related:** extends the v3 Sankey redesign (`2026-04-15-budget-v3-sankey-redesign-design.md`)

---

## 1. Motivation

Every knob that feeds the `/budgets` Sankey currently lives on `/settings`:

1. `BudgetSettingsSection` — savings target, payday day, personal allocation
2. `ContributionSection` — contribution mode (full / fixed / reimbursement) and fixed amount
3. `CategoryBudgetsSection` — per-category monthly caps (one row per expense category, currently ~20 rows)

The user goes to `/budgets`, sees the Sankey reflect a number they don't like, has to leave the page to `/settings`, scroll through unrelated sections, edit, save, come back. This breaks the feedback loop and hides the settings behind a route that's crowded with identity/privacy/banking concerns.

Two UX problems on top of the routing friction:

- **The category-caps UI doesn't scale.** Today `CategoryBudgetsSection` renders a row for *every* expense category. With the default seed (~20 categories) and users who typically only care about 3–5, this produces a long list of empty rows. Frontend-design review flagged this as "scan fatigue" on the settings page — the fix was deferred.
- **There's no entry point discoverability for the contribution-mode setting.** New users don't know Aporte al hogar exists until they stumble onto it in settings.

This spec moves all three sections into a single "Configurar presupuesto" modal on `/budgets`, redesigns the category caps UI to be empty-by-default with a search picker, and leaves the backend API untouched.

---

## 2. Scope

### In scope
- New `BudgetConfigModal` component mounted on `/budgets`
- New gear-button entry point next to the existing `CurrencyToggle` in the `/budgets` header
- Accordion layout with 5 collapsible rows across 3 section groups (Mi plan / Hogar / Categorías)
- Inline per-section save (each row has its own Guardar button, no global dirty state)
- New `CategoryCapsEditor` component: list-active-caps + `+ Agregar tope` button + searchable picker with "top 5 spent this month" suggestions
- Mobile: bottom-sheet variant of the same modal using the existing `@keyframes slide-up` in `globals.css`
- Removal of `BudgetSettingsSection`, `ContributionSection`, and `CategoryBudgetsSection` from `/settings/page.tsx`

### Out of scope
- Any backend/API/schema changes. All three sections already have working endpoints (`PATCH /budgets/settings`, `PATCH /auth/contribution`, `POST /budgets/categories/{household_id}`). The modal re-uses them verbatim.
- Rewriting the individual form controls (currency dropdowns, number inputs). We port the existing logic out of the old section components, not rewrite it.
- Cuotas UI — `MarkAsCuotaDialog` is triggered from the transactions list, not from settings, and stays as-is.
- A first-run onboarding flow ("finish setting up your budget"). The spec covers only the recurring-config surface.
- Making the modal sections contextually accessible from clicks on individual Sankey nodes. That was considered as option C in brainstorming and rejected as future work.

---

## 3. UX specification

### 3.1 Entry point

Add a gear button to the `/budgets` page header, right of `CurrencyToggle`:

```tsx
<div className="header-actions flex items-center gap-2">
  {showToggle && <CurrencyToggle … />}
  <button
    type="button"
    aria-label="Configurar presupuesto"
    onClick={() => setConfigOpen(true)}
    className="w-9 h-9 rounded-lg border border-slate-200 bg-white …"
  >
    <Settings2Icon />
  </button>
</div>
```

**Empty-state nudge:** when the user has never set a savings target OR payday, render a small blue dot on the gear button (absolute-positioned, 7px, border-white). Conditions, evaluated from the `budgetSettings` query already used by the old `BudgetSettingsSection`:

```ts
const needsSetup =
  budgetSettings.data?.savings_target_amount == null ||
  budgetSettings.data?.payday_day_of_month == null;
```

The dot is a subtle nudge — no banner, no toast, no red alert. Once the user opens the modal and saves one of those fields, the dot disappears.

### 3.2 Modal shell

Component: `frontend/app/(dashboard)/components/BudgetConfigModal.tsx`

Layout (desktop, ≥768px):

- Fixed overlay, `bg-slate-900/40 backdrop-blur-sm`
- Centered card, `max-w-md` (~440px), `max-h-[90vh]`, scrollable body, `rounded-2xl`, `shadow-[0_24px_64px_-16px_rgba(15,23,42,0.22),0_8px_24px_-12px_rgba(15,23,42,0.10)]`
- Entry animation: 340ms `cubic-bezier(.2,.9,.25,1.2)` from `opacity:0; translateY(8px) scale(.985)` → `opacity:1`

Layout (mobile, <768px):

- Bottom sheet: full-width card anchored to `bottom-0`, `rounded-t-2xl`, max-height `90vh`, uses the existing `animate-slide-up` class in `globals.css`
- Drag handle (decorative): `h-1 w-10 rounded-full bg-slate-200` above the header
- Same accordion content, same section breadcrumbs, same inline save pattern
- Close on overlay tap, `Esc` keypress, or explicit close button

**Header:**

- Radial blue glow top-right (`radial-gradient(1200px 200px at 90% -20%, rgba(96,165,250,0.18), transparent 60%)`) on a white → `#F6FAFF` vertical gradient
- Eyebrow in luka-primary: `CONFIGURAR PRESUPUESTO` (uppercase, letter-spacing 0.12em)
- Title: "Tu plan de este mes" — DM Sans 700, 22px, `-0.02em` letter-spacing
- Subtitle: "Todos los números que alimentan el Sankey, en un solo lugar."
- Close button top-right (`32×32`, `rounded-[9px]`, `bg-slate-900/5`)

**Footer:**

- Left: `Esc` hint with a kbd-styled chip
- Right: primary "Listo" button that closes the modal
- No global save button — saves happen per section (see §3.4)

### 3.3 Accordion structure

Three section breadcrumbs (small uppercase labels), each containing 1–2 accordion rows:

| Breadcrumb | Rows |
|------------|------|
| **Mi plan** | Meta de ahorro · Gasto personal · Día de pago |
| **Hogar** | Aporte al hogar |
| **Categorías** | Topes por categoría |

**Row anatomy (collapsed):**

```
[icon-tile 42×42]  LABEL (uppercase, muted, 10.5px)       [chevron ▸]
                   Current value (15px, 700, slate-900)
                      <unit in Geist Mono, 12px, muted>
```

- Icon tile: `42×42`, `rounded-xl`, `bg-gradient-to-br from-[#EFF6FF] to-[#DBEAFE]`, icon in `luka-primary`. Icons per row:
  - Meta de ahorro → `Target`
  - Gasto personal → `User`
  - Día de pago → `Calendar`
  - Aporte al hogar → `Home`
  - Topes por categoría → `Grid3x3`
- Value renders:
  - Meta de ahorro: `$300.000` + `CLP / mes` unit (or `Sin meta` italic when null)
  - Gasto personal: `$200.000` + `CLP / mes` unit (or `Sin monto`)
  - Día de pago: `Día 5` + `de cada mes` unit (or `Sin configurar`)
  - Aporte al hogar: `Completa` / `Fija ($800.000 CLP)` / `Sólo reembolso` + short descriptor unit
  - Topes por categoría: `{N} topes activos` + `${total} cubiertos` unit (or `Sin topes`). `{N}` and `${total}` are computed from the *last-saved* `["category-budgets", householdId, month]` query response, not from the in-flight draft. The summary only updates after a successful save — the user doesn't see a flickering total while typing.
- Chevron is a `ChevronRight` that rotates 90° on expand (260ms cubic-bezier `.2,.9,.25,1`)

**Row anatomy (expanded):**

- Row background: `linear-gradient(180deg, #F5F9FF 0%, rgba(245,249,255,0) 80%)`
- Left accent bar: absolute, `w-[3px]`, `top-3 bottom-3 left-1`, `bg-gradient-to-b from-[var(--luka-primary)] to-[var(--luka-sky)]`
- Body container: `display: grid; grid-template-rows: 0fr → 1fr` transition (pure-CSS smooth height animation, GPU-accelerated — no measurement, no JS)
- Body inner padding: `pt-1 pb-4 pl-[72px] pr-4` (aligned to the label column)
- Each body has its own Guardar button (see §3.4)

Only one row can be expanded at a time. Clicking another row collapses the current one. On modal open, the initial state is:

- If `needsSetup === true` (no savings target or payday), **Meta de ahorro** starts expanded (one row expanded).
- Otherwise, all rows start collapsed (zero rows expanded).

The auto-expand is a one-time nudge per open — if the user collapses it and then toggles it back, normal one-at-a-time behaviour resumes.

### 3.4 Save pattern

Each expanded row owns its own mutation and save button — no cross-row dirty state, no global save.

Behaviour:

1. User edits a field, clicks **Guardar** inside the row
2. Per-row mutation fires (existing API call — `updateBudgetSettings`, `updateContribution`, `setCategoryBudgets`)
3. On success:
   - Invalidate `["budgetSettings"]` and `["budget-v2", householdId]` (same invalidations as today) so the Sankey behind the modal updates live
   - Show a green "Guardado ✓" chip next to the button, fades in with `opacity 0 → 1` and `translateX(-4px → 0)` over 240ms
   - Auto-collapse the row after 900ms (gives the user time to see the confirmation). **The 900ms timer is cancelled if the user expands another row in the meantime** — otherwise a fast user would see row A collapse from under row B half a second after they opened B. The timer is also cancelled if the modal is closed.
4. On error:
   - Show `Error al guardar. Intenta de nuevo.` chip in `text-red-500`
   - Row stays expanded so the user can retry

This mirrors how the existing `BudgetSettingsSection` / `ContributionSection` / `CategoryBudgetsSection` already handle save — we port that logic, not invent it.

**Closing the modal without explicitly saving:** does NOT prompt a confirmation. Any unsaved edits in a row are discarded. This is the trade-off of the per-row save model, and it's acceptable because the only way to lose work is to edit a field and then click somewhere else — every other path (Guardar button, Listo button, Esc) either saves or respects the last-saved state. If this turns out to be a papercut in practice, we can add a "¿Descartar cambios?" confirm at close-time as a follow-up.

### 3.5 Category caps editor (the detail that matters)

Component: `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsEditor.tsx` (nested under the modal)

The inner-body of the Topes por categoría row.

#### Default state — list of active caps only

Render one row per category that currently has a cap (i.e., `amount > 0` from `getCategoryBudgets`). **Never render empty rows for uncapped categories.**

Row anatomy:

```
[32×32 cat-pill gradient]  Category name (13.5px, 500)    [number input, Geist Mono]   [× remove]
                           Gastado: $182.000 (10.5px muted, sub-line)
```

- Cat-pill color: deterministic per category (hash of category name → one of 5 gradient themes: amber/green/pink/blue/purple). Emoji inside is decorative; if no emoji mapping exists, use the first uppercase letter of the category name.
- The "Gastado: $X" sub-line pulls from the existing `budget-v2` query already loaded on the page. Specifically, from the Sankey nodes where `id === spent_{category}`. No new API call.
- Remove button: small × icon, `w-6 h-6`, `text-slate-400`, `hover:bg-red-50 hover:text-red-600`. Click = remove this category from the local draft; saving will submit the list without it.
- Input is right-aligned, Geist Mono 12.5px, `bg-slate-50` → focus `bg-white + ring`.

Below the list, a dashed "+ Agregar tope" button:

```
[+] Agregar tope        (dashed border slate-300, text luka-primary, hover solid border)
```

Below that, a helper line: "Sólo se muestran las categorías con tope activo. Toca + Agregar tope para incluir otra."

**Empty state (no caps yet):** the list is empty, only the add button and a friendly one-liner show. No faux list, no "You haven't set any caps" card.

#### Picker popover

Clicking "+ Agregar tope" opens a popover anchored inside the accordion body (NOT a nested modal — just an expanding card below the button).

Popover structure:

1. **Search bar** — magnifying glass icon + `<input placeholder="Buscar categoría…" />`, 13.5px, transparent border, auto-focused on open. Filters both sections by case-insensitive substring.
2. **Section: "Sugeridas · top 5 gasto del mes"** — top 5 expense categories by spend this month from the `budget-v2` Sankey data, excluding categories already in the caps list. Rank badge `top 1/2/3/4/5` in luka-primary, monetary amount on the right in Geist Mono. Row background has a subtle `linear-gradient(90deg, rgba(37,99,235,0.04), transparent)` highlight.
3. **Section: "Otras"** — all remaining expense categories not in the caps list and not in the top 5, sorted by spend descending (then by `user_category_preferences.sort_order` for zero-spend). Spend amount if >0, `—` if zero.
4. **Footer:** `{N} categorías restantes · enter para seleccionar` (with `{N}` being total not-yet-capped count)

**Interaction:**

- Click a picker row → the row animates into the caps list (new `.cap-row` with a `0.98 → 1` scale-in), input is pre-focused with `placeholder="Tu tope"`, and the popover closes
- Keyboard: arrow keys navigate, Enter selects (follow-up; v1 can be click-only)
- Clicking outside the popover (but still inside the accordion body) closes it

**Max height:** `max-h-72` with `overflow-y-auto` on the popover body, so long category lists don't push the Guardar button out of view.

#### Save

The "Guardar topes" button in the caps row submits *all* active caps (including any that were edited but not removed, minus any that were removed, plus any newly added). This is exactly what the existing `setCategoryBudgets` endpoint already does — it's a full-replace on the list. No incremental add/remove API needed.

### 3.6 Visual detail summary (for the implementer)

| Element | Spec |
|---------|------|
| Font, body | DM Sans (already loaded via `--font-dm-sans`) |
| Font, monetary units | Geist Mono (already loaded via `--font-geist-mono`), weight 500, 12px |
| Primary color | `var(--luka-primary)` `#2563EB` |
| Expanded row bg | `linear-gradient(180deg, #F5F9FF 0%, rgba(245,249,255,0) 80%)` |
| Expanded row accent | `linear-gradient(180deg, var(--luka-primary), var(--luka-sky))` `3px` width |
| Icon tile | `42×42`, `rounded-xl`, `linear-gradient(135deg, #EFF6FF, #DBEAFE)` |
| Modal shadow | `0 24px 64px -16px rgba(15,23,42,0.22), 0 8px 24px -12px rgba(15,23,42,0.10)` |
| Modal enter anim | 340ms `cubic-bezier(.2,.9,.25,1.2)` pop-in |
| Accordion body anim | 280ms `cubic-bezier(.2,.9,.25,1)` grid-rows `0fr → 1fr` |
| Chevron rotation | 260ms, 0 → 90deg, tints to luka-primary on expand |
| Saved chip | 240ms, `opacity+translateX` fade-in, `text-emerald-600` |

---

## 4. Data flow & state

### 4.1 Data the modal needs

| Source | Query key | Existing or new? |
|--------|-----------|------------------|
| `budgetSettings` (savings target, payday, personal allocation) | `["budgetSettings"]` | existing, used by `BudgetSettingsSection` today |
| Current user / contribution mode | `["me"]` + household-member contribution fields | existing — `useQuery(["me"])` already loaded in `budgets/page.tsx` |
| Category budgets for the month | `["category-budgets", householdId, month]` | existing, used by `CategoryBudgetsSection` today |
| Category preferences (expense list, sort order) | `["category-preferences"]` | existing |
| Per-category spend this month | derived from the `["budget-v2", householdId, monthStr, currency, "household"]` query already loaded on the page (read the `spent_{cat}` Sankey nodes) | **no new call** |

No new backend endpoints. No new query hooks. The modal imports `api.*` functions the old sections already called.

### 4.2 Local state (per row)

- **Meta de ahorro:** `amount: string, currency: string` — seeded from `budgetSettings.savings_target_amount / savings_target_currency`
- **Gasto personal:** `amount: string` — seeded from `budgetSettings.personal_allocation_amount`
- **Día de pago:** `day: string` — seeded from `budgetSettings.payday_day_of_month`
- **Aporte al hogar:** `mode: "full"|"fixed"|"reimbursement", fixedAmount: string, fixedCurrency: string` — seeded from `me.contribution_mode / contribution_fixed_amount / contribution_fixed_currency`
- **Topes por categoría:** `draft: Record<string, string>` — seeded from `categoryBudgets.budgets[]` (category → amount), plus a `pickerOpen: boolean`

### 4.3 Mutations

| Row | API call | Invalidates |
|-----|----------|-------------|
| Meta de ahorro / Gasto personal / Día de pago | `api.updateBudgetSettings(...)` | `["budgetSettings"]`, `["budget-v2"]` |
| Aporte al hogar | `api.updateContribution(...)` | `["me"]`, `["household-summary"]`, `["budget-v2"]` |
| Topes por categoría | `api.setCategoryBudgets(householdId, {month, budgets})` | `["category-budgets", householdId, month]`, `["budget-v2", householdId]` |

These are the exact invalidation sets the old settings components already use. Copy them over.

---

## 5. Removal of old settings sections

In `frontend/app/(dashboard)/settings/page.tsx`, delete the imports and render calls for:

- `BudgetSettingsSection`
- `ContributionSection`
- `CategoryBudgetsSection`

Delete the component files:

- `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx`
- `frontend/app/(dashboard)/settings/components/ContributionSection.tsx`
- `frontend/app/(dashboard)/settings/components/CategoryBudgetsSection.tsx`

The `CategoriesSection` (category order drag-and-drop) stays on settings — it's not a budget config, it's a global preference.

**Query-hook relocation:** the `["category-budgets", householdId, month]` and `["budgetSettings"]` query calls currently live inline inside the section component files that are being deleted. When the sections are removed, those query calls must be **relocated into the new modal**, not lost. The plan should ensure the modal mounts these queries (either inline or via a shared `useBudgetConfig` hook) before the old section files are deleted, so there's never a commit where the queries are orphaned.

The final `/settings` surface is: Profile · Transactions config · Bank accounts · Compartido · Notifications · Categories · Privacy · Delete account. Nothing budget-related.

---

## 6. Accessibility

- Modal is a proper `role="dialog"` with `aria-modal="true"` and `aria-labelledby` pointing at the header title
- `Esc` closes the modal (existing pattern — see `MarkAsCuotaDialog`)
- Focus is trapped inside the modal while open (use `focus-trap-react` if available, otherwise the shadcn `Dialog` primitive which handles this)
- On open, focus lands on the close button (safe default that doesn't commit accidental input)
- Each accordion row is a `<button>` (not a div) with `aria-expanded={isExpanded}` and `aria-controls={bodyId}`
- Section breadcrumbs are `<h3>`s so screen readers get structure
- Category picker: `role="listbox"`, picker items `role="option"`

**Keyboard scope for v1:** the modal-level keyboard contract is required (Tab through controls, Esc closes, Enter on an accordion button toggles expand/collapse, focus trapped inside). Picker-internal arrow-key navigation and Enter-to-select are a **follow-up**; v1 ships with click-only picker interaction. This split lets us hold the modal to a proper a11y baseline without making picker keyboard flow a blocker.

---

## 7. Testing

Frontend has no test infrastructure (confirmed via NEXT-STEPS.md "No frontend test infrastructure"), so verification is type-check + manual UAT, not unit tests.

**Type-check gate:**

- `cd frontend && npm run build` must pass with zero new TS errors.

**Manual UAT checklist (run locally with `npm run dev`):**

1. Open `/budgets` as a user with no savings target → gear button shows the blue dot
2. Click gear → modal opens, `Meta de ahorro` row auto-expands (first-open nudge)
3. Enter 300000, click Guardar → "Guardado ✓" chip appears, row collapses after ~900ms, Sankey behind the modal updates the `Meta de ahorro` node
4. Blue dot on gear disappears (because savings target is now set)
5. Expand Aporte al hogar, switch to "Fija", enter 800000, Guardar → verify the hogar Sankey node renders as "Contribución fija" in the personal view for the other household member
6. Expand Topes por categoría with zero existing caps → only the `+ Agregar tope` button is visible (empty state)
7. Click `+ Agregar tope` → picker opens with "Sugeridas · top 5" showing the 5 highest-spend categories from the current month
8. Click Supermercado → new cap row appears pre-focused, popover closes
9. Enter 250000, click Guardar topes → Sankey `spent_supermercado` link reflects the new cap (colored according to risk)
10. Click × on an existing cap → row disappears, click Guardar topes → cap is gone from the next `getCategoryBudgets` response
11. Repeat 6–10 on iPhone viewport (375×812): modal becomes a bottom sheet, slides up, scrollable body, same content
12. Go to `/settings` → no budget-related sections visible; the page still renders without errors
13. Keyboard-only: tab through modal, Esc closes, enter on an accordion row toggles expansion

---

## 8. Design decisions (why not X?)

**Why not tabs inside the modal?** Tabs hide content behind clicks. With only 5 rows across 3 groups, a single-column accordion with breadcrumb labels gives the same structure with zero click-cost on initial scan. (Considered and rejected in brainstorming option B.)

**Why not inline on the budget page (no modal)?** Would push the personal Sankey far below the fold and clutter the primary visualization. The budget page is a "viewing" surface; config belongs in a focused edit surface. (Considered and rejected in brainstorming option D.)

**Why not context menus on individual Sankey nodes?** Would be discoverable only by power users, requires wiring click handlers on every rect node in `BudgetSankey.tsx`, and produces two parallel UX entry points to maintain. Re-evaluate once the gear-button modal is live and there's usage data. (Brainstorming option C, deferred.)

**Why per-row save instead of a global save button?** The old settings sections already work per-row; reusing their mutation code is cheaper than rebuilding it around a unified dirty-state reducer. It also makes "change one thing and close" feel instant instead of "change, click save at the bottom, close."

**Why not show all 20 category caps with empty inputs?** The original design. User feedback in brainstorming was that empty rows create scan fatigue — the thing the user wants (their active 3 caps) is buried in a list of 17 unset rows. The "list active + picker for new" pattern puts the user's current config first and makes adding new caps a deliberate, ranked choice.

**Why derive "top 5 spent" from the existing `budget-v2` query instead of a new endpoint?** The data is already on the page. The Sankey response has a `spent_{category}` node for every expense category with nonzero spend this month. Reading from the existing query = zero new API surface, zero new cache key, and consistent with whatever month/currency the page is already showing.

**Why Geist Mono for monetary units only?** Gives tabular precision where numbers matter and introduces a single polished font pairing without making the whole modal feel "developer-toolish". Both fonts are already loaded via the root layout — no new dependencies.

**Why does the gear button get a blue dot instead of a prominent "Set up your budget" banner?** Banners interrupt the primary visualization. A single 7px dot on a pre-existing button is the smallest nudge that still reads as "something needs attention" to a first-time user. If usage data shows the dot isn't enough, we upgrade to a tooltip or first-visit pop-over as a follow-up — not to a banner.

**Why doesn't closing the modal with unsaved edits show a confirmation?** Per-row save is the intended model; any unsaved edit in an expanded row is an interrupted save, not an accidental loss. A confirmation would punish the common case (user edited, clicked Guardar, then clicked Listo) to protect the rare case (user edited, clicked Listo without saving). If UAT reveals this is confusing, we add a dirty-state check at close-time.

---

## 9. Known limitations

- **Picker spend ranking uses household view only.** The "top 5 spent" suggestions are drawn from the `view=household` budget-v2 query. When the user is in `view=personal`, the ranking still reflects household spend (which is what the caps affect, since category_budgets are household-level). Documented here so it doesn't surprise a future reviewer.
- **Deterministic cat-pill color** is hash-based, not user-configurable. If two categories collide on the same gradient it's visually fine — the gradient is decorative, not semantic.
- **Emoji icons on cat-pills are a frontend-only mapping.** A small dict (`ICONS.ts`) maps the default-seed expense categories to an emoji. Custom user categories fall back to a first-letter pill. The mapping lives in `frontend/app/lib/categoryIcons.ts` and is additive-only.
- **Contribution-mode "Fija" currency picker** duplicates what's on `BudgetSettingsSection`. Both live in the same modal now, so it's consistent — but if a user wants their savings target in USD and their contribution in CLP, they can do that today and we shouldn't force parity.

---

## 10. Rollout

Single-PR rollout, frontend-only:

1. Add `BudgetConfigModal` + `CategoryCapsEditor` + the gear button to `/budgets`
2. Remove the three sections from `/settings/page.tsx` and delete their files
3. Add the category-icons dict
4. `npm run build` + manual UAT per §7
5. Ship

No feature flag — this is a non-destructive UX move (same endpoints, same data model) that's cheap to revert by reintroducing the settings sections if UAT flags something unexpected.
