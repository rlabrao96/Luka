# Budgeting: Personal + Household Waterfall
**Date:** 2026-03-20
**Status:** Approved — ready for implementation planning

---

## Overview

Replace the current single-bar household budget page with a **waterfall budget view** that models how money actually flows: income arrives in personal accounts, household gets funded first (via transfer or shared spending), and what remains is the personal budget ceiling.

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

---

## Fintoc Sync Logic

The `run_fintoc_sync` ARQ job already fetches movements per connected account. Classification is added as a pre-step before the existing expense reconciliation path.

### Classification rules (per movement):

**Amount > 0 (inflow on this account):**
1. Look up `fintoc_account_id` of the counterparty in the movement metadata
2. If counterparty matches any `fintoc_account_id` in the same household → `transfer` (this account received from a sibling account; skip — we only record the outbound leg)
3. Otherwise → `income`

**Amount < 0 (outflow from this account):**
1. Look up counterparty `fintoc_account_id`
2. If counterparty matches any `fintoc_account_id` in the same household → `transfer`; set `transfer_to_account_id` to the matching `bank_accounts.id`
3. Otherwise → `expense` (existing reconciliation path, no change)

**Key design decisions:**
- Transfers are recorded as a **single transaction** on the source account only. The destination inflow is inferred. This avoids double-counting.
- If Fintoc is not connected for a user, the personal budget degrades gracefully — income shows as 0 and the UI displays a soft prompt to connect a bank account.
- Existing expense reconciliation (email-parsed pending → Fintoc-settled matching) is untouched.

---

## API

### New endpoint

```
GET /budgets/personal/{household_id}?month=YYYY-MM
```

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
| `income` | SUM of `transaction_type = 'income'` on current user's personal accounts for the month |
| `household.deposited` | SUM of `transaction_type = 'transfer'` from personal → joint accounts (all members) for the month |
| `household.spent` | SUM of shared-split transactions on joint account for the month (existing logic) |
| `household.available` | `deposited − spent` |
| `personal.ceiling` | `income − household.deposited` (waterfall) or `income` (single) |
| `personal.breakdown.household` | SUM of `transaction_type = 'expense'` with `split_type = 'shared'` on personal accounts (couple + no joint case) |
| `personal.breakdown.personal` | SUM of `transaction_type = 'expense'` with no shared split on personal accounts |
| `personal.spent` | `breakdown.household + breakdown.personal` |
| `personal.available` | `ceiling − spent` |

### Mode detection

- `household.type == 'individual'` → `mode = 'single'`; `household` block omitted
- `household.type == 'couple'` → `mode = 'waterfall'`; `household` block always included

### Existing endpoints

`GET /POST /budgets/monthly/{household_id}` stays unchanged for users who want to set an optional household budget target.

---

## UI — Budgets Page

### Month selector
Displayed at top of page, defaults to current month. Same pattern as the transactions page.

### Waterfall mode layout (couple)

**1. Income header**
Simple stat row: `"Ingresos: $2.500.000"`. If Fintoc not connected → soft grey message: `"Conecta tu banco para ver tus ingresos"`.

**2. Household card ("Hogar")**
- Progress bar: deposited / spent / available
- Same color logic as current budget: green < 70%, yellow 70–90%, red > 90% of deposited

**3. Personal card ("Personal")**
- Label: ceiling amount (`"Techo: $1.700.000"`)
- Two stacked mini progress bars:
  - **"Hogar"** bar (sky-blue `luka-sky`) — household-tagged spending as % of ceiling
  - **"Personal"** bar (blue `luka-primary`) — personal spending as % of ceiling
- Available amount below both bars, colored green/red based on sign

### Solo mode layout
- Income header (same)
- Single card with one progress bar (personal spending vs income)
- No household section, no tags

### Graceful degradation
- Fintoc not connected → income = 0, ceiling = 0; card shows connect-bank prompt instead of bars
- No transactions this month → bars show empty state, not errors

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
- Budget targets for personal spending (ceiling is derived, not user-set)
- Historical income chart (future)
- Notifications when personal budget is exceeded (future)
