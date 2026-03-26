# Household Enhancement & Subscriptions Tab — Design Spec

**Date:** 2026-03-26
**Status:** Approved

## Overview

Two parallel features for the Luka dashboard:
1. **Enhanced Household tab** — per-category spending breakdown by member + settlement suggestion based on configurable split ratio
2. **Subscriptions tab** — auto-detect recurring expenses from transaction history, show timeline of upcoming charges with price change alerts

## Feature 1: Enhanced Household Tab

### Current State
- Shows monthly contribution totals per member with percentage bars
- Shows partner aggregate stats (privacy-protected via SECURITY DEFINER)
- Current month only

### New Design

**Layout (top to bottom):**

1. **Hero card** — Total shared expenses for the month, per-person amounts with %, horizontal contribution bar
2. **Category breakdown table** — Rows per category, each with:
   - Category name + emoji + mini proportion bar (blue/pink)
   - Per-person amount with % of that category underneath
   - Total column with % of overall spending underneath
   - Footer row with totals
3. **Settlement card** — Compact blue gradient bar at bottom: "X debe transferir $Y a Z" with configured split ratio displayed

**Month selector:** Dropdown to pick month (reuse existing FilterPanel month pattern from transactions page).

**Split ratio config:** Edit button on settlement card opens modal with two inputs summing to 100% (e.g., 50/50, 60/40).

### Backend Changes

**Enhanced endpoint — `GET /households/{id}/summary`:**
- Add `by_category` field: array of `{category, member_totals: [{user_id, name, amount, pct}], total, pct_of_overall}`
- Add `month` query parameter (default: current month)

**New endpoint — `GET /households/{id}/settlement`:**
- Input: household_id, month (optional, default current)
- Calculates: total shared per member, expected share based on ratio, difference
- Returns: `{from_user: {id, name}, to_user: {id, name}, amount, split_ratio: [int, int], month}`

**New endpoint — `PATCH /households/{id}/split-ratio`:**
- Input: `{ratio: [50, 50]}` — two integers summing to 100
- Stores in new `split_ratio` column on `households` table (JSONB, default `[50, 50]`)

**Schema change:**
- `households` table: add `split_ratio JSONB DEFAULT '[50, 50]'`

### Frontend Changes

**Enhanced hooks:**
- `useHouseholdSummary(month?)` — updated to pass month param, returns category breakdown
- New `useSettlement(householdId, month?)` → `GET /households/{id}/settlement`
- New `useSplitRatio()` + `useUpdateSplitRatio()` mutation → `GET/PATCH split-ratio`

**New/modified components:**
- `HouseholdHero` — total expenses card with contribution bar
- `CategoryBreakdownTable` — table with mini bars and percentages
- `SettlementCard` — compact gradient card with transfer suggestion
- `SplitRatioModal` — modal to edit the household split ratio

## Feature 2: Subscriptions / Recurring Expenses Tab

### Detection Algorithm

Query existing transactions to find recurring patterns:
1. Group transactions by `merchant_id` (fallback: `raw_merchant_name`)
2. For each merchant, check if charges appear in 2+ consecutive months
3. Amount tolerance: within 20% between months (handles price changes, variable bills)
4. Calculate: average amount, frequency (monthly), last charge date, predicted next charge date
5. Price trend: compare latest charge to previous — flag as stable / increased / decreased

**No new database tables** — subscriptions are a computed view over `transactions`.

### Backend

**New module:** `modules/subscriptions/`

**New endpoint — `GET /subscriptions/detected`:**
- Query parameter: `months_back` (default: 6, how far back to look)
- Returns array of:
  ```
  {
    merchant_name: string,
    category: string | null,
    average_amount: number,
    last_amount: number,
    previous_amount: number | null,
    last_charge_date: date,
    predicted_next_date: date,
    frequency: "monthly",
    trend: "stable" | "increased" | "decreased",
    trend_pct: number | null,
    months_seen: number,
    split_type: "personal" | "shared" | "partner"
  }
  ```

### Frontend

**New route:** `/subscriptions`

**Navigation:** New sidebar item "Suscripciones" with `Repeat` icon (lucide-react), positioned after Presupuesto.

Nav order: Dashboard → Transacciones → Hogar → Presupuesto → **Suscripciones** → Configuración

**Layout:**

1. **Summary card** — Total monthly recurring, active count, % of total monthly spending
2. **Timeline** — "Próximos cobros — [next month]" vertical timeline sorted by predicted date. Blue dots for earlier dates, gray for later.
3. **Price change alerts** — Yellow warning banners for subscriptions where `trend != "stable"`. Shows: merchant name, old amount → new amount, % change.

**New hooks:**
- `useSubscriptions()` → `GET /subscriptions/detected`

**Components:**
- `SubscriptionSummary` — KPI card with total + count + %
- `SubscriptionTimeline` — vertical timeline with date markers and amounts
- `PriceChangeAlert` — yellow warning banner per changed subscription
- `SubscriptionEmptyState` — "No hemos detectado gastos recurrentes aún. Necesitamos al menos 2 meses de transacciones."

### Edge Cases

- **Empty state:** User has <2 months of data → show friendly empty state
- **Solo users:** Works identically — subscriptions are per-user
- **No household:** Settlement card hidden, household tab shows "create household" prompt (existing behavior)
- **All subscriptions stable:** No price change alerts shown
- **Partner privacy:** Subscriptions page shows only the logged-in user's recurring charges

## Out of Scope

- Manual subscription tagging
- Subscription cancellation detection
- Historical subscription trend charts
- Push notifications for upcoming charges
- Per-category split ratios (one ratio for the whole household)
- Historical settlement (current month only)
- New database tables for subscriptions

## Technical Notes

- Both features can be developed in parallel (independent modules)
- Subscriptions detection is read-only — no writes, no background jobs
- Settlement calculation reuses existing transaction data with splits
- Split ratio is the only schema migration needed (one JSONB column)
