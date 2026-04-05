# Dashboard Redesign — Design Spec

**Date:** 2026-04-05
**Status:** Draft

## Problem

The current dashboard is not useful. It shows three KPI cards (personal spending, shared spending, budget available), a spending trend chart, a category donut, and recent transactions — but lacks bank balance visibility, income tracking, cash flow summary, budget progress by category, and the ability to filter by month or currency. All data is hardcoded to the current month and CLP.

## Design

### Layout: Stacked Sections (Layout A)

All sections stack vertically in priority order. On desktop (1200px+), some sections use horizontal grid layouts. On mobile, everything is single-column.

### Section 1: Header + Controls

**Greeting row:**
- Left: "Buenos días/tardes/noches, {name}" + subtitle "Aquí está tu resumen financiero"
- Right: month pill + currency pill

**Month selector:**
- Default: clean pill button showing current month (e.g., "Abril 2026") with a small chevron
- On click: dropdown with 6 rolling months, current month highlighted in blue with checkmark
- Past month selected: pill gets blue tint background (`#EFF6FF` bg, `#BFDBFE` border), banner appears below header: "Viendo datos de {month} {year}"
- No arrow navigation — just the dropdown

**Currency toggle:**
- Pill button showing "CLP" or "USD"
- Defaults to user's `preferred_currency` from `/auth/me`
- Tap to switch between CLP and USD
- Persists selection in local state (does not update user preference on the server)

### Section 2: Balance + Cash Flow

**Desktop:** 4 cards in a single row (grid-template-columns: 1fr 1fr 1fr 1fr)
**Mobile:** Balance card full-width, then 3 cash flow cards in a row

**Card 1 — Saldo disponible:**
- Blue gradient background (`#2563EB` to `#1D4ED8`)
- Shows sum of `balance_current` for checking/savings accounts (`account_kind` in `["checking_account", "savings_account", "sight_account", "depository"]`) matching selected currency. Note: Plaid accounts may use `depository` as account_kind — include both naming conventions.
- Excludes credit cards and lines of credit
- Subtitle: bank name(s)
- Hidden when viewing a past month (no historical balance data available)

**Card 2 — Ingresos del mes:**
- Green text (`#16A34A`)
- Sum of transactions with positive `amount` for the selected month and currency
- Subtitle: "Sueldo + otros" or similar contextual text

**Card 3 — Gastos del mes:**
- Red text (`#DC2626`)
- Sum of transactions with negative `amount` (absolute value) for the selected month and currency
- Includes savings outflows (treated as expenses for cash flow purposes)
- Subtitle: "Personal + compartido"

**Card 4 — Movimiento neto:**
- Blue text (`#2563EB`)
- Ingresos minus gastos
- Positive = surplus, negative = deficit
- Subtitle: "Ingresos - gastos"

### Section 3: Spending Trend Chart

**Full width on both mobile and desktop.**

- Area chart (Recharts) showing personal vs compartido spending over the last 6 months
- Y-axis: abbreviated amounts ($k notation for CLP, standard for USD)
- Legend: "Personal" (blue `#2563EB`) / "Compartido" (light blue `#93C5FD`)
- This chart is contextual — always shows the last 6 months anchored to the current date, regardless of the selected month
- Taller on desktop (~200px), shorter on mobile (~140px)

### Section 4: Category Breakdown + Budget Progress

**Desktop:** side-by-side, 50/50 grid
**Mobile:** stacked — donut first, budget bars below

**Left — Category donut:**
- Pie/donut chart for the selected month
- Top 5 categories by spend + "Otros" bucket
- Legend shows category name and amount (e.g., "Alimentacion — $578k")
- Interactive hover state showing category detail

**Right — Budget progress (top 5 categories):**
- Each category shows:
  - Category name (left)
  - Percentage + amounts (right): e.g., "80% · $280k / $350k"
  - Progress bar below
- Color coding by percentage:
  - Green (`#16A34A`): under 50%
  - Blue (`#2563EB`): 50–79%
  - Amber (`#F59E0B`): 80–99%
  - Red (`#DC2626`): 100%+
- If no budget is set for a category, show the bar without a percentage/target

### Section 5: Recent Transactions

**Full width on both mobile and desktop.**

- Shows latest transactions for the selected month
- Limit: 5 transactions
- Each row shows:
  - Mobile: merchant name + amount
  - Desktop: merchant name + category tag + split type (Personal/Compartido) + amount
- Amounts color-coded: red for expenses, green for income
- "Ver todas" link in the header, navigates to `/transactions`

### No emojis

No emojis anywhere in the dashboard UI — icons only (Lucide icon set via shadcn/ui).

## Data Strategy

### Prefetching

On page load, prefetch data for the **current month** in **both currencies** (CLP and USD). This means:
- `useMyTransactions()` — already fetches 6 months of data (no change needed)
- `useSharedTransactions()` — already fetches 6 months (no change needed)
- `useMonthlySpending()` — already fetches all months (no change needed)
- `useBudgetStatus()` — prefetch for current month
- Bank accounts — already prefetched in `StoreInitializer`

### Month switching

When the user selects a different month:
- Cash flow cards: filter transactions client-side (data already in memory from 6-month fetch)
- Category donut: filter transactions client-side
- Budget bars: fetch via `useBudgetStatus(month)` — React Query caches per month
- Recent transactions: filter client-side
- Balance card: hide (no historical data)

### Currency switching

When the user selects a different currency:
- All cards: filter transactions by `currency` field client-side
- Balance card: filter bank accounts by `currency` field
- Budget bars: budgets are tied to a `bank_account_id` which has a currency. Only show budget bars when the budget's bank account currency matches the selected currency. If no budgets exist for the selected currency, hide the budget section entirely.
- No additional API calls needed — all transaction data is already loaded

### Existing hooks reused

| Hook | Used for | Changes needed |
|------|----------|----------------|
| `useMyTransactions()` | Cash flow, category donut, recent TX | None |
| `useSharedTransactions()` | Cash flow (shared portion), trend chart | None |
| `useMonthlySpending()` | Trend chart | None |
| `useBudgetStatus(month?)` | Budget progress bars | Already accepts optional month |
| `useQuery(["bank-accounts"])` | Balance card | Already prefetched |
| `useQuery(["me"])` | Default currency preference | Already available |

### New computation (client-side only)

- **Income calculation:** filter `myTxns` where `amount > 0` for selected month/currency
- **Expense calculation:** filter `myTxns` where `amount < 0` for selected month/currency. `myTxns` includes all transactions owned by the user (both personal and shared split types). `sharedTxns` contains partner's transactions — these are NOT included in the expense total to avoid double-counting. The user sees only their own spending.
- **Net:** income - |expenses|
- **Category budget mapping:** match category names from transactions to budget categories

## Responsive Breakpoints

| Section | Mobile (<768px) | Desktop (768px+) |
|---------|----------------|------------------|
| Balance + Cash flow | Balance full-width, 3 cards in row | 4 cards in row |
| Trend chart | Full width, 140px height | Full width, 200px height |
| Category + Budget | Stacked vertically | Side-by-side 50/50 |
| Recent TX | Name + amount | Name + category + split type + amount |

## Files to Modify

### Frontend

| File | Changes |
|------|---------|
| `frontend/app/(dashboard)/page.tsx` | Replace entire page with new layout, add month/currency state |
| `frontend/app/(dashboard)/components/KpiCard.tsx` | Update to support balance variant (gradient bg) and color variants |
| `frontend/app/(dashboard)/components/SpendingChart.tsx` | Minor: ensure legend shows, adjust height responsive |
| `frontend/app/(dashboard)/components/CategoryDonut.tsx` | Accept month prop instead of hardcoding current month |
| `frontend/app/(dashboard)/components/MonthSelector.tsx` | **New** — dropdown month pill component |
| `frontend/app/(dashboard)/components/CurrencyToggle.tsx` | **New** — currency toggle pill component |
| `frontend/app/(dashboard)/components/BudgetBars.tsx` | **New** — top 5 category budget progress bars |
| `frontend/app/(dashboard)/components/CashFlowCards.tsx` | **New** — income/expenses/net cards with computation |

### Backend

No backend changes needed. All required endpoints and data already exist.

## Out of Scope

- Historical balance snapshots (would need a new table + cron job to capture daily balances)
- Budget creation/editing from the dashboard (use existing budget settings page)
- Savings goal tracking
- Partner spending comparison on the dashboard
