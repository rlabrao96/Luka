# Budget Page Redesign — Design Spec

**Date:** 2026-04-14
**Status:** Draft — pending spec review and user approval
**Target ship:** 1-week sprint, parallelized across 6–8 subagents
**Author:** Brainstorm session with Rafael (product) + Claude (design)

## 1. Context & Problem

### 1.1 What exists today
The current `/budgets` page (`frontend/app/(dashboard)/budgets/page.tsx`) renders:
- Month selector
- Income card
- Pace chart (daily cumulative vs straight-line pace)
- 50/20/30 allocation card
- Waterfall cards

The backend (`backend/modules/budgets/personal_service.py`) computes a personal ceiling, a waterfall breakdown, and a pace block, all scoped by currency when the caller passes one.

### 1.2 Why it's not valuable
The page is **descriptive only** — it reports what happened. It doesn't:
- Prevent overspend (there are no category-level caps or alerts)
- Handle multi-currency users (the `CLP()` formatter is hardcoded on line 16 regardless of the user's `preferred_currency`)
- Support the single most common Chilean overspend cause: **cuotas** (installment purchases)
- Give couples a **privacy-preserving** way to share a household budget without disclosing individual income
- Carve out known bills, subscriptions, or savings before computing "spendable" — so the user sees an income number that's not actually spendable
- Stay silent by default — the pace chart is always loud even when nothing is wrong

### 1.3 Why now
The user explicitly said the page "is not useful" and asked for a redesign that makes household + personal budgeting "a billion-dollar idea". They want a working v1 in one week, parallelized across agents.

---

## 2. Goals & Non-Goals

### 2.1 Goals (ranked, from the brainstorm)
1. **Prevent overspend** (job A) — active guardrails, silent by default, speak up only when a category genuinely risks overshooting
2. **Clarity** (job C) — a beautiful Sankey flow showing income → buckets → leftover, so users understand at a glance where money is going
3. **Savings as a first-class bucket** (job B, third priority) — carved out *before* spendable, not as leftover

### 2.2 Explicit non-goals for v1 (and why)
- **Couple conflict resolution / fairness negotiation** — Luka doesn't take sides. The contribution-mode feature solves privacy, not fairness.
- **Cash forecasting across multiple future months** — v1 is this-month-only. Cuota-aware future projection is Phase 2.
- **Goal-based savings (YNAB-style named goals)** — v1 ships with a single monthly savings target. Named goals are Phase 2.
- **Deep ML / training pipelines** — Bayesian hierarchical math has the right shape, and we ship a simpler heuristic variant first.
- **Cuota auto-detection from email parsing** — v1 is manual entry only. Auto-detection from the email parser is Phase 2.

---

## 3. Core Philosophy

**The page's one-sentence promise:**
> "The big number on this page is money you can actually spend this month. Everything already promised — rent, subscriptions, cuotas, your savings target — is already carved out. If a category is at risk, we'll tell you. Otherwise, we stay quiet."

**Three principles that drive every decision:**

1. **Silent by default.** No notifications, no alerts, no color changes unless something actually threatens the month. Notification fatigue is the #1 killer of budget apps; Luka earns the right to speak by staying quiet until it matters.
2. **Honest spendable.** The centerpiece number is not "income" — it is income minus known bills, minus cuotas, minus the savings target. What's left is *actually* discretionary. This is what "don't let me overspend" requires mathematically.
3. **Household waterfall.** You first pay the home, then yourself. Household section stacks above Personal. This matches how Chilean couples reason about money and makes the Sankey story crisp.

---

## 4. User Experience

### 4.1 Page layout (stacked, single page)

```
┌────────────────────────────────────────────────┐
│ Presupuesto                                     │
│ [< Abril 2026 >]             [CLP | USD] toggle │ ← toggle auto-hidden if single currency
├────────────────────────────────────────────────┤
│ ⚠️ Risk alert band (only if triggered)           │ ← silent when empty
├────────────────────────────────────────────────┤
│ HOGAR                                            │
│  Sankey: Household income → Shared bills →      │
│          Household cuotas → Savings →            │
│          Shared spendable                        │
│                                                  │
│  [Household spendable card]  [Runway card]      │
│  [Risk categories row]                           │
├────────────────────────────────────────────────┤
│ PERSONAL                                         │
│  Sankey: Personal income (or residual after     │
│          household contribution) → Personal     │
│          bills → Personal cuotas → Savings →    │
│          Personal spendable                     │
│                                                  │
│  [Personal spendable card]  [Runway card]       │
│  [Risk categories row]                           │
└────────────────────────────────────────────────┘
```

The two sections are visually distinct but share the same component set. For individual households, the "Hogar" section collapses to just show the full Personal view.

### 4.2 The Sankey

Centerpiece visual. Rendered via Recharts' Sankey primitive.

**Streams (nodes):**
- **Income** (leftmost)
- **Known bills** (rent, utilities, insurance, subscriptions detected by the existing subscriptions module)
- **Cuotas del mes** (sum of active cuota installments due this month)
- **Meta de ahorro** (savings target, carved out before spendable)
- **Spendable** (what's actually discretionary)
- **Risk categories** (top 3–5, auto-picked) as red-tinted sub-streams of spendable
- **Everything else** as a neutral "Otros gastos" stream

**Visual rules:**
- Known bills stream is **always visible** even when $0 (so users understand the carve-out model)
- Cuotas stream only appears when the user has active cuotas
- Risk categories stream turns red when any category has `alert: true`
- All numbers are currency-scoped to the active toggle value

### 4.3 Risk alert band (job A intervention)

Yellow band at the top of the page, **hidden when empty**. Appears only when one or more risk categories have `p_overshoot > 0.70`.

Example copy:
> "⚠️ **Restaurantes** va al 73% de su límite con 12 días por delante. Al ritmo actual, el mes cerraría en **$240k** (límite: $185k)."

Maximum 3 entries, most severe first. No stacking, no modal — just an inline band that the user scrolls past.

### 4.4 Runway card (job A)

Small card on each section (Household, Personal):
```
┌─────────────────────────┐
│ Próximo sueldo: 12 días │
│ Runway actual: 8 días   │  ← red when runway < days_to_payday
└─────────────────────────┘
```

v1: `days_to_payday` is read from a new Settings field (user enters their payday day-of-month). Auto-detection from income history is Phase 2.

### 4.5 Currency toggle

A `CLP | USD` segmented control at the top of the page. Auto-hidden when the user has transactions in only one currency this month. Tapping the toggle re-queries every aggregate in the active currency.

### 4.6 Settings additions

**New Settings section: "Presupuesto"**
- Savings target (amount + currency, per month)
- Payday day-of-month (1–31)
- Risk category sensitivity — **not user-facing in v1**, hardcoded to `P > 0.70`

**New Settings section: "Contribución al hogar"** (only shown for couples)
- Radio group: `Completa` / `Fija` / `Sólo reembolso`
- If Fija: amount + currency inputs
- Copy explains what each mode does and what the partner sees

---

## 5. Data Model Changes

### 5.1 New columns on `household_members`

| Column | Type | Default | Purpose |
|---|---|---|---|
| `contribution_mode` | `enum('full','fixed','reimbursement')` | `'full'` | How this member shows up in the household budget |
| `fixed_contribution_amount` | `numeric(14,2) NULL` | `NULL` | Used only when mode=`fixed` |
| `fixed_contribution_currency` | `char(3) NULL` | `NULL` | Currency for the fixed contribution |

**Semantics:**
- `full`: member's real personal-account income is summed into household total. Partner can see it via existing aggregate RPCs.
- `fixed`: partner sees only `fixed_contribution_amount` — real income is **never exposed** via any RPC or API response in the household view. The member's personal view still uses their real income.
- `reimbursement`: member contributes $0 to the household pot. Settlement logic (existing endpoint) tracks who paid what.

### 5.2 New table `user_budget_settings`

Savings target is **per-user, not per-household** (each member has their own savings discipline and their own target). The household Sankey's "Meta de ahorro" bucket is computed as the **sum of each active member's personal savings target** (full + fixed members; reimbursement members' target is optional and only affects their personal view). The personal Sankey's "Meta de ahorro" bucket is that user's own target.

This table also owns `payday_day_of_month` (§4.4 / Chunk H), so both Chunk F and Chunk H share a single schema location owned by Chunk 0.

| Column | Type | Default | Purpose |
|---|---|---|---|
| `user_id` | `uuid PK FK → users.id` | | One row per user |
| `savings_target_amount` | `numeric(14,2) NULL` | `NULL` | Monthly savings target |
| `savings_target_currency` | `char(3) NULL` | `NULL` | Currency of the target |
| `payday_day_of_month` | `int NULL CHECK BETWEEN 1 AND 31` | `NULL` | Used by runway card |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | | |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | | |

`household_budget_allocations` is **not modified** by this spec. It continues to own the existing 50/20/30 percentages used by the legacy `/budgets/personal` endpoint, which stays in place for transition.

### 5.3 New table `cuota_purchases`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK` | |
| `user_id` | `uuid NOT NULL FK → users.id` | |
| `household_id` | `uuid NOT NULL FK → households.id` | For household-scoped queries |
| `origin_transaction_id` | `uuid NULL FK → transactions.id` | The original purchase tx when known |
| `merchant_name` | `text NOT NULL` | |
| `total_amount` | `numeric(14,2) NOT NULL` | Full purchase amount |
| `currency` | `char(3) NOT NULL` | |
| `installments_total` | `int NOT NULL CHECK > 0` | |
| `installments_paid` | `int NOT NULL DEFAULT 0` | |
| `monthly_amount` | `numeric(14,2) NOT NULL` | Computed: total / installments_total |
| `first_cuota_date` | `date NOT NULL` | |
| `last_cuota_date` | `date NOT NULL` | Computed: first + (installments_total - 1) months |
| `status` | `enum('active','completed','cancelled') DEFAULT 'active'` | |
| `split_type` | `enum('personal','shared') DEFAULT 'personal'` | So household cuotas show up in the household Sankey |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | |

**Indexes:**
- `(user_id, status)` — for the active-cuotas summary
- `(household_id, status)` — for household aggregate
- `(last_cuota_date)` — for future-month projection

### 5.4 New column on `categories` (or equivalent canonical category table)

| Column | Type | Default | Purpose |
|---|---|---|---|
| `counts_as_savings` | `boolean NOT NULL DEFAULT false` | `false` | Transactions in this category don't count against spendable; they count toward savings progress |

**Seed:** set `counts_as_savings=true` for the `Inversión` category. Future users can extend (e.g., APV, Aportes jubilación).

**Note:** Luka currently uses string-based category slugs on transactions rather than a `categories` table. If a central table doesn't exist, this flag lives as a hardcoded set in `backend/modules/transactions/categories.py` (or equivalent) that the forecast engine consults. Chunk 0 decides the exact location after code inspection.

### 5.5 Migration

Single Alembic revision:
1. Add columns to `household_members` and backfill `contribution_mode='full'`
2. Create `user_budget_settings` table (one row per existing user, all nullable fields NULL)
3. Create `cuota_purchases` table + indexes
4. Either add `counts_as_savings` to categories table, or create the hardcoded savings-category set in application code (Chunk 0 decides)
5. Seed `counts_as_savings=true` for `Inversión`

**No new `budget_risk_categories` table** — risk category sets are computed on the fly and cached in Redis.

---

## 6. Mathematical Model

### 6.1 Principle

Every number on the budget page is a **posterior prediction with uncertainty**, not a counter. The user sees point estimates; the engine reasons in distributions. This is what enables silent-by-default alerts: we fire only when the probability of overshoot crosses a calibrated threshold, not when arbitrary percentage-of-budget heuristics trip.

The full engine is **Bayesian hierarchical** with EWMA updates, day-of-month profile calibration, and population priors for cold-start. **v1 ships with the same function signatures but simpler heuristic implementations** — the frontend is unaware of the swap, so Phase 2 upgrades are invisible.

### 6.2 v1 primitives (ship in days)

All primitives live in `backend/modules/budgets/forecast.py` as pure functions, unit-tested with synthetic data.

**Historical category mean (3-month arithmetic):**
```
μ(u,c) = mean(monthly_spend_u_c[t-3 : t-1])
```

**Historical variance (3-month sample std):**
```
σ(u,c) = stddev(monthly_spend_u_c[t-3 : t-1])
```

**Cold-start handling:** if `n_months_history < 1`, return `null` for risk categories and display a message: "Luka necesita 1 mes de datos para calcular categorías de riesgo."

**Risk category scoring — share × CV:**
```
R(u,c) = (μ(u,c) / Σ_c' μ(u,c')) × (σ(u,c) / μ(u,c))
```
Select the top 5 by `R`. Cached in Redis under `budget:risk:{user_id}:{YYYY-MM}` with month-long TTL to keep the set stable within a month.

**Category cap:** the 75th percentile of historical monthly spend for that category (computed from the same 3-month window), or a user override if set.

**Known bills (deterministic source of truth):**

`known_bills` for a given `(user_or_household, month, currency)` is **exclusively the output of the existing subscriptions module** (`backend/modules/subscriptions/`). v1 does not add a separate bills concept — if a user wants rent to be carved out, they mark it as a subscription in the existing subscriptions UI (rent is already detected automatically as a recurring expense by the subscriptions pre-cache cron).

```
known_bills = Σ subscription.monthly_amount
  where subscription.user_or_household matches the view scope
    AND subscription.currency = currency
    AND subscription.active_in_month(month) = true
```

**Pace prediction (v1 linear, with early-month guard):**
```
effective_day = max(current_day, 3)
Ŝ(u,c) = spent_so_far × (days_in_month / effective_day)
```
The `max(·, 3)` guard suppresses nonsensical projections in the first days of the month (day 1 would otherwise multiply by `days_in_month` and trigger false alerts on every category). As a result, **risk alerts are effectively suppressed for the first 3 days of each month** — this is intentional and documented.

**Overshoot probability (v1 flat-variance Normal):**
```
P(overshoot_c) = 1 - Φ((cap - Ŝ) / σ(u,c))
```
where `Φ` is the standard Normal CDF. We use the *historical* variance flat — we don't shrink it by the fraction of month remaining. (Phase 2 adds the shrinkage factor `sqrt(1 - d/D)`.)

**Alert threshold:** `P(overshoot) > 0.70`. Static in v1, calibrated on production data later.

**Runway:**
```
daily_burn_14 = (Σ last 14 days of spending) / 14
runway_days = spendable_remaining / daily_burn_14
```
Alert if `runway_days < days_to_payday`.

**Cuotas this month:**
```
cuotas_this_month = Σ cp.monthly_amount
  where cp.status = 'active'
    AND cp.first_cuota_date <= month_end
    AND cp.last_cuota_date >= month_start
```

**Cuotas future commitment:**
```
cuotas_future_total = Σ cp.monthly_amount × (cp.installments_total - cp.installments_paid)
  where cp.status = 'active'
```

**Spendable ceiling and remaining (the heart of the page):**

Two distinct concepts — the **ceiling** (how much the user can spend this month) and the **remaining** (how much is left after what's been spent).

```
spendable_ceiling = income - known_bills - cuotas_this_month - savings_target
spendable_spent   = Σ expenses where category.counts_as_savings = false
                      AND transaction_type != 'transfer'
spendable_remaining = spendable_ceiling - spendable_spent
pct_used = spendable_spent / spendable_ceiling   (when ceiling > 0)
```

The API response (§7.1) maps these directly: `spendable.amount = spendable_ceiling`, `spendable.spent = spendable_spent`, `spendable.remaining = spendable_remaining`, `spendable.pct_used = pct_used`.

Investment-categorized transactions (`counts_as_savings=true`) are **excluded from `spendable_spent`** and instead counted toward `savings_target.progress`.

**Personal vs household income source (per contribution mode):**

The spendable formula above takes `income` as an input. That input differs between the two views and by contribution mode:

| View | Contribution mode | `income` value used in the formula |
|---|---|---|
| `personal` | any mode | The caller's **real personal income** (from the caller's personal accounts, that currency, that month) |
| `household` | `full` | Σ real personal income of all `full` members |
| `household` | `fixed` | `fixed_contribution_amount` of each `fixed` member (their real income never appears) |
| `household` | `reimbursement` | `0` for each `reimbursement` member; settlement is handled by the existing settlement endpoint |

**The Personal Sankey always starts from the caller's real income**, regardless of contribution mode. When the caller is in `full` or `fixed` mode, their contribution to the household pot appears as an **explicit outflow node** ("Aporte al hogar") in the Personal Sankey — symmetric to how rent or cuotas appear. For `full` mode, the outflow is the member's real income routed to household (since all of it goes to the pot when fully merged); for `fixed`, it's `fixed_contribution_amount`; for `reimbursement`, there is no such outflow node. This makes the waterfall explicit in every mode.

### 6.3 Phase 2 upgrade path (written into spec so the future session knows what to swap)

Same function signatures, swap internals:

| Primitive | v1 | Phase 2 |
|---|---|---|
| `μ` | 3-month arithmetic mean | EWMA with α=0.293 (2-month half-life) |
| `σ` | 3-month sample std | EWMA of squared residuals |
| cold start | null + message | Hierarchical prior with population blend `λ(n) = 1 - e^(-n/3)` |
| population prior | none | Cross-user aggregation per `(country, income_band, category)`, refreshed weekly via cron |
| pace prediction | linear | Day-of-month profile `P_c(d/D)` smoothed with Beta prior |
| overshoot variance | flat historical | Shrinking: `σ × sqrt(1 - d/D)` |
| alert threshold | static 0.70 | Per-user calibration from true-overshoot rate |

Frontend contract is stable across both.

### 6.4 Interpretability (v1 partial, Phase 2 full)

v1 ships with one "why this number?" tooltip on the risk alert band only. Phase 2 adds tooltips to every number. Example copy (Phase 2):
> "Tu límite de Restaurantes es $185k porque gastaste en promedio $192k/mes los últimos 3 meses. Este mes vas en $142k al día 18 de 30, con 73% de probabilidad de superar el límite al ritmo habitual."

---

## 7. Backend API

### 7.1 New endpoint

```
GET /budgets/v2/{household_id}?month=YYYY-MM-DD&currency=CLP&view=household|personal
```

**Request params:**
- `month` (required): first-of-month date
- `currency` (optional, default = user's preferred_currency): CLP or USD
- `view` (required): `household` or `personal`

**Caller scoping:** `view=personal` **always** returns the budget for the **authenticated caller**. There is no `user_id` query param — a household member cannot query another member's personal view under any circumstance. The `household_id` in the path is used only to verify the caller belongs to that household and to resolve household-scoped settings.

**Contract guarantee:** when `risk_categories[i]` has `alert: true`, the corresponding `sankey.nodes` entry for that category is tagged `risk: true` and the two payloads are always consistent (computed from the same underlying query in the same request). Chunk B consumes both as a trusted pair and does not re-derive one from the other.

**Response payload (shared shape for both views):**
```json
{
  "view": "personal",
  "month": "2026-04-01",
  "currency": "CLP",
  "sankey": {
    "nodes": [
      {"id": "income", "label": "Ingresos", "value": 1800000},
      {"id": "known_bills", "label": "Gastos fijos", "value": 520000},
      {"id": "cuotas", "label": "Cuotas del mes", "value": 120000},
      {"id": "savings_target", "label": "Meta de ahorro", "value": 300000},
      {"id": "spendable", "label": "Disponible", "value": 860000},
      {"id": "spent_restaurants", "label": "Restaurantes", "value": 142000, "risk": true},
      {"id": "spent_groceries", "label": "Supermercado", "value": 180000, "risk": true},
      {"id": "spent_other", "label": "Otros", "value": 95000}
    ],
    "links": [
      {"source": "income", "target": "known_bills", "value": 520000},
      {"source": "income", "target": "cuotas", "value": 120000},
      {"source": "income", "target": "savings_target", "value": 300000},
      {"source": "income", "target": "spendable", "value": 860000},
      {"source": "spendable", "target": "spent_restaurants", "value": 142000},
      {"source": "spendable", "target": "spent_groceries", "value": 180000},
      {"source": "spendable", "target": "spent_other", "value": 95000}
    ]
  },
  "spendable": {
    "amount": 860000,
    "spent": 417000,
    "remaining": 443000,
    "pct_used": 0.485
  },
  "risk_categories": [
    {
      "name": "Restaurantes",
      "spent": 142000,
      "cap": 185000,
      "historical_mean": 192000,
      "historical_std": 34000,
      "p_overshoot": 0.73,
      "projected_final": 240000,
      "alert": true
    }
  ],
  "runway": {
    "days_remaining": 8,
    "days_to_payday": 12,
    "daily_burn_14d": 55000,
    "alert": true
  },
  "cuotas": {
    "this_month": 120000,
    "future_total": 2100000,
    "active_count": 4
  },
  "savings_target": {
    "target": 300000,
    "progress": 142000,
    "pct_complete": 0.473
  }
}
```

### 7.2 Existing endpoints

The current `GET /budgets/personal/{household_id}` endpoint **stays in place** for the v1 transition and is marked deprecated. The frontend switches to `/budgets/v2/` for the new page. Once everything is green, the old endpoint is removed in a follow-up PR.

### 7.3 Contribution-mode aware aggregation

When `view=household` and any member has `contribution_mode='fixed'`, the endpoint:
- Replaces that member's real income contribution with their `fixed_contribution_amount`
- Omits their personal-spend breakdown from the household payload entirely (personal spend stays private)
- Their shared-split expenses still show up in household spending (they're using the shared pot)

When `view=household` and any member has `contribution_mode='reimbursement'`, that member contributes **$0** to the household pot. Settlement details are served by the existing settlement endpoint.

When `view=personal` for a `fixed`-mode caller, **the caller's own real income is used** in their personal budget — the fixed-contribution restriction only suppresses income disclosure to *other* household members via `view=household`, never to the caller themselves. The caller's personal Sankey shows the `fixed_contribution_amount` as an outflow node (labeled "Aporte al hogar"), matching the rule in §6.2.

**Privacy enforcement** happens in the service layer, not the router. RLS on the underlying tables continues to protect raw rows. The aggregate service is updated to respect `contribution_mode` and is responsible for redacting fixed-mode income from every `view=household` response shape.

### 7.4 New CRUD endpoints

```
POST   /cuotas           Create a cuota purchase
GET    /cuotas           List active cuotas (filterable by household view)
PATCH  /cuotas/{id}      Update (mainly to cancel or edit)
DELETE /cuotas/{id}      Delete
```

Simple service layer in `backend/modules/budgets/cuota_service.py`.

```
PATCH  /settings/budget        Update user_budget_settings (savings_target_amount, currency, payday_day_of_month)
PATCH  /settings/contribution   Update household_members contribution_mode + fixed_contribution_amount + currency
```

Both endpoints are scoped to the authenticated caller. `/settings/budget` writes to `user_budget_settings`; `/settings/contribution` writes to the caller's own row in `household_members` (a member cannot change another member's contribution mode).

---

## 8. Frontend Architecture

### 8.1 New files

```
frontend/app/(dashboard)/budgets/
  page.tsx                          (rewritten)
  components/
    BudgetSankey.tsx                 (Recharts Sankey wrapper)
    SpendableCard.tsx                (big number + sparkline)
    RiskCategoryRow.tsx              (list of risk categories with cap bars)
    RiskAlertBand.tsx                (yellow alert band, silent when empty)
    RunwayCard.tsx                   (days-to-payday + runway days)
    CurrencyToggle.tsx               (segmented CLP|USD, auto-hidden)
    HouseholdBudgetSection.tsx       (wraps Sankey + cards for household view)
    PersonalBudgetSection.tsx        (wraps Sankey + cards for personal view)

frontend/app/lib/hooks/
  useBudgetV2.ts                     (replaces useBudget)
  useCuotas.ts                       (cuota CRUD)
  useBudgetSettings.ts               (savings target, payday, contribution mode)

frontend/app/lib/format.ts
  formatMoney(amount, currency)      (replaces hardcoded CLP() helper)
```

### 8.2 Currency fix (the bug)

`formatMoney(amount: number, currency: 'CLP' | 'USD'): string`:
- CLP: `'es-CL'` locale, no decimals, `$` prefix, thousand separator `.`
- USD: `'en-US'` locale, 2 decimals, `$` prefix, thousand separator `,`

Every component on the budget page takes `currency` as a prop and calls `formatMoney` — no module-level formatter. The `CLP()` function is removed.

### 8.3 State management

- Zustand store adds `selectedCurrency` (persists to localStorage)
- TanStack Query hooks: `useBudgetV2({ householdId, month, currency, view })` with 30s `staleTime`
- The same hook is called twice on the page (once for household, once for personal)
- Invalidation: any transaction edit, settings change, or cuota CRUD invalidates `['budget-v2']`

### 8.4 Responsive behavior

- **Desktop:** two sections stacked, Sankey at full width
- **Tablet:** same layout, Sankey shrinks proportionally
- **Mobile:** Sankey rendered with horizontal scroll (Recharts Sankey doesn't reflow well at narrow widths); currency toggle moves to a bottom-sheet trigger

---

## 9. Implementation Chunks (parallelizable)

Each chunk is self-contained enough to run in a separate worktree with a dedicated subagent. Dependencies are explicit.

### Chunk 0 — Migrations & scaffolding **[blocker]**
- **Duration:** ~2 hours
- **Owner:** 1 agent, must complete before A–H start
- **Scope:**
  - Alembic revision for all schema changes in §5:
    - `household_members.contribution_mode / fixed_contribution_amount / fixed_contribution_currency` (with `contribution_mode='full'` backfill)
    - New `user_budget_settings` table (§5.2) — owns `savings_target_amount`, `savings_target_currency`, **and `payday_day_of_month`**
    - New `cuota_purchases` table + indexes (§5.3)
  - Decide `counts_as_savings` location (categories table vs hardcoded set in `backend/modules/transactions/categories.py` or equivalent)
  - Seed `counts_as_savings=true` for Inversión
  - Run locally against dev DB and verify clean rollback (`alembic downgrade -1`)

### Chunk A — Currency fix + page scaffolding
- **Duration:** ~1 day
- **Scope:**
  - Create `frontend/app/lib/format.ts` with `formatMoney`
  - Remove the hardcoded `CLP()` helper
  - Add `CurrencyToggle` component + `selectedCurrency` to Zustand
  - Rescaffold `/budgets/page.tsx` as two stacked sections (empty placeholders)
  - Auto-hide toggle when single-currency (check via `useQuery` on user's distinct currencies this month)
- **Parallel with:** everything after Chunk 0
- **Verifies:** currency bug fixed; page shell renders

### Chunk B — Sankey component
- **Duration:** ~1.5 days
- **Scope:**
  - `BudgetSankey.tsx` using Recharts Sankey primitive
  - Props: `{ nodes, links, currency }`
  - Mobile-responsive (horizontal scroll on narrow widths)
  - Color rules: neutral for bills/savings, red tint for risk categories, accent for spendable
  - Build a storybook-style dev page with fake data for iteration
- **Parallel with:** Chunks A, C, D, E, F

### Chunk C — Backend budget v2 endpoint
- **Duration:** ~2 days
- **Scope:**
  - New `GET /budgets/v2/{household_id}` endpoint (see §7.1 for the exact response shape)
  - New `backend/modules/budgets/forecast.py` with pure functions (v1 signatures, heuristic internals per §6.2):
    - `category_stats(user_id, category, db)` → `(mean, std, sample_size)`
    - `select_risk_categories(user_id, db)` → top 5 by share × CV
    - `pace_forecast(spent_so_far, day, days_in_month, std)` → `(projected, p_overshoot)` with `max(current_day, 3)` guard
    - `runway(spendable_remaining, daily_burn_14)` → `days`
    - `spendable_ceiling(income, known_bills, cuotas, savings_target)` → `amount` (does NOT subtract spent)
    - `spendable_spent(transactions, category_savings_set)` → excludes savings-categorized txns
  - `cuota_service.py` for cuota aggregates
  - `known_bills` computed from the **existing subscriptions module** (§6.2) — no new bills concept
  - Redis caching of risk category sets under `budget:risk:{user_id}:{YYYY-MM}`, month-long TTL
  - **Contract guarantee:** `risk_categories[i]` and the matching `sankey.nodes` entry are always computed in the same request from the same query and are consistent (§7.1)
  - **Day 1 deliverable before coding internals:** commit a fixture JSON file at `backend/tests/fixtures/budget_v2_sample_response.json` matching §7.1 exactly, so Chunks B, G, H can start against a fake before the endpoint is wired up
  - Unit tests with synthetic data (deterministic)
- **Parallel with:** Chunks A, B, D, E, F (after Chunk 0)
- **Note:** this chunk is the **critical path** — all frontend chunks consume its payload

### Chunk D — Contribution modes
- **Duration:** ~1 day
- **Scope:**
  - Backend: extend household aggregate service to honor `contribution_mode`
  - Backend: new `PATCH /settings/contribution` endpoint
  - Frontend: Settings panel section "Contribución al hogar" with 3-way radio + amount inputs
  - Frontend: `useBudgetSettings` hook
  - Privacy test: verify a fixed-mode member's real income is NOT exposed in any `view=household` response
- **Parallel with:** B, C, E, F

### Chunk E — Cuotas (manual entry only)
- **Duration:** ~1 day
- **Scope:**
  - Backend CRUD endpoints for `cuota_purchases`
  - `cuota_service.get_active_cuotas_summary(user_id, month)` → `{this_month, future_total, active_count}`
  - Integration into Chunk C's endpoint (exposes `cuotas` block)
  - Frontend: "Marcar como compra en cuotas" action in transaction detail view
  - Frontend: form (total amount pre-filled from tx, installments count, first cuota date)
  - Frontend: `useCuotas` hook for list/create/cancel
- **Parallel with:** B, C, D, F
- **Out of scope:** auto-detection from email parser (Phase 2)

### Chunk F — Savings target + investment-as-savings
- **Duration:** ~0.5 day
- **Scope:**
  - Backend: `PATCH /settings/budget` endpoint for `user_budget_settings.savings_target_amount / savings_target_currency` (and `payday_day_of_month`, shared with Chunk H)
  - Backend: forecast engine excludes `counts_as_savings=true` categories from `spendable_spent` and includes them in `savings_target.progress` (per §6.2)
  - Backend: household aggregate sums member savings targets per §5.2 rule
  - Frontend: Settings "Meta de ahorro" input (amount + currency)
  - Frontend: savings target rendered as a Sankey bucket, carved out of the ceiling before spendable
- **Parallel with:** B, C, D, E
- **Schema owned by:** Chunk 0 (`user_budget_settings` table)

### Chunk G — Risk alert band (inline intervention)
- **Duration:** ~0.5 day
- **Scope:**
  - `RiskAlertBand.tsx` reads `risk_categories` from the budget v2 response
  - Renders only entries with `alert: true`
  - Copy: "⚠️ [Category] va al X% de su límite con N días por delante. Al ritmo actual, el mes cerraría en $Y (límite: $Z)."
  - Silent when empty
- **Parallel with:** B (after Chunk C's endpoint shape is stable)

### Chunk H — Runway card
- **Duration:** ~0.5 day
- **Scope:**
  - `RunwayCard.tsx` with days-to-payday + runway days
  - Red styling when `runway_days < days_to_payday`
  - Payday source: `user_budget_settings.payday_day_of_month` (owned by Chunk 0 migration, written by Chunk F's `PATCH /settings/budget`)
  - Frontend: add payday input to the same Settings section as the savings target
- **Parallel with:** B, C, D, E, F, G
- **Schema owned by:** Chunk 0

### Out of scope in v1 (explicit Phase 2 chunks)
- **Chunk I (Sunday email recap)** — deferred entirely to Phase 2 per user decision
- Any cuota auto-detection
- Any day-of-month profile calibration
- Any population priors

---

## 10. Timeline (1-week sprint)

| Day | Parallelized work | Serial requirements |
|---|---|---|
| **Day 1 AM** | Chunk 0 (migrations) | Must complete first |
| **Day 1 PM → Day 3** | Chunks A, B, C, D, E, F in parallel across 6 agents; G and H start as soon as C's API contract is stable (Day 2) | None |
| **Day 4** | Merge + end-to-end integration testing against staging DB | All chunks merged |
| **Day 5** | User acceptance testing with real transactions (CLP, USD, mixed, couples, cuotas) + bug-fix pass | |
| **Day 6** | Frontend polish, copy review, mobile testing | |
| **Day 7** | Ship to production (Railway + Vercel) | |

**Critical path:** Chunk 0 → Chunk C → frontend chunks that consume Chunk C's payload (B, G, H).
**Non-critical parallel path:** A, D, E, F — each independent of C beyond the data model.

---

## 11. Testing Strategy

### 11.1 Backend unit tests
- `tests/test_forecast.py` — synthetic data generators produce known distributions; assert recovered means/stds/risk categories are within tolerance
- `tests/test_cuota_service.py` — cuota aggregates (this month, future total, edge cases around month boundaries)
- `tests/test_budget_v2_endpoint.py` — end-to-end with seeded DB fixtures
- `tests/test_contribution_modes.py` — **privacy test** uses a seeded fixture where the `fixed`-mode member's real income ($1,800,000) and their `fixed_contribution_amount` ($800,000) are **intentionally different values** so grep-level assertions are unambiguous. The test asserts (a) no field anywhere in the `view=household` JSON response (recursive walk) equals `1800000`, (b) the `income` field in the household view equals the sum of the other member's income plus `800000`, and (c) the personal-spend breakdown for the `fixed` member is absent from the household response entirely

### 11.2 Manual QA checklist (Day 5)
- [ ] CLP-only user sees correct formatter, no toggle
- [ ] USD-only user sees correct formatter, no toggle
- [ ] Mixed-currency user sees toggle, switching re-renders every number
- [ ] Individual household: no "Hogar" section, only "Personal"
- [ ] Couple household, both `full`: both incomes visible to both
- [ ] Couple household, partner in `fixed`: viewing partner sees only `fixed_contribution_amount`, never real income
- [ ] Couple household, partner in `reimbursement`: household pot shows $0 from that member
- [ ] Savings target set → carved out of spendable → Sankey shows bucket
- [ ] Investment-categorized tx counts toward savings progress, not spent
- [ ] Cuota created manually → shows in `cuotas.this_month`
- [ ] Risk category with `p_overshoot > 0.70` → yellow alert band appears
- [ ] Risk category with `p_overshoot < 0.70` → band silent
- [ ] Runway < days_to_payday → runway card red
- [ ] Mobile: Sankey scrolls horizontally, currency toggle in bottom sheet

### 11.3 Frontend testing
No automated frontend tests (Luka doesn't have a frontend test infrastructure — §NEXT-STEPS). Manual QA only for v1.

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chunk C (backend endpoint) blows the day budget due to forecast complexity | Medium | High | v1 ships with flat-variance heuristics, not full Bayesian. Time-box to 2 days. |
| Recharts Sankey looks bad on mobile | Medium | Medium | Horizontal scroll fallback + time-box to 1.5 days; if it fails, ship a stacked bar chart as placeholder |
| Privacy leak in `fixed`-mode aggregate | Low | **Critical** | Dedicated privacy test in test suite; service-layer enforcement; code review focused on this specific path |
| Cuota mapping to monthly transactions wrong across month boundaries | Medium | Low | Use `first_cuota_date` and `last_cuota_date` as inclusive bounds; unit tests with edge cases |
| Alert threshold 0.70 too noisy or too quiet in production | High | Low | Log all alert events; review after week 1; tune threshold via config before writing to DB |
| Users confused by "spendable" number being lower than "income" | Medium | Medium | Inline tooltip on the spendable card: "Disponible = ingresos − gastos fijos − cuotas − meta de ahorro". Ship copy in v1. |

---

## 13. Phase 2 Parking Lot

Everything below is out of v1 scope and captured here so a future session can pick it up.

### Math engine upgrades
1. **EWMA mean/variance** with α=0.293 (2-month half-life)
2. **Day-of-month profile calibration** — per-category CDF `P_c(d/D)`, Beta-smoothed
3. **Shrinking variance** `σ × sqrt(1 - d/D)` for overshoot probability
4. **Hierarchical cold-start priors** — population blend `λ(n) = 1 - e^(-n/3)`
5. **Population priors** — cross-user `(country, income_band, category)` aggregates, weekly cron
6. **Per-user alert threshold calibration** — RL or frequentist tuning from true-overshoot data

### Feature additions
7. **Sunday email recap** (Chunk I from original plan — weekly summary, spendable left, risk categories, forecast)
8. **Cuota auto-detection from email parser** — extract `"cuota N/M"` strings into structured `cuota_purchases` rows
9. **Day-to-payday auto-detection** from income transaction history
10. **Cuota-aware savings narrative one-liner** — "Tus cuotas comprometen 5.2 meses de tu meta de ahorro"
11. **Named savings goals** (multi-goal UI, Pinterest-worthy, Phase 2 evolution of single savings target)
12. **Unified multi-currency FX view** (Q5 option B — requires reliable FX rate source)
13. **Interpretability tooltips on every number** (v1 has them only on the alert band)
14. **Payday-to-payday month cycle** (Q4 option B)
15. **Month-over-month comparison** ("Gastaste $340k más que Marzo; principal cambio: Restaurantes +$180k")
16. **Household partner activity feed** (transparency-mode couples only)
17. **Anomaly alerts** ("Gasto inusual: $120k en Falabella, 3× tu promedio")
18. **WhatsApp cuota pre-purchase warning** ("Esta cuota te compromete hasta Enero 2027")
19. **Dedicated Cuotas page** — list + calendar heatmap of when each cuota ends
20. **Hybrid per-month contribution mode** (member can change mode monthly)
21. **Percentage contribution mode** ("I contribute 50% of my income")

### Out-of-scope sibling projects (parallel work surfaced during brainstorm, tracked separately)
- **Subscriptions page audit** — verify that upcoming-bills calendar (14 days) and subscription audit card already live there; spec any gaps
- **Dashboard additions** — top-5 merchants card + pace summary (moved out of budget page scope)

---

## 14. Open Questions

1. **Default risk category cap** — v1 uses 75th percentile of historical spend. Is this too lenient (users never trigger alerts) or too strict (always triggering)? Tune after Week 1 data.
2. **`counts_as_savings` location** — categories table vs hardcoded set in code. Chunk 0 decides after inspecting current category storage.
3. **Daily burn rate window** — v1 uses 14 days. Is this the right window, or should it be 7 / 30? Review after launch.
4. **Payday configuration** — what if the user's payday varies (freelancer, commissions)? v1 ignores this; Phase 2 auto-detection handles it.
5. **Subscriptions module coverage for `known_bills`** — §6.2 makes the subscriptions module the single source of truth for known bills. If a user has rent but the subscriptions module hasn't detected it, they must mark it manually in the subscriptions UI. Verify on Day 4 that the existing subscriptions module surfaces a `monthly_amount` and an `active_in_month` check that Chunk C can call without modification; if not, Chunk C adds a thin read-model helper in `backend/modules/subscriptions/read.py`.

---

## 15. Success Criteria

### v1 ships when:
- All checkboxes in §11.2 pass on staging
- Privacy test (§11.1) passes
- Currency bug is verified fixed on production
- User (Rafael) can:
  - See the Sankey with real data
  - Mark a transaction as cuota and see it reflected in the next budget load
  - Configure contribution mode for himself and his partner
  - Set a savings target and see it carved out
  - Trigger a risk alert with real spending and see the yellow band

### Post-v1 success (Week 2 measurement):
- Zero privacy leak incidents
- Alert frequency: 1–3 per user per month (not 0, not 10)
- Spendable number accuracy: user-reported "yes, that matches what I actually have" > 80%
- Sankey is the most-viewed visual on the page (analytics event)
