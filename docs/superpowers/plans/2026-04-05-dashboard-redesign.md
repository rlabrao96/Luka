# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current dashboard with a useful financial overview: bank balance, cash flow (income/expenses/net), spending trends, category breakdown with budget progress, and recent transactions — with month and currency selectors.

**Architecture:** Backend adds a `category_budgets` table and CRUD endpoints for per-category budget amounts. Frontend adds new components (month selector, currency toggle, cash flow cards, budget bars) and rewrites the dashboard page. Existing components (SpendingChart, CategoryDonut, RecentTransactions) receive new props for month/currency filtering. Client-side filtering of the 6-month transaction dataset.

**Tech Stack:** Next.js 14, Tailwind CSS, shadcn/ui, Recharts, React Query, Zustand

**Design Spec:** `docs/superpowers/specs/2026-04-05-dashboard-redesign-design.md`

**Important context:**
- Per-category budgets will be added in Tasks 1-3 (new `category_budgets` table + API endpoints + frontend hook). Budget bars then show actual spending vs budget per category.
- Balance amounts for CLP are stored as integers (no cents). USD amounts are stored in cents (divide by 100).
- The `CHECKING_KINDS` set must include `"depository"` for Plaid accounts (existing code in `transactions/page.tsx:34` uses `["checking_account", "savings_account", "sight_account"]`).
- `myTxns` includes the user's own transactions with both `split_type: "personal"` and `split_type: "shared"`. `sharedTxns` is partner transactions — do NOT include those in expense/income totals.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/modules/budgets/category_service.py` | Create | CRUD logic for per-category budgets |
| `backend/modules/budgets/schemas.py` | Modify | Add CategoryBudget schemas |
| `backend/modules/budgets/router.py` | Modify | Add category budget endpoints |
| `backend/modules/households/models.py` | Modify | Add CategoryBudget model |
| `backend/alembic/versions/029_category_budgets.py` | Create | Migration for category_budgets table |
| `frontend/app/lib/api.ts` | Modify | Add category budget API functions + types |
| `frontend/app/lib/hooks/useBudget.ts` | Modify | Add useCategoryBudgets hook |
| `frontend/app/(dashboard)/components/MonthSelector.tsx` | Create | Dropdown pill for month selection (6 rolling months) |
| `frontend/app/(dashboard)/components/CurrencyToggle.tsx` | Create | CLP/USD toggle pill |
| `frontend/app/(dashboard)/components/BalanceCard.tsx` | Create | Blue gradient card showing checking balance |
| `frontend/app/(dashboard)/components/CashFlowCards.tsx` | Create | 3 cards: ingresos, gastos, movimiento neto |
| `frontend/app/(dashboard)/components/BudgetBars.tsx` | Create | Top 5 category spending bars with % + amounts |
| `frontend/app/(dashboard)/components/SpendingChart.tsx` | Modify | Accept currency prop for Y-axis formatting |
| `frontend/app/(dashboard)/components/CategoryDonut.tsx` | Modify | Accept filtered data (remove hardcoded month filter) |
| `frontend/app/(dashboard)/page.tsx` | Rewrite | New layout with all sections, month/currency state |

---

### Task 1: Category Budgets — Backend Model + Migration

**Files:**
- Modify: `backend/modules/households/models.py`
- Create: `backend/alembic/versions/029_category_budgets.py`

- [ ] **Step 1: Add CategoryBudget model**

In `backend/modules/households/models.py`, after the `HouseholdBudget` class (line 95), add:

```python
class CategoryBudget(Base):
    __tablename__ = "category_budgets"
    __table_args__ = (
        UniqueConstraint(
            "household_id", "category", "month",
            name="uq_category_budgets_household_cat_month",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Create Alembic migration**

Create `backend/alembic/versions/029_category_budgets.py`:

```python
"""Add category_budgets table

Revision ID: 029
Revises: 028
Create Date: 2026-04-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"],
            name="fk_category_budgets_household_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "household_id", "category", "month",
            name="uq_category_budgets_household_cat_month",
        ),
    )


def downgrade() -> None:
    op.drop_table("category_budgets")
```

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/households/models.py backend/alembic/versions/029_category_budgets.py
git commit -m "feat: add category_budgets table for per-category budget limits"
```

---

### Task 2: Category Budgets — Backend Service + Endpoints

**Files:**
- Create: `backend/modules/budgets/category_service.py`
- Modify: `backend/modules/budgets/schemas.py`
- Modify: `backend/modules/budgets/router.py`

- [ ] **Step 1: Add schemas**

In `backend/modules/budgets/schemas.py`, add at the end:

```python
# ── Category budget schemas ──


class CategoryBudgetItem(BaseModel):
    category: str
    amount: float


class CategoryBudgetResponse(BaseModel):
    household_id: str
    month: str
    budgets: list[CategoryBudgetItem]


class SetCategoryBudgetRequest(BaseModel):
    month: date
    budgets: list[CategoryBudgetItem]
```

- [ ] **Step 2: Create category_service.py**

Create `backend/modules/budgets/category_service.py`:

```python
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from modules.households.models import CategoryBudget


async def get_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
) -> dict:
    result = await db.execute(
        select(CategoryBudget).where(
            CategoryBudget.household_id == household_id,
            CategoryBudget.month == month,
        )
    )
    rows = result.scalars().all()
    return {
        "household_id": str(household_id),
        "month": month.isoformat(),
        "budgets": [{"category": r.category, "amount": float(r.amount)} for r in rows],
    }


async def set_category_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: date,
    budgets: list[dict],
) -> dict:
    # Delete existing budgets for this month, then insert new ones
    await db.execute(
        delete(CategoryBudget).where(
            CategoryBudget.household_id == household_id,
            CategoryBudget.month == month,
        )
    )
    for b in budgets:
        db.add(CategoryBudget(
            household_id=household_id,
            category=b["category"],
            month=month,
            amount=b["amount"],
        ))
    await db.commit()
    return await get_category_budgets(db, household_id, month)
```

- [ ] **Step 3: Add endpoints to router**

In `backend/modules/budgets/router.py`, add imports at the top:

```python
from modules.budgets.schemas import CategoryBudgetResponse, SetCategoryBudgetRequest
from modules.budgets.category_service import get_category_budgets, set_category_budgets
```

Then add at the end of the file:

```python
@router.get("/categories/{household_id}", response_model=CategoryBudgetResponse)
async def get_cat_budgets(
    household_id: uuid.UUID,
    month: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if not month:
        today = date.today()
        month = date(today.year, today.month, 1)
    else:
        month = date(month.year, month.month, 1)
    return await get_category_budgets(db, household_id, month)


@router.post("/categories/{household_id}", response_model=CategoryBudgetResponse)
async def set_cat_budgets(
    household_id: uuid.UUID,
    body: SetCategoryBudgetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    month = date(body.month.year, body.month.month, 1)
    return await set_category_budgets(
        db, household_id, month, [b.model_dump() for b in body.budgets]
    )
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/budgets/category_service.py backend/modules/budgets/schemas.py backend/modules/budgets/router.py
git commit -m "feat: add category budget CRUD endpoints (GET/POST /budgets/categories/{household_id})"
```

---

### Task 3: Category Budgets — Frontend Hook + API

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/lib/hooks/useBudget.ts`

- [ ] **Step 1: Add types and API functions**

In `frontend/app/lib/api.ts`, add the type near the other budget types (after `BudgetStatus` around line 120):

```typescript
export interface CategoryBudgetItem {
  category: string;
  amount: number;
}

export interface CategoryBudgetResponse {
  household_id: string;
  month: string;
  budgets: CategoryBudgetItem[];
}
```

In the `api` object, add the API function (near the other budget functions):

```typescript
getCategoryBudgets: (householdId: string, month?: string) =>
  get<CategoryBudgetResponse>(
    `/budgets/categories/${householdId}${month ? `?month=${month}` : ""}`
  ),

setCategoryBudgets: (householdId: string, body: { month: string; budgets: CategoryBudgetItem[] }) =>
  post<CategoryBudgetResponse>(`/budgets/categories/${householdId}`, body),
```

- [ ] **Step 2: Add React Query hook**

In `frontend/app/lib/hooks/useBudget.ts`, add:

```typescript
export function useCategoryBudgets(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["categoryBudgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId!, month),
    enabled: !!householdId,
  });
}
```

Also add the import for `CategoryBudgetResponse` if needed (it's used via `api` so may not need explicit import).

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useBudget.ts
git commit -m "feat: add frontend hook and API for category budgets"
```

---

### Task 4: MonthSelector Component

**Files:**
- Create: `frontend/app/(dashboard)/components/MonthSelector.tsx`

- [ ] **Step 1: Create MonthSelector component**

```tsx
"use client";
import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

interface MonthSelectorProps {
  value: string;            // "2026-04" format
  onChange: (month: string) => void;
  currentMonth: string;     // today's month for highlighting
}

function getMonthOptions(): { key: string; label: string }[] {
  const now = new Date();
  const options: { key: string; label: string }[] = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleDateString("es-CL", { month: "short", year: "numeric" });
    // Capitalize first letter
    options.push({ key, label: label.charAt(0).toUpperCase() + label.slice(1) });
  }
  return options;
}

export function MonthSelector({ value, onChange, currentMonth }: MonthSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const options = getMonthOptions();

  const selectedLabel = options.find((o) => o.key === value)?.label ?? value;
  const isViewingPast = value !== currentMonth;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold border transition-colors ${
          isViewingPast
            ? "bg-blue-50 border-blue-200 text-blue-600"
            : "bg-white border-slate-200 text-slate-800 shadow-sm"
        }`}
      >
        {selectedLabel}
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[160px] bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => { onChange(opt.key); setOpen(false); }}
              className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between transition-colors ${
                opt.key === value
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              {opt.label}
              {opt.key === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it renders**

Open the app in the browser and temporarily import MonthSelector in the dashboard page to confirm it renders and the dropdown works. Remove the temporary import after verifying.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/components/MonthSelector.tsx
git commit -m "feat(dashboard): add MonthSelector dropdown component"
```

---

### Task 5: CurrencyToggle Component

**Files:**
- Create: `frontend/app/(dashboard)/components/CurrencyToggle.tsx`

- [ ] **Step 1: Create CurrencyToggle component**

```tsx
"use client";

interface CurrencyToggleProps {
  value: string;          // "CLP" or "USD"
  onChange: (currency: string) => void;
}

const CURRENCIES = ["CLP", "USD"] as const;

export function CurrencyToggle({ value, onChange }: CurrencyToggleProps) {
  return (
    <div className="flex rounded-lg border border-slate-200 overflow-hidden shadow-sm">
      {CURRENCIES.map((c) => (
        <button
          key={c}
          onClick={() => onChange(c)}
          className={`px-3 py-1.5 text-sm font-semibold transition-colors ${
            c === value
              ? "bg-blue-600 text-white"
              : "bg-white text-slate-500 hover:bg-slate-50"
          }`}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/components/CurrencyToggle.tsx
git commit -m "feat(dashboard): add CurrencyToggle component"
```

---

### Task 6: BalanceCard Component

**Files:**
- Create: `frontend/app/(dashboard)/components/BalanceCard.tsx`

Reference: `frontend/app/(dashboard)/transactions/page.tsx:14-21` for `formatAmount`, lines 34-35 for `CHECKING_KINDS`.

- [ ] **Step 1: Create BalanceCard component**

```tsx
"use client";
import type { BankAccountRow } from "@/app/lib/api";

interface BalanceCardProps {
  accounts: BankAccountRow[];
  currency: string;
}

const CHECKING_KINDS = new Set([
  "checking_account", "savings_account", "sight_account", "depository",
]);

function formatBalance(n: number, currency: string): string {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? n / 100 : n;
  if (currency === "USD")
    return `US$${displayVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(displayVal).toLocaleString("es-CL")}`;
}

export function BalanceCard({ accounts, currency }: BalanceCardProps) {
  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === currency && a.account_kind && CHECKING_KINDS.has(a.account_kind)
  );

  const total = filtered.reduce((s, a) => s + (a.balance_current ?? 0), 0);

  // Build subtitle from unique bank names
  const banks = [...new Set(filtered.map((a) => a.bank_name).filter(Boolean))];
  const subtitle = banks.length > 0 ? banks.join(" + ") : "Sin cuentas";

  return (
    <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl p-4 text-white">
      <p className="text-xs font-medium uppercase tracking-wide opacity-80">
        Saldo disponible
      </p>
      <p className="text-2xl font-bold mt-1 tabular-nums">
        {formatBalance(total, currency)}
      </p>
      <p className="text-xs opacity-70 mt-0.5">{subtitle}</p>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BalanceCard.tsx
git commit -m "feat(dashboard): add BalanceCard with gradient background"
```

---

### Task 7: CashFlowCards Component

**Files:**
- Create: `frontend/app/(dashboard)/components/CashFlowCards.tsx`

- [ ] **Step 1: Create CashFlowCards component**

This component receives pre-computed income, expenses, and net values. The parent page handles the filtering.

```tsx
"use client";
import { TrendingUp, TrendingDown, ArrowRightLeft } from "lucide-react";

interface CashFlowCardsProps {
  income: number;
  expenses: number;
  net: number;
  currency: string;
}

function fmt(n: number, currency: string): string {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? n / 100 : n;
  if (currency === "USD")
    return `US$${Math.abs(displayVal).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(Math.abs(displayVal)).toLocaleString("es-CL")}`;
}

export function CashFlowCards({ income, expenses, net, currency }: CashFlowCardsProps) {
  return (
    <>
      {/* Ingresos */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center mb-2">
          <TrendingUp size={16} className="text-green-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Ingresos del mes
        </p>
        <p className="text-2xl font-bold text-green-600 mt-1 tabular-nums">
          {fmt(income, currency)}
        </p>
      </div>

      {/* Gastos */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center mb-2">
          <TrendingDown size={16} className="text-red-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Gastos del mes
        </p>
        <p className="text-2xl font-bold text-red-600 mt-1 tabular-nums">
          {fmt(expenses, currency)}
        </p>
      </div>

      {/* Movimiento neto */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center mb-2">
          <ArrowRightLeft size={16} className="text-blue-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Movimiento neto
        </p>
        <p className={`text-2xl font-bold mt-1 tabular-nums ${net >= 0 ? "text-blue-600" : "text-red-600"}`}>
          {net >= 0 ? "+" : "-"}{fmt(Math.abs(net), currency)}
        </p>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/components/CashFlowCards.tsx
git commit -m "feat(dashboard): add CashFlowCards (income/expenses/net)"
```

---

### Task 8: BudgetBars Component

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetBars.tsx`

**Context:** Per-category budgets are now available via `useCategoryBudgets`. This component shows the top 5 categories by spending, each with a progress bar against its category budget. Categories without a budget show spending amount only (no percentage). An overall budget summary is shown if a total budget is set.

- [ ] **Step 1: Create BudgetBars component**

```tsx
"use client";
import type { BudgetStatus, CategoryBudgetItem } from "@/app/lib/api";

interface CategorySpend {
  category: string;
  amount: number;
}

interface BudgetBarsProps {
  categories: CategorySpend[];         // top 5, already sorted desc
  categoryBudgets: CategoryBudgetItem[];  // per-category budget limits
  budget: BudgetStatus | undefined;    // overall monthly budget
  currency: string;
}

function fmt(n: number, currency: string): string {
  const isDecimal = currency !== "CLP";
  const val = isDecimal ? n / 100 : n;
  if (currency === "CLP" && Math.abs(val) >= 1_000_000)
    return `$${(val / 1_000_000).toFixed(1)}M`;
  if (currency === "CLP" && Math.abs(val) >= 1_000)
    return `$${Math.round(val / 1_000)}k`;
  if (currency === "USD")
    return `US$${Math.abs(val).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  return `$${Math.round(val).toLocaleString("es-CL")}`;
}

function pctColor(pct: number): string {
  if (pct >= 100) return "red";
  if (pct >= 80) return "amber";
  if (pct >= 50) return "blue";
  return "green";
}

function barBg(color: string): string {
  const map: Record<string, string> = {
    green: "bg-green-500", blue: "bg-blue-600", amber: "bg-amber-500", red: "bg-red-500",
  };
  return map[color] ?? "bg-blue-600";
}

function textColor(color: string): string {
  const map: Record<string, string> = {
    green: "text-green-600", blue: "text-blue-600", amber: "text-amber-600", red: "text-red-600",
  };
  return map[color] ?? "text-blue-600";
}

export function BudgetBars({ categories, categoryBudgets, budget, currency }: BudgetBarsProps) {
  if (categories.length === 0) return null;

  // Build a lookup: category name → budget amount
  const budgetMap = new Map(categoryBudgets.map((b) => [b.category, b.amount]));

  return (
    <div className="space-y-4">
      {/* Overall budget progress (if budget is set) */}
      {budget && budget.budgeted > 0 && (
        <div className="pb-3 border-b border-slate-100">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="font-semibold text-slate-700">Presupuesto total</span>
            <span className="text-slate-500">
              <span className={`font-bold ${textColor(pctColor(budget.percent_used))}`}>
                {Math.round(budget.percent_used)}%
              </span>
              {" "}· {fmt(budget.spent, currency)} / {fmt(budget.budgeted, currency)}
            </span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barBg(pctColor(budget.percent_used))}`}
              style={{ width: `${Math.min(budget.percent_used, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Per-category bars */}
      {categories.map((cat) => {
        const catBudget = budgetMap.get(cat.category);
        const hasBudget = catBudget != null && catBudget > 0;
        const pct = hasBudget ? (cat.amount / catBudget) * 100 : 0;
        const color = hasBudget ? pctColor(pct) : "blue";

        return (
          <div key={cat.category}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-semibold text-slate-700">{cat.category}</span>
              <span className="text-slate-500">
                {hasBudget ? (
                  <>
                    <span className={`font-bold ${textColor(color)}`}>
                      {Math.round(pct)}%
                    </span>
                    {" "}· {fmt(cat.amount, currency)} / {fmt(catBudget, currency)}
                  </>
                ) : (
                  <span className="font-medium">{fmt(cat.amount, currency)}</span>
                )}
              </span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${barBg(color)}`}
                style={{ width: hasBudget ? `${Math.min(pct, 100)}%` : "100%" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetBars.tsx
git commit -m "feat(dashboard): add BudgetBars for top 5 category spending"
```

---

### Task 9: Update SpendingChart for Currency

**Files:**
- Modify: `frontend/app/(dashboard)/components/SpendingChart.tsx`

Currently the Y-axis formatter is hardcoded to CLP (`$${(v / 1000).toFixed(0)}k`). Add a `currency` prop.

- [ ] **Step 1: Update SpendingChart to accept currency prop**

In `frontend/app/(dashboard)/components/SpendingChart.tsx`:

Change the interface and formatter:

```tsx
// OLD (line 9-11):
interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
}

// NEW:
interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
  currency?: string;
}
```

Change the component signature (line 15):

```tsx
// OLD:
export function SpendingChart({ data }: SpendingChartProps) {

// NEW:
export function SpendingChart({ data, currency = "CLP" }: SpendingChartProps) {
```

Change the formatter (line 13):

```tsx
// OLD:
const CLP = (v: number) => `$${(v / 1000).toFixed(0)}k`;

// NEW — move inside component or make it a function factory:
// Actually, keep it simple — make a local formatter inside the component:
```

Replace line 13 with nothing, and inside the component add:

```tsx
const fmtAxis = (v: number) => {
  if (currency === "USD") {
    const val = v / 100;
    return val >= 1000 ? `US$${(val / 1000).toFixed(0)}k` : `US$${val.toFixed(0)}`;
  }
  return v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1000).toFixed(0)}k`;
};
```

Update the YAxis (line 46):

```tsx
// OLD:
<YAxis tickFormatter={CLP} ...

// NEW:
<YAxis tickFormatter={fmtAxis} ...
```

- [ ] **Step 2: Verify chart still renders with existing data**

Open the dashboard in the browser. The chart should look the same since default is CLP.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/components/SpendingChart.tsx
git commit -m "feat(dashboard): add currency support to SpendingChart"
```

---

### Task 10: Update CategoryDonut for Currency

**Files:**
- Modify: `frontend/app/(dashboard)/components/CategoryDonut.tsx`

Currently the formatter on line 18 is hardcoded to CLP: `const CLP = (v: number) => ...`. Add a `currency` prop so USD amounts format correctly.

- [ ] **Step 1: Add currency prop to CategoryDonut**

In `frontend/app/(dashboard)/components/CategoryDonut.tsx`:

Change the interface (line 14-16):

```tsx
// OLD:
interface CategoryDonutProps {
  data: Array<{ category: string; amount: number }>;
}

// NEW:
interface CategoryDonutProps {
  data: Array<{ category: string; amount: number }>;
  currency?: string;
}
```

Change the component signature (line 20):

```tsx
// OLD:
export function CategoryDonut({ data }: CategoryDonutProps) {

// NEW:
export function CategoryDonut({ data, currency = "CLP" }: CategoryDonutProps) {
```

Replace the hardcoded formatter (line 18):

```tsx
// OLD:
const CLP = (v: number) => `$${Math.round(Number(v)).toLocaleString("es-CL")}`;

// NEW (move inside component or make dynamic):
```

Delete line 18 and add inside the component body (after the `const [activeIndex, ...]` line):

```tsx
const fmtAmount = (v: number) => {
  const n = Math.abs(Number(v));
  if (currency === "USD") {
    const val = n / 100;
    return `US$${val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(n).toLocaleString("es-CL")}`;
};
```

Then replace all references to `CLP(...)` with `fmtAmount(...)` (lines 66 and 91).

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/components/CategoryDonut.tsx
git commit -m "feat(dashboard): add currency support to CategoryDonut"
```

---

### Task 11: Rewrite Dashboard Page

**Files:**
- Rewrite: `frontend/app/(dashboard)/page.tsx`

This is the main task. The page orchestrates all components, manages month/currency state, and computes derived data.

- [ ] **Step 1: Rewrite page.tsx**

Replace the entire content of `frontend/app/(dashboard)/page.tsx`:

```tsx
"use client";
import { useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { BarChart3 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { MonthSelector } from "./components/MonthSelector";
import { CurrencyToggle } from "./components/CurrencyToggle";
import { BalanceCard } from "./components/BalanceCard";
import { CashFlowCards } from "./components/CashFlowCards";
import { BudgetBars } from "./components/BudgetBars";
import { RecentTransactions } from "./components/RecentTransactions";

import { useMyTransactions, useMonthlySpending } from "@/app/lib/hooks/useTransactions";
import { useBudgetStatus, useCategoryBudgets } from "@/app/lib/hooks/useBudget";
import { useLukaStore } from "@/app/lib/store";
import { api, type BankAccountRow } from "@/app/lib/api";

// Lazy-load chart components (~200KB Recharts bundle)
const SpendingChart = dynamic(
  () => import("./components/SpendingChart").then((m) => ({ default: m.SpendingChart })),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-slate-100 rounded-xl" /> },
);
const CategoryDonut = dynamic(
  () => import("./components/CategoryDonut").then((m) => ({ default: m.CategoryDonut })),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-slate-100 rounded-xl" /> },
);

function getCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthKey(iso: string): string {
  return iso.split("T")[0].slice(0, 7);
}

export default function DashboardPage() {
  const name = useLukaStore((s) => s.userFullName) ?? "tú";
  const householdId = useLukaStore((s) => s.householdId);

  // ── Controls ──
  const currentMonth = getCurrentMonth();
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [selectedCurrency, setSelectedCurrency] = useState("CLP");

  // Default currency from user preference
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  useEffect(() => {
    if (me?.preferred_currency) setSelectedCurrency(me.preferred_currency);
  }, [me?.preferred_currency]);

  const isViewingPast = selectedMonth !== currentMonth;

  // ── Data ──
  const { data: myTxns = [] } = useMyTransactions();
  const { data: monthlySpending = [] } = useMonthlySpending();
  const { data: budget } = useBudgetStatus(selectedMonth);
  const { data: catBudgets } = useCategoryBudgets(selectedMonth);
  const { data: accounts = [] } = useQuery<BankAccountRow[]>({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

  // ── Derived: filter transactions by month + currency ──
  const monthTxns = useMemo(
    () => myTxns.filter(
      (t) => getMonthKey(t.transaction_date) === selectedMonth
        && (t.currency ?? "CLP") === selectedCurrency
    ),
    [myTxns, selectedMonth, selectedCurrency]
  );

  // Cash flow
  const income = useMemo(
    () => monthTxns.filter((t) => Number(t.amount) > 0).reduce((s, t) => s + Number(t.amount), 0),
    [monthTxns]
  );
  const expenses = useMemo(
    () => monthTxns.filter((t) => Number(t.amount) < 0).reduce((s, t) => s + Math.abs(Number(t.amount)), 0),
    [monthTxns]
  );
  const net = income - expenses;

  // Category breakdown (top 5 + Otros)
  const categoryData = useMemo(() => {
    const map: Record<string, number> = {};
    monthTxns
      .filter((t) => Number(t.amount) < 0)
      .forEach((t) => {
        const cat = t.category ?? "Otros";
        map[cat] = (map[cat] ?? 0) + Math.abs(Number(t.amount));
      });
    const sorted = Object.entries(map)
      .map(([category, amount]) => ({ category, amount }))
      .sort((a, b) => b.amount - a.amount);
    if (sorted.length <= 5) return sorted;
    const top5 = sorted.slice(0, 5);
    const overflowTotal = sorted.slice(5).reduce((s, e) => s + e.amount, 0);
    if (overflowTotal === 0) return top5;
    const othersIdx = top5.findIndex((e) => e.category === "Otros");
    if (othersIdx >= 0) {
      return top5.map((e, i) => i === othersIdx ? { ...e, amount: e.amount + overflowTotal } : e);
    }
    return [...top5, { category: "Otros", amount: overflowTotal }];
  }, [monthTxns]);

  // Recent transactions (latest 5 for selected month/currency)
  const recentTxns = useMemo(
    () => monthTxns
      .sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime())
      .slice(0, 5),
    [monthTxns]
  );

  // ── Greeting ──
  const firstName = name.split(" ")[0];
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Buenos días" : hour < 19 ? "Buenas tardes" : "Buenas noches";

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-luka-dark tracking-tight">
            {greeting}, {firstName}
          </h1>
          <p className="text-sm text-luka-muted mt-0.5">Aquí está tu resumen financiero</p>
        </div>
        <div className="flex items-center gap-2">
          <MonthSelector value={selectedMonth} onChange={setSelectedMonth} currentMonth={currentMonth} />
          <CurrencyToggle value={selectedCurrency} onChange={setSelectedCurrency} />
        </div>
      </div>

      {/* Banner for past month */}
      {isViewingPast && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm text-blue-700 text-center">
          Viendo datos de {new Date(Number(selectedMonth.split("-")[0]), Number(selectedMonth.split("-")[1]) - 1).toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </div>
      )}

      {/* ── Section 1: Balance + Cash Flow ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {!isViewingPast && (
          <BalanceCard accounts={accounts} currency={selectedCurrency} />
        )}
        <CashFlowCards
          income={income}
          expenses={expenses}
          net={net}
          currency={selectedCurrency}
        />
      </div>

      {/* ── Section 2: Spending Trend ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-luka-dark">Tendencia de gastos</h2>
            <p className="text-xs text-luka-muted mt-0.5">Personal vs. compartido · Últimos 6 meses</p>
          </div>
          <div className="flex gap-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
              Personal
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
              Compartido
            </span>
          </div>
        </div>
        <div className="h-[140px] md:h-[200px]">
          <SpendingChart data={monthlySpending} currency={selectedCurrency} />
        </div>
      </div>

      {/* ── Section 3: Category Donut + Budget Bars ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Category donut */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-luka-dark">Por categoría</h2>
            <p className="text-xs text-luka-muted mt-0.5">
              {isViewingPast
                ? new Date(Number(selectedMonth.split("-")[0]), Number(selectedMonth.split("-")[1]) - 1).toLocaleDateString("es-CL", { month: "long" })
                : "Este mes"
              }
            </p>
          </div>
          {categoryData.length > 0 ? (
            <CategoryDonut data={categoryData} currency={selectedCurrency} />
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center gap-2">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                <BarChart3 size={18} className="text-slate-400" />
              </div>
              <p className="text-xs text-luka-muted">Sin datos aún</p>
            </div>
          )}
        </div>

        {/* Budget bars */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-luka-dark">Gasto por categoría</h2>
            <p className="text-xs text-luka-muted mt-0.5">Top 5 categorías</p>
          </div>
          {categoryData.length > 0 ? (
            <BudgetBars
              categories={categoryData.slice(0, 5)}
              categoryBudgets={catBudgets?.budgets ?? []}
              budget={budget}
              currency={selectedCurrency}
            />
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center gap-2">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                <BarChart3 size={18} className="text-slate-400" />
              </div>
              <p className="text-xs text-luka-muted">Sin datos aún</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Section 4: Recent Transactions ── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-luka-dark">Últimas transacciones</h2>
            <p className="text-xs text-luka-muted mt-0.5">Movimientos recientes</p>
          </div>
          <a href="/transactions" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
            Ver todas →
          </a>
        </div>
        <RecentTransactions transactions={recentTxns} compact={true} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Fix SpendingChart height**

The SpendingChart currently hardcodes `height={200}` in its ResponsiveContainer. Update `SpendingChart.tsx` to use `height="100%"` so the parent div controls the height:

In `frontend/app/(dashboard)/components/SpendingChart.tsx`, change:

```tsx
// OLD (line 32):
<ResponsiveContainer width="100%" height={200}>

// NEW:
<ResponsiveContainer width="100%" height="100%">
```

Also update the empty state height to match:

```tsx
// OLD (line 22):
<div className="h-[200px] flex flex-col ...

// NEW:
<div className="h-full min-h-[140px] flex flex-col ...
```

- [ ] **Step 3: Verify the full dashboard renders**

Open http://localhost:3000 in the browser. Verify:
1. Greeting shows correctly
2. Month selector dropdown works
3. Currency toggle switches between CLP/USD
4. Balance card shows (disappears when viewing past month)
5. Cash flow cards show income/expenses/net
6. Spending trend chart renders
7. Category donut renders
8. Budget bars render
9. Recent transactions show
10. Mobile responsive (resize browser to <768px)

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/page.tsx frontend/app/\(dashboard\)/components/SpendingChart.tsx
git commit -m "feat(dashboard): redesign with balance, cash flow, budget bars, month/currency selectors"
```

---

### Task 12: Responsive Polish

**Files:**
- Modify: `frontend/app/(dashboard)/page.tsx`

- [ ] **Step 1: Fix grid layout for mobile**

The current grid uses `md:grid-cols-4` for the balance + cash flow section. On mobile, the 3 cash flow cards should be in a row even on small screens. When the balance card is hidden (past month), the 3 cards should span the full width.

In `page.tsx`, update the balance + cash flow grid:

```tsx
// OLD:
<div className="grid grid-cols-1 md:grid-cols-4 gap-4">
  {!isViewingPast && (
    <BalanceCard accounts={accounts} currency={selectedCurrency} />
  )}
  <CashFlowCards ...

// NEW:
<div className={`grid gap-4 ${isViewingPast ? "grid-cols-3" : "grid-cols-1 md:grid-cols-4"}`}>
  {!isViewingPast && (
    <BalanceCard accounts={accounts} currency={selectedCurrency} />
  )}
  <CashFlowCards ...
```

On mobile without balance card, 3 columns may be too tight. Adjust:

```tsx
<div className={`grid gap-4 ${
  isViewingPast
    ? "grid-cols-1 sm:grid-cols-3"
    : "grid-cols-1 sm:grid-cols-3 md:grid-cols-4"
}`}>
```

When showing balance (not past), on mobile: balance full-width, then 3 cash flow cards in a row. The `CashFlowCards` renders 3 sibling `<div>`s so they naturally fill grid cells.

- [ ] **Step 2: Test mobile layout**

Resize browser to 375px width. Verify:
- Balance card is full width
- Cash flow cards stack on very small screens, 3-across on `sm`
- Category + budget stack vertically
- Month selector and currency toggle don't overflow

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/page.tsx
git commit -m "fix(dashboard): responsive grid for mobile and past-month views"
```

---

### Task 13: Final Verification and Cleanup

- [ ] **Step 1: Remove unused imports from old page**

Check that the old imports (`CreditCard`, `Users`, `Wallet` from lucide, `useSharedTransactions`, `useHouseholdSummary`) are not referenced. If not, they were already removed in the rewrite. Verify no TypeScript errors:

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 2: Visual verification in browser**

Open http://localhost:3000 and verify:
1. Current month view: balance + 3 cash flow cards + trend + category/budget + recent TX
2. Switch to past month: balance hides, banner appears, data filters correctly
3. Switch to USD: all amounts format as USD, balance updates
4. Mobile (375px): everything stacks correctly
5. Desktop (1200px+): 4-column top row, side-by-side category/budget

- [ ] **Step 3: Push**

```bash
git push
```
