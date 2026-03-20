# Budgeting: Personal + Household Waterfall
**Date:** 2026-03-20
**Status:** Under review — iteration 4 (additions: allocation % + pace chart)

---

## Overview

Replace the current single-bar household budget page with a **waterfall budget view** that models how money actually flows: income arrives in personal accounts, household gets funded first (via transfer or shared spending), and what remains is the personal budget ceiling.

The page has three layers:
1. **Waterfall summary** — income → household → personal ceiling with progress bars
2. **Percentage allocation** — user sets Hogar / Ahorro / Personal caps as % of income; app suggests defaults from history and 50/20/30 literature
3. **Pace chart** — cumulative spending vs linear budget pace through the month, color-coded green/red

The page adapts to three household configurations:
- **Solo (individual household)** → single collapsed budget (income - personal spending = available)
- **Couple + joint account** → full waterfall (income → household deposit → personal remainder)
- **Couple + no joint account** → same waterfall, but household contribution is shared-classified spending on personal accounts rather than a transfer

---

## Data Model

### Migration: extend `transactions` table

```sql
ALTER TABLE transactions
  ADD COLUMN transaction_type VARCHAR(10) NOT NULL DEFAULT 'expense'
  CHECK (transaction_type IN ('expense', 'income', 'transfer'));

ALTER TABLE transactions
  ADD COLUMN transfer_to_account_id UUID REFERENCES bank_accounts(id) ON DELETE SET NULL;
```

**`transaction_type` values:**
- `expense` — outflow to external party (default, existing behavior unchanged)
- `income` — inflow from external source (salary, received transfer from outside household)
- `transfer` — movement between two bank accounts within the same household (personal → joint)

**`transfer_to_account_id`:** only populated when `transaction_type = 'transfer'`; points to the destination `bank_accounts.id`.

No changes to `household_budgets`. It remains available for users who want to set an optional household target amount.

### New table: `household_budget_allocations`

```sql
CREATE TABLE household_budget_allocations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id  UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
  month         DATE NOT NULL,
  hogar_pct     NUMERIC(5,2) NOT NULL,   -- e.g. 50.00
  ahorro_pct    NUMERIC(5,2) NOT NULL,   -- e.g. 20.00
  personal_pct  NUMERIC(5,2) NOT NULL,   -- e.g. 30.00 (must equal 100 - hogar - ahorro)
  UNIQUE (household_id, month),
  CONSTRAINT pct_sum CHECK (hogar_pct + ahorro_pct + personal_pct = 100)
);
```

**Design notes:**
- Absolute cap amounts are **never stored** — derived at render time as `income × pct / 100`. They auto-adjust as income changes each month.
- `personal_pct` is user-controlled but always equals `100 - hogar_pct - ahorro_pct`; the CHECK constraint enforces this.
- If no allocation row exists for a month, the app falls back to suggested defaults (see Allocation Suggestion Logic below).

---

## Fintoc Sync Logic

### Scope of changes

Two code paths insert Fintoc transactions and both must be updated:

1. **`run_fintoc_sync`** (nightly ARQ cron) — reconciles email-parsed pending transactions to settled Fintoc movements
2. **`import_fintoc_history`** (ARQ job, fires when a user first connects a bank account) — bulk-inserts up to 90 days of history

Additionally, `FintocClient.fetch_transactions()` currently hard-filters to debits only (`amount < 0`). This filter must be removed so inflows are fetched and classified. This is a breaking change to the shared client interface used by both jobs — both jobs must handle positive-amount movements after this change.

### `FintocTransaction` dataclass

`FintocClient` currently maps Fintoc movements to a dataclass with fields: `id`, `amount`, `description`, `transaction_date`, `account_id`. The Fintoc movements API does not reliably expose a structured counterparty account ID field. Therefore **the fallback path is the primary implementation path** — the structured counterparty ID path is aspirational. Add an optional `counterparty_account_id: str | None = None` field to `FintocTransaction`; populate it if the Fintoc API payload exposes it (check `recipient_account` or equivalent at integration time). If the field is absent, the fallback always applies.

### Classification rules (per movement)

**Amount > 0 (inflow on this account):**
1. If `counterparty_account_id` is present and matches a `fintoc_account_id` in the same household → inbound transfer leg; **skip** (only the outbound leg is recorded)
2. Otherwise, if description contains transfer keywords (`"TRANSFERENCIA"`, `"TRASPASO"`) AND a same-amount outbound movement exists on another household account within ±1 day → inbound transfer leg; **skip**
3. Otherwise → create `transaction_type = 'income'` record; **no `TransactionSplit`** (income rows are not spending, budget queries filter on `transaction_type`, not `split_type`)

**Amount < 0 (outflow from this account):**
1. If `counterparty_account_id` is present and matches a `fintoc_account_id` in the same household → `transaction_type = 'transfer'`; `transfer_to_account_id` = matched account; **no `TransactionSplit`**
2. Otherwise, if description contains transfer keywords AND a same-amount inbound movement exists on another household account within ±1 day → `transaction_type = 'transfer'`; `transfer_to_account_id` = matched account; **no `TransactionSplit`**
3. Otherwise → `transaction_type = 'expense'`; existing reconciliation and split-assignment logic applies unchanged

**`import_fintoc_history` split assignment:** The existing `split_map` (`account_type → split_type`) must only apply to `expense` transactions. Income and transfer rows must not receive a `TransactionSplit` row. The `split_map` loop must be gated on `transaction_type == 'expense'`.

**`reconcile_transactions` pass-through:** The classified `transaction_type` value must be passed from the `FintocTransaction` dataclass into the `Transaction(...)` insert inside `reconcile_transactions`. Unmatched insertions must use the dataclass value explicitly — do not rely on the DB `DEFAULT 'expense'`.

**Key design decisions:**
- Transfers are recorded as a **single transaction** on the source account only. The destination inflow is inferred. This avoids double-counting.
- Income and transfer transactions have no `TransactionSplit`. Budget queries for income and transfers filter on `transaction_type` only. Budget queries for personal spending filter on `transaction_type = 'expense'` AND `split_type`.
- If Fintoc is not connected, the personal budget degrades gracefully — income = 0, the UI shows a connect-bank prompt.

### Deploy sequencing note
The Alembic migration (`transaction_type DEFAULT 'expense'`) and the classification logic must ship in the **same deploy**. If the migration ships first without the updated `FintocClient` and classification logic, any inflow records inserted in the window between deploys will land with `transaction_type = 'expense'`, silently corrupting the income calculation. Coordinate Railway backend deploy to include both migration and code.

---

## API

### New endpoint

```
GET /budgets/personal/{household_id}?month=YYYY-MM-DD
```

`month` accepts a `date` value (e.g. `2026-03-01`) and is truncated to the first of the month server-side — consistent with the existing `GET /budgets/monthly/{household_id}` convention.

**Response shape:**

```json
{
  "mode": "waterfall",
  "month": "2026-03",
  "income": 2500000,
  "household": {
    "deposited": 800000,
    "spent": 620000,
    "available": 180000,
    "percent_used": 77.5
  },
  "personal": {
    "ceiling": 1700000,
    "ceiling_clamped": false,
    "spent": 600000,
    "breakdown": {
      "household": 150000,
      "personal": 450000
    },
    "available": 1100000,
    "percent_used": 35.3
  }
}
```

**Solo mode response:**

```json
{
  "mode": "single",
  "month": "2026-03",
  "income": 2500000,
  "personal": {
    "ceiling": 2500000,
    "spent": 600000,
    "breakdown": {
      "household": 0,
      "personal": 600000
    },
    "available": 1900000,
    "percent_used": 24.0
  }
}
```

### Calculations

| Field | Source |
|-------|--------|
| `income` | SUM of `transaction_type = 'income'` on **requesting user's** personal accounts for the month |
| `household.deposited` | SUM of `transaction_type = 'transfer'` from personal → joint accounts for **all household members** for the month. `null` if no joint account exists (couple + no joint case). |
| `user.deposited` (internal) | SUM of `transaction_type = 'transfer'` from personal → joint for **requesting user only** — used in personal ceiling calculation only, not in response |
| `household.spent` | SUM of `transaction_type = 'expense'` with `split_type = 'shared'` on joint account(s) for the month. For couple + no joint: SUM of shared-split expenses on personal accounts. |
| `household.available` | `household.deposited − household.spent` if `deposited > 0`; `null` otherwise (no joint account = no ceiling to track against) |
| `household.percent_used` | `round(spent / deposited * 100, 1)` if `deposited > 0`; `null` otherwise |
| `personal.ceiling` | `income − user.deposited` (waterfall) or `income` (single). Unclamped — may be negative if transfers exceed income. |
| `personal.ceiling_clamped` | `true` if `personal.ceiling < 0`; `false` otherwise |
| `personal.breakdown.household` | SUM of `transaction_type = 'expense'` with `split_type = 'shared'` on requesting user's personal accounts |
| `personal.breakdown.personal` | SUM of `transaction_type = 'expense'` with `split_type = 'personal'` on requesting user's personal accounts |
| `personal.spent` | `breakdown.household + breakdown.personal` |
| `personal.available` | `ceiling − spent` if not clamped; `-(personal.spent)` if clamped (shows how far over budget) |
| `personal.percent_used` | `round(spent / ceiling * 100, 1)` if `ceiling > 0`; `null` if `ceiling <= 0` (covers both clamped and zero-income cases) |

### Mode detection

- `household.type == 'individual'` → `mode = 'single'`; `household` block omitted
- `household.type == 'couple'` → `mode = 'waterfall'`; `household` block always included

### Allocation endpoints

```
GET  /budgets/allocation/{household_id}?month=YYYY-MM-DD   → current allocation + suggestions
POST /budgets/allocation/{household_id}                    → save allocation for a month
```

**GET response:**
```json
{
  "month": "2026-03-01",
  "allocation": {
    "hogar_pct": 50.0,
    "ahorro_pct": 20.0,
    "personal_pct": 30.0,
    "is_default": false
  },
  "suggestions": {
    "historical": { "hogar_pct": 55.0, "ahorro_pct": 10.0, "personal_pct": 35.0 },
    "recommended": { "hogar_pct": 50.0, "ahorro_pct": 20.0, "personal_pct": 30.0, "label": "Regla 50/20/30" }
  }
}
```

`is_default: true` when no row exists for this month — the allocation block shows the 50/20/30 fallback.

**POST body:** `{ month, hogar_pct, ahorro_pct, personal_pct }` — upserts the allocation row; server validates sum = 100.

**Historical suggestion logic:** look at last 3 months of `transaction_type = 'expense'` data; compute actual hogar/personal split; `ahorro` = unspent income fraction. Round to nearest 5% for clean numbers.

### Pace block (added to existing personal budget endpoint)

`GET /budgets/personal/{household_id}?month=YYYY-MM-DD` gains a `pace` field:

```json
"pace": {
  "spendable_budget": 2000000,
  "daily_points": [
    { "day": 1, "cumulative_spent": 45000 },
    { "day": 2, "cumulative_spent": 90000 }
  ],
  "today_day": 12,
  "days_in_month": 31,
  "pace_at_today": 774193,
  "actual_at_today": 600000,
  "delta": -174193,
  "on_track": true
}
```

- `spendable_budget` = `income × (1 - ahorro_pct / 100)`
- `pace_at_today` = `spendable_budget × today_day / days_in_month` (linear interpolation)
- `daily_points` contains one entry per day from day 1 to `today_day`; days with no spending carry forward the previous day's cumulative total
- `delta` = `actual_at_today - pace_at_today`; negative = under budget (good)
- For past months: `today_day = days_in_month` (full month shown)

### Existing endpoints

`GET /POST /budgets/monthly/{household_id}` stays unchanged for users who want to set an optional household budget target.

---

## UI — Budgets Page

### Month selector
Displayed at top of page, defaults to current month. Same pattern as the transactions page.

### Page layout (top to bottom)

**1. Income header**
Simple stat row: `"Ingresos: $2.500.000"`. If Fintoc not connected → soft grey message: `"Conecta tu banco para ver tus ingresos"`.

**2. Pace chart**
Recharts `AreaChart` or `LineChart` spanning full card width.
- X-axis: days 1 → last day of month (tick every 5 days)
- Y-axis: CLP amounts (abbreviated: `$1.2M`)
- **Dashed grey line:** linear budget pace (0 → `spendable_budget`)
- **Solid colored line:** actual cumulative spending up to today; color transitions from `luka-success` (green) when below pace to `luka-danger` (red) when above; uses gradient/segment coloring
- **Callout** at today's dot: `"$174K bajo el ritmo"` (green) or `"$80K sobre el ritmo"` (red)
- For current month: future portion of dashed line shown as faded/dotted
- For past months: full month shown, no "today" callout

**3. Allocation card ("Tu presupuesto")**
Shown when user hasn't set an allocation for this month, OR when they tap "Editar":
- First time: shows two suggestion pills ("Según tu historial" / "Regla 50/20/30") — tapping one pre-fills the sliders
- Three sliders: Hogar (%), Ahorro (%), Personal (auto-fills remainder, read-only)
- Live preview of absolute amounts as user drags: `"Hogar: $1.250.000"`
- Save button; on save → upserts allocation, reloads budget data

**4. Waterfall summary cards**

*Household card ("Hogar"):*
- **Couple + joint account:** progress bar `deposited` vs `spent × hogar_pct cap`; color logic: green < 70%, yellow 70–90%, red > 90%. Available shown below.
- **Couple + no joint account:** plain stat `"Gastos compartidos: $620.000"`. No bar.

*Personal card ("Personal"):*
- Label: `"Techo: $1.700.000"`. If `ceiling_clamped`, show in danger color.
- Two stacked mini bars (only when `ceiling > 0`):
  - **"Hogar"** bar (`luka-sky`) — `breakdown.household` as % of ceiling
  - **"Personal"** bar (`luka-primary`) — `breakdown.personal` as % of ceiling
- Available/overrun below bars; green if positive, red if negative

### Solo mode
Same layout — income header → pace chart → allocation card → single personal card. No household section.

### Graceful degradation
- Fintoc not connected → income = 0; pace chart and bars show empty state with connect-bank prompt
- No allocation set → falls back to 50/20/30 defaults; allocation card shown prominently with suggestion pills
- No transactions this month → pace chart shows flat line at 0; bars empty, not errors

---

## Three Household Configurations

| Config | `mode` | `household.deposited` source | `personal.breakdown.household` source |
|--------|--------|------------------------------|---------------------------------------|
| Individual | `single` | — | — |
| Couple + joint account | `waterfall` | `transfer` transactions personal → joint | `shared` splits on personal accounts (rare) |
| Couple + no joint account | `waterfall` | 0 (no transfers) | `shared` splits on personal accounts |

---

## Out of Scope

- Setting a personal income target manually (Fintoc-detected only for MVP)
- Per-category budget caps beyond the three buckets (Hogar / Ahorro / Personal)
- Projected future spending line on pace chart (future)
- WhatsApp alert when pace is exceeded (future)
- Historical income chart across multiple months (future)
- Savings account auto-detection (ahorro % is a planning target, not verified against a savings account balance)
