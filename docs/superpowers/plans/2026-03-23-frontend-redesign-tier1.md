# Frontend Redesign — Tier 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Luka's frontend to a professional, mobile-first finance dashboard with DM Sans typography, card-based transaction rows, bottom sheets for mobile editing, collapsible filters, and polished budgets page.

**Architecture:** Mobile-first responsive redesign touching 3 pages (Transactions, Dashboard, Budgets) plus global changes (typography, new BottomSheet component). One new backend endpoint for split type updates. All changes build on existing Next.js 14 + Tailwind v4 + shadcn/ui stack.

**Tech Stack:** Next.js 14, Tailwind CSS v4, DM Sans (Google Fonts), Recharts, shadcn/ui + Base-UI, React portals (bottom sheet)

**Spec:** `docs/superpowers/specs/2026-03-23-frontend-redesign-tier1-design.md`

---

## File Map

### New files
- `frontend/components/ui/bottom-sheet.tsx` — Reusable mobile bottom sheet component
- `frontend/app/(dashboard)/components/CategoryBottomSheet.tsx` — Category picker in bottom sheet
- `frontend/app/(dashboard)/components/SplitTypeEditor.tsx` — Split type editor (bottom sheet on mobile, dropdown on desktop)
- `frontend/app/(dashboard)/components/TransactionCard.tsx` — New card-based transaction row
- `frontend/app/(dashboard)/components/FilterPanel.tsx` — Collapsible mobile filter panel

### Modified files
- `frontend/app/layout.tsx` — Replace Geist with DM Sans font
- `frontend/app/globals.css` — Update `--font-sans`, add gradient tokens
- `frontend/app/(dashboard)/transactions/page.tsx` — Refactor SummaryBar, filters, tabs
- `frontend/app/(dashboard)/components/RecentTransactions.tsx` — Replace with TransactionCard usage, add date grouping
- `frontend/app/(dashboard)/page.tsx` — KPI card stacking, chart layout, use new transaction cards
- `frontend/app/(dashboard)/budgets/page.tsx` — Income card, month selector polish
- `frontend/app/(dashboard)/components/AllocationCard.tsx` — Touch-friendly sliders
- `frontend/app/(dashboard)/components/WaterfallCards.tsx` — Card shadow/progress bar polish
- `frontend/app/(dashboard)/components/KpiCard.tsx` — Mobile stacking support
- `frontend/components/ui/tabs.tsx` — Verify underline variant works (may already exist as "line" variant)
- `frontend/app/lib/api.ts` — Add `updateTransactionSplitType` method
- `backend/modules/transactions/router.py` — Add PATCH split-type endpoint

---

## Task 1: Typography — Replace Geist Sans with DM Sans

**Files:**
- Modify: `frontend/app/layout.tsx:2,6-14,29`
- Modify: `frontend/app/globals.css:28-29`

- [ ] **Step 1: Update font import in layout.tsx**

Replace Geist font imports with DM Sans:

```tsx
// layout.tsx — replace lines 2, 6-14
import { DM_Sans, Geist_Mono } from "next/font/google";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});
```

Update the body className (line 29):
```tsx
className={`${dmSans.variable} ${geistMono.variable} antialiased`}
```

- [ ] **Step 2: Update CSS font variables**

In `globals.css`, change line 28:
```css
--font-sans: var(--font-dm-sans);
```

Also update line 111 (body font-family) — this MUST be changed or it will still reference the old variable and fall back to system-ui:
```css
/* Change from: */
font-family: var(--font-geist-sans), system-ui, sans-serif;
/* To: */
font-family: var(--font-dm-sans), system-ui, sans-serif;
```

- [ ] **Step 3: Verify in browser**

Run: `cd frontend && npm run dev`
Check: All text renders in DM Sans across dashboard, transactions, budgets pages. Verify font weights (400, 500, 600, 700) render correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/globals.css
git commit -m "feat(ui): replace Geist Sans with DM Sans typography"
```

---

## Task 2: Add Gradient Tokens + Card Shadow Standards to globals.css

**Files:**
- Modify: `frontend/app/globals.css:23` (after existing color tokens, inside `@theme inline`)

- [ ] **Step 1: Add gradient and shadow tokens**

Add after the existing `--color-luka-*` variables inside the `@theme inline` block:

```css
/* Direction icon gradients (used as inline styles, documented here for reference) */
/* Expense: linear-gradient(135deg, #fef2f2, #fecaca) */
/* Income:  linear-gradient(135deg, #ecfdf5, #d1fae5) */

/* Card shadow scale */
--shadow-card:     0 1px 3px rgba(0,0,0,0.03);
--shadow-card-hover: 0 2px 8px rgba(0,0,0,0.06);
--shadow-elevated: 0 -4px 24px rgba(0,0,0,0.12);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat(ui): add card shadow scale and gradient token docs"
```

---

## Task 3: Bottom Sheet Component

**Files:**
- Create: `frontend/components/ui/bottom-sheet.tsx`

- [ ] **Step 1: Create the bottom sheet component**

```tsx
"use client";
import { useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);

  // Trap focus inside sheet
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    // Prevent body scroll
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 transition-opacity duration-200"
        onClick={onClose}
      />
      {/* Sheet */}
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-[0_-4px_24px_rgba(0,0,0,0.12)] animate-slide-up max-h-[70vh] flex flex-col"
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 rounded-full bg-slate-300" />
        </div>
        {/* Title */}
        {title && (
          <div className="px-5 pb-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          </div>
        )}
        {/* Content */}
        <div className="overflow-y-auto flex-1 px-5 py-3">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
```

- [ ] **Step 2: Add slide-up animation to globals.css**

Add at the end of `globals.css`:

```css
@keyframes slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.animate-slide-up {
  animation: slide-up 300ms ease-out;
}
```

- [ ] **Step 3: Verify bottom sheet renders**

Temporarily import and render the bottom sheet in a page with `open={true}` to verify:
- Backdrop shows
- Sheet slides up from bottom
- Escape key closes it
- Backdrop click closes it
- Content scrolls if tall
- Remove test code after verification.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ui/bottom-sheet.tsx frontend/app/globals.css
git commit -m "feat(ui): add reusable BottomSheet component for mobile interactions"
```

---

## Task 4: TransactionCard Component — New Card-Based Row

**Files:**
- Create: `frontend/app/(dashboard)/components/TransactionCard.tsx`
- Reference: `frontend/app/(dashboard)/components/RecentTransactions.tsx` (for existing logic)

- [ ] **Step 1: Create TransactionCard component**

This component renders a single transaction as a card. It handles:
- Direction icon with gradient background
- Merchant name (truncated) + amount (right-aligned, color-coded)
- Bank name + category badge + split badge on second line
- Optional `compact` mode for dashboard (non-interactive badges)
- Optional `onCategoryTap` and `onSplitTap` callbacks for editing

```tsx
"use client";
import { TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/app/lib/api";

const SPLIT_STYLES: Record<string, { label: string; className: string }> = {
  personal: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  partner: { label: "Pareja", className: "bg-purple-50 text-purple-600" },
  shared: { label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
};

function toTitleCase(str: string) {
  return str.toLowerCase().split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatCLP(amount: number) {
  return `$${Math.round(amount).toLocaleString("es-CL")}`;
}

interface TransactionCardProps {
  txn: Transaction;
  compact?: boolean;
  currentCategory?: string | null;
  onCategoryTap?: (txn: Transaction) => void;
  onSplitTap?: (txn: Transaction) => void;
}

export function TransactionCard({
  txn,
  compact = false,
  currentCategory,
  onCategoryTap,
  onSplitTap,
}: TransactionCardProps) {
  const isOutflow = txn.transaction_type !== "income";
  const split = SPLIT_STYLES[txn.split_type ?? "personal"] ?? SPLIT_STYLES.personal;
  const category = currentCategory !== undefined ? currentCategory : txn.category;

  return (
    <div className="bg-white rounded-xl p-3.5 border border-slate-100 shadow-[var(--shadow-card)]">
      <div className="flex items-center gap-3">
        {/* Direction icon */}
        <div
          className="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center shrink-0"
          style={{
            background: isOutflow
              ? "linear-gradient(135deg, #fef2f2, #fecaca)"
              : "linear-gradient(135deg, #ecfdf5, #d1fae5)",
          }}
        >
          {isOutflow ? (
            <TrendingDown size={16} className="text-red-400" strokeWidth={2.5} />
          ) : (
            <TrendingUp size={16} className="text-emerald-500" strokeWidth={2.5} />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Line 1: Merchant + Amount */}
          <div className="flex justify-between items-baseline gap-2">
            <p className="text-sm font-semibold text-luka-dark truncate">
              {toTitleCase(txn.raw_merchant_name)}
            </p>
            <span
              className={cn(
                "text-[15px] font-bold tabular-nums shrink-0",
                isOutflow ? "text-luka-dark" : "text-luka-success"
              )}
            >
              {isOutflow
                ? formatCLP(Math.abs(Number(txn.amount)))
                : `+${formatCLP(Math.abs(Number(txn.amount)))}`}
            </span>
          </div>

          {/* Line 2: Bank + Category + Split */}
          <div className="flex justify-between items-center mt-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-[10px] text-slate-400 shrink-0">
                {txn.bank_name ? toTitleCase(txn.bank_name) : "—"}
              </span>
              <button
                onClick={compact ? undefined : () => onCategoryTap?.(txn)}
                disabled={compact}
                className={cn(
                  "text-[10px] font-medium px-1.5 py-0.5 rounded",
                  category
                    ? "bg-slate-100 text-slate-600"
                    : "bg-amber-50 text-amber-600",
                  !compact && "cursor-pointer hover:opacity-80"
                )}
              >
                {category ?? "Sin categoría"}
              </button>
            </div>
            <button
              onClick={compact ? undefined : () => onSplitTap?.(txn)}
              disabled={compact}
              className={cn(
                "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0",
                split.className,
                !compact && "cursor-pointer hover:opacity-80"
              )}
            >
              {split.label}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify card renders correctly**

Import TransactionCard into the transactions page temporarily in place of one RecentTransactions row to verify layout, truncation, colors. Check on both mobile (375px) and desktop (1280px) widths.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(dashboard)/components/TransactionCard.tsx
git commit -m "feat(ui): add TransactionCard component with card-based layout"
```

---

## Task 5: Category Bottom Sheet (Mobile Editor)

**Files:**
- Create: `frontend/app/(dashboard)/components/CategoryBottomSheet.tsx`
- Reference: `frontend/app/(dashboard)/components/RecentTransactions.tsx:8-34` (category lists)

- [ ] **Step 1: Create CategoryBottomSheet**

```tsx
"use client";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { cn } from "@/lib/utils";

const EXPENSE_CATEGORIES = [
  "Alimentación", "Supermercado", "Transporte", "Combustible",
  "Entretenimiento", "Salud", "Farmacia", "Hogar",
  "Ropa", "Tecnología", "Educación", "Viajes", "Servicios", "Otros",
];

const INCOME_CATEGORIES = [
  "Sueldo", "Freelance", "Inversiones", "Arriendo",
  "Bono", "Transferencia de terceros", "Deuda pendiente", "Otros ingresos",
];

interface CategoryBottomSheetProps {
  open: boolean;
  onClose: () => void;
  currentCategory: string | null;
  isIncome: boolean;
  onSelect: (category: string | null) => void;
}

export function CategoryBottomSheet({
  open,
  onClose,
  currentCategory,
  isIncome,
  onSelect,
}: CategoryBottomSheetProps) {
  const categories = isIncome ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

  function handleSelect(cat: string | null) {
    onSelect(cat);
    onClose();
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Categoría">
      <button
        onClick={() => handleSelect(null)}
        className="w-full text-left px-3 py-2.5 text-sm text-slate-400 hover:bg-slate-50 rounded-lg"
      >
        Sin categoría
      </button>
      <div className="h-px bg-slate-100 my-1" />
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => handleSelect(cat)}
          className={cn(
            "w-full text-left px-3 py-2.5 text-sm hover:bg-blue-50 hover:text-luka-primary rounded-lg transition-colors",
            currentCategory === cat
              ? "text-luka-primary font-semibold bg-blue-50"
              : "text-slate-700"
          )}
        >
          {cat}
        </button>
      ))}
    </BottomSheet>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/(dashboard)/components/CategoryBottomSheet.tsx
git commit -m "feat(ui): add CategoryBottomSheet for mobile category editing"
```

---

## Task 6: Split Type Editor + Backend Endpoint

**Files:**
- Create: `frontend/app/(dashboard)/components/SplitTypeEditor.tsx`
- Modify: `frontend/app/lib/api.ts:294` (add new API method)
- Modify: `backend/modules/transactions/schemas.py` (add new schema)
- Modify: `backend/modules/transactions/service.py` (add new service function)
- Modify: `backend/modules/transactions/router.py` (add PATCH endpoint)

- [ ] **Step 1: Add schema for split type update**

In `backend/modules/transactions/schemas.py`, add alongside `CategoryUpdateRequest`:

```python
from typing import Literal

class SplitTypeUpdateRequest(BaseModel):
    split_type: Literal["personal", "shared", "partner"]
```

- [ ] **Step 2: Add service function**

In `backend/modules/transactions/service.py`, add a function following the `update_category` pattern:

```python
async def update_split_type(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, split_type: str
) -> bool:
    """Update transaction split type. Returns False if not found or not owned."""
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False
    txn.split_type = split_type
    await db.commit()
    return True
```

- [ ] **Step 3: Add router endpoint**

In `backend/modules/transactions/router.py`, add the endpoint following the existing `update_category` pattern. Import `SplitTypeUpdateRequest` from schemas:

```python
from modules.transactions.schemas import TransactionResponse, CategoryUpdateRequest, SplitTypeUpdateRequest

@router.patch("/{transaction_id}/split-type")
async def update_split_type(
    transaction_id: uuid.UUID,
    body: SplitTypeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_split_type(db, transaction_id, current_user.id, body.split_type)
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}
```

- [ ] **Step 2: Add API client method**

In `frontend/app/lib/api.ts`, add after the `updateTransactionCategory` method (around line 298):

```typescript
updateTransactionSplitType: (transactionId: string, splitType: string) =>
  apiFetch<{ ok: boolean }>(`/transactions/${transactionId}/split-type`, {
    method: "PATCH",
    body: JSON.stringify({ split_type: splitType }),
  }),
```

- [ ] **Step 3: Create SplitTypeEditor component**

```tsx
"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type Transaction } from "@/app/lib/api";

const SPLIT_OPTIONS = [
  { value: "personal", label: "Personal", className: "bg-blue-50 text-blue-600" },
  { value: "shared", label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
  { value: "partner", label: "Pareja", className: "bg-purple-50 text-purple-600" },
];

interface SplitTypeEditorProps {
  txn: Transaction;
  isMobile: boolean;
}

export function SplitTypeEditor({ txn, isMobile }: SplitTypeEditorProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localSplit, setLocalSplit] = useState(txn.split_type ?? "personal");
  const queryClient = useQueryClient();

  const current = SPLIT_OPTIONS.find((o) => o.value === localSplit) ?? SPLIT_OPTIONS[0];

  async function handleSelect(value: string) {
    setOpen(false);
    if (value === localSplit) return;
    setSaving(true);
    setLocalSplit(value); // optimistic
    try {
      await api.updateTransactionSplitType(txn.id, value);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      setLocalSplit(txn.split_type ?? "personal"); // revert
    } finally {
      setSaving(false);
    }
  }

  if (isMobile) {
    return (
      <>
        <button
          onClick={() => setOpen(true)}
          disabled={saving}
          className={cn(
            "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 cursor-pointer hover:opacity-80",
            current.className,
            saving && "opacity-50"
          )}
        >
          {current.label}
        </button>
        <BottomSheet open={open} onClose={() => setOpen(false)} title="Tipo de gasto">
          {SPLIT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleSelect(opt.value)}
              className={cn(
                "w-full text-left px-3 py-2.5 text-sm rounded-lg transition-colors",
                localSplit === opt.value
                  ? "font-semibold bg-blue-50 text-luka-primary"
                  : "text-slate-700 hover:bg-slate-50"
              )}
            >
              <span className={cn("inline-block w-2 h-2 rounded-full mr-2", opt.className)} />
              {opt.label}
            </button>
          ))}
        </BottomSheet>
      </>
    );
  }

  // Desktop: inline dropdown
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className={cn(
          "flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80",
          current.className,
          saving && "opacity-50"
        )}
      >
        {current.label}
        <ChevronDown size={8} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[120px]">
            {SPLIT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleSelect(opt.value)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                  localSplit === opt.value ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Test backend endpoint**

Run: `cd backend && python -m pytest tests/ -k split -v` (or manually test via curl if no test exists).
Verify: PATCH returns `{ ok: true, split_type: "shared" }`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/transactions/router.py frontend/app/lib/api.ts frontend/app/(dashboard)/components/SplitTypeEditor.tsx
git commit -m "feat: add split type editing — backend endpoint + frontend editor component"
```

---

## Task 7: Collapsible Filter Panel (Mobile)

**Files:**
- Create: `frontend/app/(dashboard)/components/FilterPanel.tsx`

- [ ] **Step 1: Create FilterPanel component**

This component wraps the existing filter controls in a collapsible panel for mobile. On desktop, it renders children directly (no collapse behavior).

```tsx
"use client";
import { useState } from "react";
import { SlidersHorizontal, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface FilterPanelProps {
  activeCount: number;
  onClear: () => void;
  searchValue: string;
  onSearchChange: (v: string) => void;
  children: React.ReactNode; // filter dropdowns
}

export function FilterPanel({
  activeCount,
  onClear,
  searchValue,
  onSearchChange,
  children,
}: FilterPanelProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <>
      {/* Mobile header buttons — hidden on lg+ */}
      <div className="flex items-center gap-2 lg:hidden">
        {/* Search toggle */}
        <button
          onClick={() => setSearchOpen((v) => !v)}
          className="w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)]"
        >
          <Search size={16} className="text-slate-500" />
        </button>
        {/* Filter toggle */}
        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="relative w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)]"
        >
          <SlidersHorizontal size={16} className="text-slate-500" />
          {activeCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-luka-primary text-white text-[9px] font-bold flex items-center justify-center">
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {/* Mobile search bar — slides in */}
      {searchOpen && (
        <div className="lg:hidden">
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              autoFocus
              placeholder="Buscar comercio, banco o categoría..."
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full h-9 pl-8 pr-9 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
            />
            <button
              onClick={() => { setSearchOpen(false); onSearchChange(""); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Mobile collapsible filter panel */}
      {filtersOpen && (
        <div className="lg:hidden bg-white rounded-xl border border-slate-100 p-4 shadow-[var(--shadow-card)] space-y-3">
          {children}
          {activeCount > 0 && (
            <button
              onClick={() => { onClear(); setFiltersOpen(false); }}
              className="text-xs text-luka-primary font-medium hover:underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {/* Desktop filters — always visible, hidden on mobile */}
      <div className="hidden lg:flex flex-wrap items-center gap-2">
        {/* Desktop search */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar comercio, banco o categoría..."
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full h-8 pl-8 pr-3 rounded-lg border border-slate-200 bg-white text-[11px] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
          />
        </div>
        {children}
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/(dashboard)/components/FilterPanel.tsx
git commit -m "feat(ui): add FilterPanel with mobile collapse and desktop inline modes"
```

---

## Task 8: Refactor RecentTransactions — Date Grouping + TransactionCard

**Files:**
- Modify: `frontend/app/(dashboard)/components/RecentTransactions.tsx`

- [ ] **Step 1: Add useIsMobile hook**

Create a simple hook at the top of the file (or extract to `frontend/app/lib/hooks/useIsMobile.ts` if preferred):

```tsx
import { useState, useEffect } from "react";

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 1023px)");
    setIsMobile(mql.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);
  return isMobile;
}
```

- [ ] **Step 2: Add date grouping utility**

```tsx
function getDateKey(iso: string): string {
  return iso.split("T")[0]; // "2026-03-23"
}

function formatDateHeader(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.getTime() === today.getTime()) {
    return `Hoy, ${date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" })}`;
  }
  if (date.getTime() === yesterday.getTime()) {
    return `Ayer, ${date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" })}`;
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" });
  }
  return date.toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
}

function groupByDate(txns: Transaction[]): Map<string, Transaction[]> {
  const groups = new Map<string, Transaction[]>();
  for (const txn of txns) {
    const key = getDateKey(txn.transaction_date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(txn);
  }
  return groups;
}
```

- [ ] **Step 3: Rewrite the RecentTransactions component**

Keep the existing `CategoryCell` component (lines 66-140) for desktop inline editing. Rewrite the main export:

```tsx
interface RecentTransactionsProps {
  transactions: Transaction[];
  compact?: boolean;
}

export function RecentTransactions({ transactions, compact = false }: RecentTransactionsProps) {
  const isMobile = useIsMobile();
  const [categorySheet, setCategorySheet] = useState<Transaction | null>(null);
  const [localCategories, setLocalCategories] = useState<Map<string, string | null>>(new Map());
  const queryClient = useQueryClient();

  if (!transactions.length) {
    return (
      <div className="py-12 flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
          <TrendingDown size={18} className="text-slate-400" />
        </div>
        <p className="text-xs text-luka-muted">No hay transacciones.</p>
      </div>
    );
  }

  async function handleCategorySelect(txn: Transaction, category: string | null) {
    setLocalCategories((prev) => new Map(prev).set(txn.id, category));
    try {
      await api.updateTransactionCategory(txn.id, category);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      setLocalCategories((prev) => { const m = new Map(prev); m.delete(txn.id); return m; });
    }
  }

  const dateGroups = groupByDate(transactions);

  return (
    <div className="space-y-1">
      {Array.from(dateGroups.entries()).map(([dateKey, txns]) => (
        <div key={dateKey}>
          {/* Date header */}
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest pt-3 pb-1.5">
            {formatDateHeader(dateKey)}
          </p>
          {/* Transaction cards */}
          <div className="space-y-1.5">
            {txns.map((txn) => {
              const currentCat = localCategories.has(txn.id) ? localCategories.get(txn.id)! : txn.category;

              if (compact) {
                return <TransactionCard key={txn.id} txn={txn} compact />;
              }

              if (isMobile) {
                return (
                  <TransactionCard
                    key={txn.id}
                    txn={txn}
                    currentCategory={currentCat}
                    onCategoryTap={(t) => setCategorySheet(t)}
                    onSplitTap={() => {/* SplitTypeEditor handles its own bottom sheet */}}
                  />
                );
              }

              // Desktop: render card with inline CategoryCell overlay + SplitTypeEditor
              return (
                <div key={txn.id} className="relative group">
                  <TransactionCard
                    txn={txn}
                    currentCategory={currentCat}
                    onCategoryTap={() => {/* Desktop uses CategoryCell overlay below */}}
                    onSplitTap={() => {/* Desktop uses SplitTypeEditor rendered below */}}
                  />
                  {/* Desktop-only: overlay the category cell and split editor on the card */}
                  {/* Position these absolutely over the badge areas */}
                  <div className="absolute bottom-3 left-[62px] flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400">{txn.bank_name ? toTitleCase(txn.bank_name) : "—"}</span>
                    <CategoryCell txn={txn} />
                  </div>
                  <div className="absolute bottom-3 right-3.5">
                    <SplitTypeEditor txn={txn} isMobile={false} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Mobile category bottom sheet */}
      {categorySheet && (
        <CategoryBottomSheet
          open={!!categorySheet}
          onClose={() => setCategorySheet(null)}
          currentCategory={localCategories.get(categorySheet.id) ?? categorySheet.category}
          isIncome={categorySheet.transaction_type === "income"}
          onSelect={(cat) => handleCategorySelect(categorySheet, cat)}
        />
      )}
    </div>
  );
}
```

Add the necessary imports at the top of the file:
```tsx
import { TransactionCard } from "./TransactionCard";
import { CategoryBottomSheet } from "./CategoryBottomSheet";
import { SplitTypeEditor } from "./SplitTypeEditor";
```

**Important:** The desktop overlay approach (absolute positioning CategoryCell and SplitTypeEditor over the TransactionCard) may need fine-tuning of pixel positions. An alternative is to pass `renderCategory` and `renderSplit` render props to TransactionCard — adjust during implementation if the overlay approach is too fragile.

- [ ] **Step 4: Verify in browser**

Check transactions page:
- Mobile (375px): Card-based rows, date headers, tapping category badge opens bottom sheet, split badge also opens bottom sheet via SplitTypeEditor
- Desktop (1280px): Card-based rows, date headers, inline CategoryCell dropdown, inline SplitTypeEditor dropdown
- Dashboard compact mode: Cards with non-interactive badges, no editing

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/components/RecentTransactions.tsx
git commit -m "feat(ui): refactor RecentTransactions with card layout, date grouping, and mobile bottom sheets"
```

---

## Task 9: Transactions Page — Balance Cards, Filters, Tabs

**Files:**
- Modify: `frontend/app/(dashboard)/transactions/page.tsx`
- Reference: `frontend/components/ui/tabs.tsx` (verify "line" variant)

- [ ] **Step 1: Refactor SummaryBar for mobile stacking**

Change the balance cards grid from `grid-cols-3` (line 93) to `grid-cols-1 lg:grid-cols-3`. Each card on mobile becomes a full-width row. Keep the sync button as a standalone row above the cards.

- [ ] **Step 2: Replace inline filters with FilterPanel**

Replace the filter section (lines 348-405) with the FilterPanel component. Move the filter dropdowns as children of FilterPanel. Calculate `activeCount` from the filter state:

```tsx
const activeCount = [
  selectedMonth !== "all" ? 1 : 0,
  selectedBank !== "all" ? 1 : 0,
  selectedCategory !== "all" ? 1 : 0,
  onlyUncategorized ? 1 : 0,
].reduce((a, b) => a + b, 0);
```

Add a `clearFilters` function that resets all filter state to defaults.

- [ ] **Step 3: Switch tabs to underline variant**

Change TabsList from:
```tsx
<TabsList className="bg-white border border-slate-100 rounded-xl p-1 h-auto">
```
to:
```tsx
<TabsList variant="line" className="border-b border-slate-200">
```

The existing `line` variant in `tabs.tsx` uses `after:bg-foreground` (dark/slate-900) for the underline. Update `frontend/components/ui/tabs.tsx` line 64 to use blue instead:

```tsx
// Change: after:bg-foreground
// To:     after:bg-luka-primary
```

Also on line 63, add blue active text color for the line variant:
```tsx
"group-data-[variant=line]/tabs-list:data-active:text-luka-primary"
```

Also update the TabsTrigger classes in `transactions/page.tsx` — remove the old pill-style overrides:
```tsx
// Remove: data-[state=active]:bg-luka-primary data-[state=active]:text-white data-[state=active]:shadow-sm
```

Add tab switch → page reset: in the `Tabs` component, add `onValueChange={() => setPage(1)}`.

- [ ] **Step 4: Simplify mobile pagination**

In TransactionTable, hide First/Last buttons on mobile (use `lg` breakpoint to match the project-wide mobile/desktop split):
```tsx
<button ... className="... hidden lg:flex ...">  {/* First page */}
<button ... className="... hidden lg:flex ...">  {/* Last page */}
```

- [ ] **Step 5: Verify in browser**

- Mobile: Balance cards stacked, filter panel collapsed, underline tabs, simplified pagination
- Desktop: 3-column balance cards, inline filters, underline tabs, full pagination

- [ ] **Step 6: Commit**

```bash
git add frontend/app/(dashboard)/transactions/page.tsx
git commit -m "feat(ui): redesign transactions page — stacked balances, collapsible filters, underline tabs"
```

---

## Task 10: Dashboard Page — KPI Stacking + Chart Layout

**Files:**
- Modify: `frontend/app/(dashboard)/page.tsx:92-127,130-160,163-171`
- Modify: `frontend/app/(dashboard)/components/KpiCard.tsx`

- [ ] **Step 1: Update KPI card grid for mobile stacking**

In `page.tsx`, change the KPI grid (around line 92) from `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` to `grid-cols-1 lg:grid-cols-3` (skip the 2-col intermediate).

In `KpiCard.tsx`, update card styling to use new shadow standard:
```tsx
className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4 ..."
```

- [ ] **Step 2: Update chart grid**

Ensure the chart grid (around line 130) stacks properly on mobile: `grid-cols-1 lg:grid-cols-3`. Both charts should be full-width on mobile.

- [ ] **Step 3: Update recent transactions section**

The recent transactions already use `RecentTransactions` with `compact={true}`. After Task 8's refactor, this will automatically render as card-based rows. Verify it works.

- [ ] **Step 4: Verify in browser**

- Mobile: KPIs stacked, charts stacked full-width, recent transactions as cards
- Desktop: 3-col KPIs, 2/3+1/3 chart grid, card-based recent transactions

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/page.tsx frontend/app/(dashboard)/components/KpiCard.tsx
git commit -m "feat(ui): redesign dashboard — stacked KPIs, polished charts, card transactions"
```

---

## Task 11: Budgets Page — Income Card, Month Selector, Sliders, Waterfall

**Files:**
- Modify: `frontend/app/(dashboard)/budgets/page.tsx`
- Modify: `frontend/app/(dashboard)/components/AllocationCard.tsx:88-124` (sliders)
- Modify: `frontend/app/(dashboard)/components/WaterfallCards.tsx`

- [ ] **Step 1: Upgrade month selector**

Replace the plain `‹`/`›` text buttons (lines 55-69) with proper icon buttons:

```tsx
<div className="flex items-center gap-3">
  <button
    onClick={prevMonth}
    className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary transition-colors shadow-[var(--shadow-card)]"
  >
    <ChevronLeft size={16} className="text-slate-600" />
  </button>
  <span className="text-sm font-semibold text-luka-dark capitalize min-w-[140px] text-center">
    {selectedMonth.toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
  </span>
  <button
    onClick={nextMonth}
    disabled={isCurrentMonth}
    className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary disabled:opacity-30 transition-colors shadow-[var(--shadow-card)]"
  >
    <ChevronRight size={16} className="text-slate-600" />
  </button>
</div>
```

Add `ChevronLeft, ChevronRight` to the lucide imports.

- [ ] **Step 2: Promote income to a card**

Replace the plain text income display (lines 71-80) with a card:

```tsx
{budget && budget.income > 0 ? (
  <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
    <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Ingresos del mes</p>
    <p className="text-[22px] font-bold text-luka-dark mt-1 tabular-nums">{CLP(budget.income)}</p>
  </div>
) : (
  <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
    <p className="text-sm text-slate-400">Conecta tu banco para ver tus ingresos</p>
  </div>
)}
```

- [ ] **Step 3: Polish PaceChart card wrapper**

In `budgets/page.tsx`, update the PaceChart card wrapper (around line 84) to use the new shadow standard:
```tsx
<div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
```
(Replace the existing `border-gray-100` with `border-slate-100` and add `shadow-[var(--shadow-card)]`.)

- [ ] **Step 4: Make sliders touch-friendly in AllocationCard**

In `AllocationCard.tsx`, update the slider input elements (around lines 96-104 and 115-123):

Add custom CSS for the sliders. In the component or globals.css, add styles for larger thumb and track:

```css
/* In globals.css */
input[type="range"].luka-slider {
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  background: #e2e8f0;
  border-radius: 9999px;
  outline: none;
}
input[type="range"].luka-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 24px;
  height: 24px;
  background: #2563eb;
  border-radius: 50%;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}
input[type="range"].luka-slider::-moz-range-thumb {
  width: 24px;
  height: 24px;
  background: #2563eb;
  border-radius: 50%;
  cursor: pointer;
  border: 3px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}
```

Add `className="luka-slider w-full"` to both range inputs. Ensure `step={5}` is already set (it is).

Also update the card wrapper to use the new shadow standard.

- [ ] **Step 5: Polish WaterfallCards**

In `WaterfallCards.tsx`:
- Update card wrappers to use `shadow-[var(--shadow-card)]` and `rounded-xl`
- Increase progress bar height from default to `h-2 rounded-full`
- Make available balance text larger: `text-lg font-bold`
- Green if positive, red if exceeded (already partially implemented)

- [ ] **Step 6: Verify in browser**

- Month selector: larger tap targets, centered label
- Income: displayed as a card
- PaceChart: card matches new shadow standard
- Sliders: 24px thumb, 6px track, snap to 5%
- Waterfall: polished shadows, taller progress bars

- [ ] **Step 7: Commit**

```bash
git add frontend/app/(dashboard)/budgets/page.tsx frontend/app/(dashboard)/components/AllocationCard.tsx frontend/app/(dashboard)/components/WaterfallCards.tsx frontend/app/globals.css
git commit -m "feat(ui): redesign budgets page — income card, touch sliders, polished waterfall"
```

---

## Task 12: Final Polish + Cross-Page Verification

**Files:**
- All modified files

- [ ] **Step 1: Cross-page mobile verification**

Test at 375px width (iPhone SE) and 390px (iPhone 14):
- [ ] Transactions: stacked balances, collapsed filters, card rows, date headers, bottom sheets
- [ ] Dashboard: stacked KPIs, stacked charts, card transactions
- [ ] Budgets: income card, large sliders, polished waterfall

- [ ] **Step 2: Cross-page desktop verification**

Test at 1280px and 1440px:
- [ ] Transactions: 3-col balances, inline filters, card rows, inline dropdowns
- [ ] Dashboard: 3-col KPIs, 2/3+1/3 charts, card transactions
- [ ] Budgets: income card, sliders, waterfall

- [ ] **Step 3: Check for regressions**

- DM Sans renders everywhere (no fallback to system font)
- Bottom nav still works on mobile
- Sidebar still works on desktop
- No horizontal scrolling on any mobile page
- All interactive elements have minimum 44px touch targets
- Category editing still works (inline on desktop, bottom sheet on mobile)
- Split type editing works (new feature)

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ui): frontend redesign Tier 1 — polish and cross-page verification"
```
