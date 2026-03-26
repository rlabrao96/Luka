# Household Enhancement & Subscriptions Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-category spending breakdown with settlement suggestions to the Household tab, and a new Subscriptions tab that auto-detects recurring expenses with a timeline view.

**Architecture:** Two independent feature tracks that share no code. Household enhancement extends existing `modules/households/` with new SQL aggregation queries and a `split_ratio` column. Subscriptions is a new read-only `modules/subscriptions/` module that runs detection queries over existing transactions. Frontend adds new components to the household page and a new `/subscriptions` route.

**Tech Stack:** FastAPI + SQLAlchemy raw SQL (text()) for aggregation queries, Alembic for migration, Next.js 14 + Tailwind + shadcn/ui + lucide-react for frontend.

**Spec:** `docs/superpowers/specs/2026-03-26-household-subscriptions-design.md`

---

## File Map

### Feature 1: Household Enhancement

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/alembic/versions/019_household_split_ratio.py` | Migration: add `split_ratio` JSONB column |
| Modify | `backend/modules/households/models.py` | Add `split_ratio` field to Household model |
| Modify | `backend/modules/households/schemas.py` | Add `SplitRatioRequest`, `SettlementResponse`, `CategoryBreakdownRow` schemas |
| Modify | `backend/modules/households/service.py` | Add `get_category_breakdown()`, `get_settlement()`, `update_split_ratio()` |
| Modify | `backend/modules/households/router.py` | Add `GET /settlement`, `GET /split-ratio`, `PATCH /split-ratio` endpoints |
| Create | `backend/tests/test_household_settlement.py` | Tests for settlement + category breakdown logic |
| Modify | `frontend/app/lib/api.ts` | Add API methods + types for settlement, split-ratio, category breakdown |
| Modify | `frontend/app/lib/hooks/useHousehold.ts` | Add `useSettlement()`, `useSplitRatio()`, `useUpdateSplitRatio()` hooks |
| Modify | `frontend/app/(dashboard)/household/page.tsx` | Rewrite with HouseholdHero + CategoryBreakdownTable + SettlementCard |
| Create | `frontend/app/(dashboard)/household/SplitRatioModal.tsx` | Modal to edit split ratio |

### Feature 2: Subscriptions Tab

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `backend/modules/subscriptions/__init__.py` | Module init |
| Create | `backend/modules/subscriptions/service.py` | `detect_recurring()` query logic |
| Create | `backend/modules/subscriptions/schemas.py` | `RecurringExpenseResponse` schema |
| Create | `backend/modules/subscriptions/router.py` | `GET /subscriptions/detected` endpoint |
| Modify | `backend/main.py` | Register subscriptions router |
| Create | `backend/tests/test_subscriptions.py` | Tests for recurring detection algorithm |
| Modify | `frontend/app/lib/api.ts` | Add `getSubscriptions()` + `RecurringExpense` type |
| Create | `frontend/app/lib/hooks/useSubscriptions.ts` | `useSubscriptions()` hook |
| Create | `frontend/app/(dashboard)/subscriptions/page.tsx` | Subscriptions page with summary, timeline, alerts |
| Modify | `frontend/app/(dashboard)/components/Sidebar.tsx` | Add Suscripciones nav item |
| Modify | `frontend/app/(dashboard)/components/BottomNav.tsx` | Add Suscripciones nav item |

---

## Track A: Household Enhancement

### Task 1: Alembic Migration — add split_ratio column

**Files:**
- Create: `backend/alembic/versions/019_household_split_ratio.py`

- [ ] **Step 1: Create migration file**

```python
"""Add split_ratio JSONB column to households."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = "019"
down_revision = "018"


def upgrade() -> None:
    op.add_column(
        "households",
        sa.Column("split_ratio", JSONB, server_default='[50, 50]', nullable=False),
    )


def downgrade() -> None:
    op.drop_column("households", "split_ratio")
```

- [ ] **Step 2: Update Household model**

Modify `backend/modules/households/models.py` — add to the Household class:

```python
from sqlalchemy.dialects.postgresql import JSONB

split_ratio = Column(JSONB, nullable=False, server_default='[50, 50]')
```

- [ ] **Step 3: Run migration**

```bash
cd backend && python -m alembic upgrade head
```

Expected: migration applies cleanly, `households` table has `split_ratio` column.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/019_household_split_ratio.py backend/modules/households/models.py
git commit -m "feat: add split_ratio JSONB column to households table"
```

---

### Task 2: Backend — Settlement & Category Breakdown Schemas

**Files:**
- Modify: `backend/modules/households/schemas.py`

- [ ] **Step 1: Add new schemas**

Append to `backend/modules/households/schemas.py`:

```python
from decimal import Decimal


class MemberTotal(BaseModel):
    user_id: str
    full_name: str
    amount: Decimal
    pct: float


class CategoryBreakdownRow(BaseModel):
    category: str
    member_totals: list[MemberTotal]
    total: Decimal
    pct_of_overall: float


class HouseholdSummaryResponse(BaseModel):
    total: Decimal
    members: list[MemberTotal]
    by_category: list[CategoryBreakdownRow]


class SettlementResponse(BaseModel):
    from_user_id: str
    from_user_name: str
    to_user_id: str
    to_user_name: str
    amount: Decimal
    split_ratio: list[int]
    month: str


class SplitRatioRequest(BaseModel):
    ratio: list[int]


class SplitRatioResponse(BaseModel):
    split_ratio: list[int]
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/households/schemas.py
git commit -m "feat: add schemas for settlement, category breakdown, split ratio"
```

---

### Task 3: Backend — Category Breakdown Service

**Files:**
- Modify: `backend/modules/households/service.py`
- Create: `backend/tests/test_household_settlement.py`

- [ ] **Step 1: Write test for category breakdown**

Create `backend/tests/test_household_settlement.py`:

```python
import pytest
from decimal import Decimal
from modules.households.service import build_category_breakdown


def test_build_category_breakdown_groups_by_category():
    """Given raw rows from SQL, builds category breakdown with member totals and percentages."""
    rows = [
        {"user_id": "u1", "full_name": "Rodrigo", "category": "Supermercado", "amount": Decimal("52300")},
        {"user_id": "u2", "full_name": "María", "category": "Supermercado", "amount": Decimal("78400")},
        {"user_id": "u1", "full_name": "Rodrigo", "category": "Restaurantes", "amount": Decimal("45200")},
        {"user_id": "u2", "full_name": "María", "category": "Restaurantes", "amount": Decimal("32100")},
    ]
    result = build_category_breakdown(rows)
    assert len(result) == 2

    supermercado = next(r for r in result if r["category"] == "Supermercado")
    assert supermercado["total"] == Decimal("130700")
    assert len(supermercado["member_totals"]) == 2

    rodrigo = next(m for m in supermercado["member_totals"] if m["user_id"] == "u1")
    assert rodrigo["amount"] == Decimal("52300")
    assert round(rodrigo["pct"], 1) == 40.0


def test_build_category_breakdown_empty():
    """Returns empty list when no rows."""
    result = build_category_breakdown([])
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_household_settlement.py -v -k "build_category"
```

Expected: ImportError — `build_category_breakdown` doesn't exist yet.

- [ ] **Step 3: Implement `build_category_breakdown` and `get_category_breakdown`**

Add to `backend/modules/households/service.py`:

```python
from collections import defaultdict


def build_category_breakdown(rows: list[dict]) -> list[dict]:
    """Pure function: groups SQL rows into category breakdown with percentages."""
    if not rows:
        return []

    cats: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        cats[row["category"]].append(row)

    grand_total = sum(r["amount"] for r in rows)
    result = []
    for category, members in sorted(cats.items(), key=lambda x: sum(m["amount"] for m in x[1]), reverse=True):
        cat_total = sum(m["amount"] for m in members)
        member_totals = [
            {
                "user_id": str(m["user_id"]),
                "full_name": m["full_name"],
                "amount": m["amount"],
                "pct": round(float(m["amount"]) / float(cat_total) * 100, 1) if cat_total else 0,
            }
            for m in members
        ]
        result.append({
            "category": category,
            "member_totals": member_totals,
            "total": cat_total,
            "pct_of_overall": round(float(cat_total) / float(grand_total) * 100, 1) if grand_total else 0,
        })
    return result


async def get_category_breakdown(db: AsyncSession, household_id, month: str | None = None):
    """Returns per-category spending breakdown for shared transactions."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"

    sql = text(f"""
        SELECT u.id AS user_id, u.full_name,
               COALESCE(t.category, 'Sin categoría') AS category,
               COALESCE(SUM(ABS(t.amount)), 0) AS amount
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND {month_clause}
        GROUP BY u.id, u.full_name, COALESCE(t.category, 'Sin categoría')
        ORDER BY amount DESC
    """)
    result = await db.execute(sql, params)
    rows = [dict(r._mapping) for r in result.all()]
    return build_category_breakdown(rows)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_household_settlement.py -v -k "build_category"
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/households/service.py backend/tests/test_household_settlement.py
git commit -m "feat: add category breakdown service for shared transactions"
```

---

### Task 4: Backend — Settlement Calculation Service

**Files:**
- Modify: `backend/modules/households/service.py`
- Modify: `backend/tests/test_household_settlement.py`

- [ ] **Step 1: Write test for settlement calculation**

Append to `backend/tests/test_household_settlement.py`:

```python
from modules.households.service import calculate_settlement


def test_settlement_50_50():
    """With 50/50 split, person who paid less owes their expected share minus what they paid."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("180500")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("294960")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert result["from_user_id"] == "u1"
    assert result["to_user_id"] == "u2"
    assert result["amount"] == Decimal("57230")


def test_settlement_60_40():
    """With 60/40, settlement accounts for unequal expected shares."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("100000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("100000")},
    ]
    # Total = 200000. u1 should pay 60% = 120000, u2 should pay 40% = 80000
    # u1 paid 100000, owes 120000 => u1 underpaid by 20000
    result = calculate_settlement(members, [60, 40])
    assert result["from_user_id"] == "u1"
    assert result["to_user_id"] == "u2"
    assert result["amount"] == Decimal("20000")


def test_settlement_balanced():
    """When both paid their fair share, amount is 0."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("50000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("50000")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert result["amount"] == Decimal("0")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_household_settlement.py -v -k "settlement"
```

Expected: ImportError — `calculate_settlement` doesn't exist.

- [ ] **Step 3: Implement `calculate_settlement` and `get_settlement`**

Add to `backend/modules/households/service.py`:

```python
def calculate_settlement(members: list[dict], split_ratio: list[int]) -> dict:
    """Pure function: calculates who owes whom based on actual spending and ratio."""
    if len(members) != 2:
        return {"from_user_id": "", "from_user_name": "", "to_user_id": "", "to_user_name": "", "amount": Decimal("0")}

    grand_total = sum(m["total"] for m in members)
    if grand_total == 0:
        return {
            "from_user_id": str(members[0]["user_id"]),
            "from_user_name": members[0]["full_name"],
            "to_user_id": str(members[1]["user_id"]),
            "to_user_name": members[1]["full_name"],
            "amount": Decimal("0"),
        }

    expected_0 = grand_total * Decimal(split_ratio[0]) / Decimal(100)
    expected_1 = grand_total * Decimal(split_ratio[1]) / Decimal(100)

    diff_0 = expected_0 - members[0]["total"]  # positive = underpaid
    diff_1 = expected_1 - members[1]["total"]

    if diff_0 > 0:
        return {
            "from_user_id": str(members[0]["user_id"]),
            "from_user_name": members[0]["full_name"],
            "to_user_id": str(members[1]["user_id"]),
            "to_user_name": members[1]["full_name"],
            "amount": diff_0,
        }
    else:
        return {
            "from_user_id": str(members[1]["user_id"]),
            "from_user_name": members[1]["full_name"],
            "to_user_id": str(members[0]["user_id"]),
            "to_user_name": members[0]["full_name"],
            "amount": abs(diff_0),
        }


async def get_settlement(db: AsyncSession, household_id, month: str | None = None):
    """Returns settlement suggestion for the household."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"

    # Get totals per member for shared transactions
    sql = text(f"""
        SELECT u.id AS user_id, u.full_name,
               COALESCE(SUM(ABS(t.amount)), 0) AS total
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND {month_clause}
        GROUP BY u.id, u.full_name
        ORDER BY total DESC
    """)
    result = await db.execute(sql, params)
    members = [dict(r._mapping) for r in result.all()]

    # Get split ratio
    h_result = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    row = h_result.scalar_one_or_none()
    split_ratio = row if row else [50, 50]

    settlement = calculate_settlement(members, split_ratio)
    settlement["split_ratio"] = split_ratio
    settlement["month"] = month or "current"
    return settlement
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_household_settlement.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/households/service.py backend/tests/test_household_settlement.py
git commit -m "feat: add settlement calculation with configurable split ratio"
```

---

### Task 5: Backend — Split Ratio & Settlement Router Endpoints

**Files:**
- Modify: `backend/modules/households/router.py`

- [ ] **Step 1: Add three new endpoints**

Append to `backend/modules/households/router.py`:

```python
from .schemas import (
    SplitRatioRequest,
    SplitRatioResponse,
    SettlementResponse,
    HouseholdSummaryResponse,
)


@router.get("/{household_id}/category-breakdown")
async def category_breakdown(
    household_id: uuid.UUID,
    month: str = Query(default=None, description="YYYY-MM format"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    data = await service.get_category_breakdown(db, household_id, month)
    return data


@router.get("/{household_id}/settlement", response_model=SettlementResponse)
async def settlement(
    household_id: uuid.UUID,
    month: str = Query(default=None, description="YYYY-MM format"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_settlement(db, household_id, month)


@router.get("/{household_id}/split-ratio", response_model=SplitRatioResponse)
async def get_split_ratio(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    result = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    ratio = result.scalar_one_or_none() or [50, 50]
    return {"split_ratio": ratio}


@router.patch("/{household_id}/split-ratio", response_model=SplitRatioResponse)
async def update_split_ratio(
    household_id: uuid.UUID,
    body: SplitRatioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    if len(body.ratio) != 2 or sum(body.ratio) != 100 or any(r < 0 for r in body.ratio):
        raise HTTPException(400, "Ratio must be two non-negative integers summing to 100")
    await db.execute(
        text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
        {"ratio": json.dumps(body.ratio), "id": str(household_id)},
    )
    await db.commit()
    return {"split_ratio": body.ratio}
```

Add these imports at the top of the file if not already present:

```python
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
```

Ensure the existing `from fastapi import ...` line includes `Query`.

- [ ] **Step 2: Commit**

```bash
git add backend/modules/households/router.py
git commit -m "feat: add settlement, category-breakdown, and split-ratio endpoints"
```

---

### Task 6: Frontend — Household API Types & Hooks

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/lib/hooks/useHousehold.ts`

- [ ] **Step 1: Add types to api.ts**

Add these type definitions in the types section of `frontend/app/lib/api.ts`:

```typescript
export interface MemberTotal {
  user_id: string;
  full_name: string;
  amount: number;
  pct: number;
}

export interface CategoryBreakdownRow {
  category: string;
  member_totals: MemberTotal[];
  total: number;
  pct_of_overall: number;
}

export interface SettlementResponse {
  from_user_id: string;
  from_user_name: string;
  to_user_id: string;
  to_user_name: string;
  amount: number;
  split_ratio: number[];
  month: string;
}

export interface SplitRatioResponse {
  split_ratio: number[];
}
```

- [ ] **Step 2: Add API methods**

Add to the `api` object in `frontend/app/lib/api.ts`:

```typescript
getCategoryBreakdown: (householdId: string, month?: string) =>
  apiFetch<CategoryBreakdownRow[]>(
    `/households/${householdId}/category-breakdown${month ? `?month=${month}` : ""}`
  ),
getSettlement: (householdId: string, month?: string) =>
  apiFetch<SettlementResponse>(
    `/households/${householdId}/settlement${month ? `?month=${month}` : ""}`
  ),
getSplitRatio: (householdId: string) =>
  apiFetch<SplitRatioResponse>(`/households/${householdId}/split-ratio`),
updateSplitRatio: (householdId: string, ratio: number[]) =>
  apiFetch<SplitRatioResponse>(`/households/${householdId}/split-ratio`, {
    method: "PATCH",
    body: JSON.stringify({ ratio }),
  }),
```

- [ ] **Step 3: Add hooks**

Append to `frontend/app/lib/hooks/useHousehold.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useCategoryBreakdown(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "category-breakdown", householdId, month],
    queryFn: () => api.getCategoryBreakdown(householdId!, month),
    enabled: !!householdId,
  });
}

export function useSettlement(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "settlement", householdId, month],
    queryFn: () => api.getSettlement(householdId!, month),
    enabled: !!householdId,
  });
}

export function useSplitRatio() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "split-ratio", householdId],
    queryFn: () => api.getSplitRatio(householdId!),
    enabled: !!householdId,
  });
}

export function useUpdateSplitRatio() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ratio: number[]) => api.updateSplitRatio(householdId!, ratio),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useHousehold.ts
git commit -m "feat: add household API types, methods, and hooks for settlement & breakdown"
```

---

### Task 7: Frontend — Rewrite Household Page

**Files:**
- Modify: `frontend/app/(dashboard)/household/page.tsx`
- Create: `frontend/app/(dashboard)/household/SplitRatioModal.tsx`

- [ ] **Step 1: Create SplitRatioModal component**

Create `frontend/app/(dashboard)/household/SplitRatioModal.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUpdateSplitRatio } from "@/app/lib/hooks/useHousehold";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentRatio: number[];
  memberNames: [string, string];
}

export default function SplitRatioModal({ open, onOpenChange, currentRatio, memberNames }: Props) {
  const [left, setLeft] = useState(currentRatio[0]);
  const mutation = useUpdateSplitRatio();

  // Sync state when prop changes (e.g., after external update)
  useEffect(() => setLeft(currentRatio[0]), [currentRatio]);

  const right = 100 - left;
  const valid = left >= 0 && left <= 100;

  function handleSave() {
    if (!valid) return;
    mutation.mutate([left, right], {
      onSuccess: () => onOpenChange(false),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Configurar split</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <label className="text-xs text-slate-500">{memberNames[0]}</label>
              <Input
                type="number"
                min={0}
                max={100}
                value={left}
                onChange={(e) => setLeft(Number(e.target.value))}
                className="text-center text-lg font-bold"
              />
            </div>
            <span className="text-slate-400 font-medium pt-4">/</span>
            <div className="flex-1">
              <label className="text-xs text-slate-500">{memberNames[1]}</label>
              <div className="flex h-10 items-center justify-center rounded-md border bg-slate-50 text-lg font-bold text-slate-600">
                {right}
              </div>
            </div>
          </div>
          {!valid && <p className="text-xs text-red-500">El valor debe estar entre 0 y 100</p>}
          <Button onClick={handleSave} disabled={!valid || mutation.isPending} className="w-full">
            {mutation.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Rewrite household page**

Rewrite `frontend/app/(dashboard)/household/page.tsx` with the approved design:
- Hero card at top (total shared expenses, per-member amounts, contribution bar)
- Month selector dropdown
- Category breakdown table with mini proportion bars and percentages
- Settlement card at bottom with edit button for split ratio
- Keep existing empty state for users without a household
- Keep existing partner stats section

Key components to use: `Card`, `CardContent` from shadcn/ui, `Pencil` icon from lucide-react for the edit button.

Data hooks: `useCategoryBreakdown(month)`, `useSettlement(month)`, `useSplitRatio()`, existing `useHouseholdSummary()`.

Colors: Blue (#3B82F6) for first member, Pink (#EC4899) for second member, matching the approved mockup.

Format amounts using `toLocaleString("es-CL")` for Chilean formatting.

- [ ] **Step 3: Verify it compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No TypeScript errors on the household page.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/(dashboard)/household/page.tsx frontend/app/(dashboard)/household/SplitRatioModal.tsx
git commit -m "feat: rewrite household page with category breakdown and settlement card"
```

---

## Track B: Subscriptions Tab

### Task 8: Backend — Subscriptions Detection Service

**Files:**
- Create: `backend/modules/subscriptions/__init__.py`
- Create: `backend/modules/subscriptions/service.py`
- Create: `backend/tests/test_subscriptions.py`

- [ ] **Step 1: Create module init**

Create empty `backend/modules/subscriptions/__init__.py`.

- [ ] **Step 2: Write test for detection algorithm**

Create `backend/tests/test_subscriptions.py`:

```python
import pytest
from datetime import date
from decimal import Decimal
from modules.subscriptions.service import detect_from_rows, predict_next_date


def test_detect_from_rows_finds_recurring():
    """Merchant appearing in 2+ consecutive months is detected."""
    rows = [
        {"merchant_key": "Netflix", "category": "Streaming", "amount": Decimal("13500"), "tx_date": date(2026, 3, 8), "month": "2026-03", "split_type": "personal"},
        {"merchant_key": "Netflix", "category": "Streaming", "amount": Decimal("12000"), "tx_date": date(2026, 2, 8), "month": "2026-02", "split_type": "personal"},
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    assert result[0]["merchant_name"] == "Netflix"
    assert result[0]["trend"] == "increased"
    assert result[0]["months_seen"] == 2


def test_detect_from_rows_skips_non_consecutive():
    """Merchant appearing in non-consecutive months is NOT detected."""
    rows = [
        {"merchant_key": "Random Shop", "category": "Compras", "amount": Decimal("10000"), "tx_date": date(2026, 3, 5), "month": "2026-03", "split_type": "personal"},
        {"merchant_key": "Random Shop", "category": "Compras", "amount": Decimal("10000"), "tx_date": date(2026, 1, 5), "month": "2026-01", "split_type": "personal"},
    ]
    result = detect_from_rows(rows)
    assert len(result) == 0


def test_detect_from_rows_amount_tolerance():
    """Amounts within 20% are accepted; beyond 20% rejected."""
    # 12000 * 1.20 = 14400. 14500 exceeds tolerance.
    rows_ok = [
        {"merchant_key": "Gym", "category": "Deporte", "amount": Decimal("12000"), "tx_date": date(2026, 3, 1), "month": "2026-03", "split_type": "shared"},
        {"merchant_key": "Gym", "category": "Deporte", "amount": Decimal("14000"), "tx_date": date(2026, 2, 1), "month": "2026-02", "split_type": "shared"},
    ]
    assert len(detect_from_rows(rows_ok)) == 1

    rows_bad = [
        {"merchant_key": "Gym", "category": "Deporte", "amount": Decimal("12000"), "tx_date": date(2026, 3, 1), "month": "2026-03", "split_type": "shared"},
        {"merchant_key": "Gym", "category": "Deporte", "amount": Decimal("20000"), "tx_date": date(2026, 2, 1), "month": "2026-02", "split_type": "shared"},
    ]
    assert len(detect_from_rows(rows_bad)) == 0


def test_predict_next_date_normal():
    assert predict_next_date(date(2026, 3, 15)) == date(2026, 4, 15)


def test_predict_next_date_month_end():
    """Jan 31 -> Feb 28 (2026 is not a leap year)."""
    assert predict_next_date(date(2026, 1, 31)) == date(2026, 2, 28)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_subscriptions.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement detection service**

Create `backend/modules/subscriptions/service.py`:

```python
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def predict_next_date(last_date: date) -> date:
    """Project day-of-month to next calendar month, clamping to month end."""
    year = last_date.year
    month = last_date.month + 1
    if month > 12:
        month = 1
        year += 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(last_date.day, max_day)
    return date(year, month, day)


def _are_consecutive(months: list[str]) -> int:
    """Returns length of longest consecutive run from the most recent month backwards."""
    if len(months) < 2:
        return len(months)

    sorted_months = sorted(months, reverse=True)
    run = 1
    for i in range(len(sorted_months) - 1):
        y1, m1 = map(int, sorted_months[i].split("-"))
        y2, m2 = map(int, sorted_months[i + 1].split("-"))
        expected_month = m1 - 1 if m1 > 1 else 12
        expected_year = y1 if m1 > 1 else y1 - 1
        if y2 == expected_year and m2 == expected_month:
            run += 1
        else:
            break
    return run


def _within_tolerance(amounts: list[Decimal], tolerance: float = 0.20) -> bool:
    """Check if all amounts are within tolerance of the median."""
    if len(amounts) < 2:
        return True
    median = sorted(amounts)[len(amounts) // 2]
    if median == 0:
        return False
    return all(abs(float(a - median) / float(median)) <= tolerance for a in amounts)


def detect_from_rows(rows: list[dict]) -> list[dict]:
    """Pure function: given transaction rows, detect recurring patterns."""
    merchants: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        merchants[row["merchant_key"]].append(row)

    results = []
    for merchant_key, txns in merchants.items():
        months = list({t["month"] for t in txns})
        consecutive = _are_consecutive(months)
        if consecutive < 2:
            continue

        amounts = [t["amount"] for t in txns]
        if not _within_tolerance(amounts):
            continue

        sorted_txns = sorted(txns, key=lambda t: t["tx_date"], reverse=True)
        latest = sorted_txns[0]
        previous = sorted_txns[1] if len(sorted_txns) > 1 else None

        avg_amount = sum(amounts) / len(amounts)
        last_amount = latest["amount"]
        previous_amount = previous["amount"] if previous else None

        if previous_amount and previous_amount != 0:
            change_pct = round(float(last_amount - previous_amount) / float(previous_amount) * 100, 1)
            if abs(change_pct) < 1:
                trend = "stable"
            elif change_pct > 0:
                trend = "increased"
            else:
                trend = "decreased"
        else:
            trend = "stable"
            change_pct = None

        results.append({
            "merchant_name": merchant_key,
            "category": latest["category"],
            "average_amount": round(avg_amount, 0),
            "last_amount": last_amount,
            "previous_amount": previous_amount,
            "last_charge_date": latest["tx_date"],
            "predicted_next_date": predict_next_date(latest["tx_date"]),
            "frequency": "monthly",
            "trend": trend,
            "trend_pct": change_pct,
            "months_seen": consecutive,
            "split_type": latest["split_type"],
        })

    results.sort(key=lambda r: r["last_amount"], reverse=True)
    return results


async def get_detected_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> list[dict]:
    """Query transactions and detect recurring patterns."""
    sql = text("""
        SELECT
            COALESCE(m.name, t.raw_merchant_name) AS merchant_key,
            t.category,
            ABS(t.amount) AS amount,
            t.transaction_date AS tx_date,
            TO_CHAR(t.transaction_date, 'YYYY-MM') AS month,
            COALESCE(ts.split_type, 'personal') AS split_type
        FROM transactions t
        LEFT JOIN merchants m ON m.id = t.merchant_id
        LEFT JOIN transaction_splits ts ON ts.transaction_id = t.id
        WHERE t.user_id = :user_id
          AND t.transaction_type = 'expense'
          AND t.transaction_date >= (NOW() - :months_back * INTERVAL '1 month')::DATE
        ORDER BY t.transaction_date DESC
    """)
    result = await db.execute(sql, {"user_id": str(user_id), "months_back": months_back})
    rows = [dict(r._mapping) for r in result.all()]
    return detect_from_rows(rows)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_subscriptions.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/subscriptions/ backend/tests/test_subscriptions.py
git commit -m "feat: add subscription detection service with consecutive-month algorithm"
```

---

### Task 9: Backend — Subscriptions Router & Schema

**Files:**
- Create: `backend/modules/subscriptions/schemas.py`
- Create: `backend/modules/subscriptions/router.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create schema**

Create `backend/modules/subscriptions/schemas.py`:

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class RecurringExpenseResponse(BaseModel):
    merchant_name: str
    category: str | None
    average_amount: Decimal
    last_amount: Decimal
    previous_amount: Decimal | None
    last_charge_date: date
    predicted_next_date: date
    frequency: str
    trend: str
    trend_pct: float | None
    months_seen: int
    split_type: str
```

- [ ] **Step 2: Create router**

Create `backend/modules/subscriptions/router.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from . import service
from .schemas import RecurringExpenseResponse

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/detected", response_model=list[RecurringExpenseResponse])
async def detected_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_detected_subscriptions(db, current_user.id, months_back)
```

- [ ] **Step 3: Register router in main.py**

Add to imports in `backend/main.py`:

```python
from modules.subscriptions.router import router as subscriptions_router
```

Add after the `bank_connect_router` line:

```python
app.include_router(subscriptions_router)
```

Add to `_CACHEABLE_PREFIXES`:

```python
_CACHEABLE_PREFIXES = ("/auth/me", "/transactions/", "/budgets/", "/households/", "/subscriptions/")
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/subscriptions/schemas.py backend/modules/subscriptions/router.py backend/main.py
git commit -m "feat: add subscriptions router with GET /subscriptions/detected endpoint"
```

---

### Task 10: Frontend — Subscriptions API & Hook

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Create: `frontend/app/lib/hooks/useSubscriptions.ts`

- [ ] **Step 1: Add type and API method**

Add to types in `frontend/app/lib/api.ts`:

```typescript
export interface RecurringExpense {
  merchant_name: string;
  category: string | null;
  average_amount: number;
  last_amount: number;
  previous_amount: number | null;
  last_charge_date: string;
  predicted_next_date: string;
  frequency: string;
  trend: "stable" | "increased" | "decreased";
  trend_pct: number | null;
  months_seen: number;
  split_type: string;
}
```

Add to `api` object:

```typescript
getSubscriptions: (monthsBack?: number) =>
  apiFetch<RecurringExpense[]>(`/subscriptions/detected${monthsBack ? `?months_back=${monthsBack}` : ""}`),
```

- [ ] **Step 2: Create hook**

Create `frontend/app/lib/hooks/useSubscriptions.ts`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useSubscriptions() {
  return useQuery({
    queryKey: ["subscriptions", "detected"],
    queryFn: () => api.getSubscriptions(),
    staleTime: 5 * 60 * 1000,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useSubscriptions.ts
git commit -m "feat: add subscriptions API type, method, and hook"
```

---

### Task 11: Frontend — Subscriptions Page

**Files:**
- Create: `frontend/app/(dashboard)/subscriptions/page.tsx`

- [ ] **Step 1: Create the subscriptions page**

Create `frontend/app/(dashboard)/subscriptions/page.tsx` with the approved timeline design:

**Summary section:**
- Two KPI cards side by side: total monthly recurring + % of total spending
- Use `Card` from shadcn/ui

**Timeline section:**
- "Próximos cobros — [next month name]" header
- Vertical timeline with left border, blue/gray dots
- Each entry: date label, merchant name with emoji category, amount
- Sort by `predicted_next_date` ascending
- Blue dots for dates in the first half of month, gray for second half

**Price change alerts:**
- Filter subscriptions where `trend !== "stable"`
- Yellow banner with warning icon: "Netflix subió de $12.000 a $13.500 (+12.5%)"
- Use `AlertTriangle` icon from lucide-react

**Empty state:**
- Center-aligned message: "No hemos detectado gastos recurrentes aún"
- Subtitle: "Necesitamos al menos 2 meses de transacciones"

Use `useSubscriptions()` hook. Use `useMyTransactions()` to calculate total monthly spending for the % KPI.

Format amounts: `amount.toLocaleString("es-CL")` prefixed with `$`.

Format dates: `new Date(date).toLocaleDateString("es-CL", { day: "numeric", month: "short" })`.

Month names in Spanish: use `toLocaleDateString("es-CL", { month: "long", year: "numeric" })`.

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(dashboard)/subscriptions/page.tsx
git commit -m "feat: add subscriptions page with timeline and price change alerts"
```

---

### Task 12: Frontend — Add Suscripciones to Navigation

**Files:**
- Modify: `frontend/app/(dashboard)/components/Sidebar.tsx`
- Modify: `frontend/app/(dashboard)/components/BottomNav.tsx`

- [ ] **Step 1: Update Sidebar.tsx**

Add `Repeat` to the lucide-react import. Insert a new entry in the `NAV` array after the Presupuesto entry:

```typescript
{ href: "/subscriptions", label: "Suscripciones", icon: Repeat },
```

Full NAV should be:
```typescript
const NAV = [
  { href: "/",              label: "Dashboard",      icon: LayoutDashboard },
  { href: "/transactions",  label: "Transacciones",  icon: CreditCard      },
  { href: "/household",     label: "Hogar",           icon: Users           },
  { href: "/budgets",       label: "Presupuesto",     icon: Wallet          },
  { href: "/subscriptions", label: "Suscripciones",   icon: Repeat          },
  { href: "/settings",      label: "Configuración",   icon: Settings        },
];
```

- [ ] **Step 2: Update BottomNav.tsx**

Same change — add `Repeat` import and `Suscripciones` entry to the NAV array in the same position. Note: with 6 items the bottom nav may be tight on small screens. Use abbreviated label `"Suscrip."` in BottomNav if needed, or reduce icon+text size.

- [ ] **Step 3: Verify navigation renders**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/(dashboard)/components/Sidebar.tsx frontend/app/(dashboard)/components/BottomNav.tsx
git commit -m "feat: add Suscripciones to sidebar and bottom nav after Presupuesto"
```

---

## Integration & Verification

### Task 13: End-to-End Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v --ignore=tests/test_whatsapp.py 2>&1 | tail -20
```

Expected: All new tests pass, no regressions.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Clean build with no TypeScript errors.

- [ ] **Step 3: Run backend locally and test endpoints**

```bash
cd backend && uvicorn main:app --reload &
# Test subscription detection
curl -s http://localhost:8000/subscriptions/detected -H "Authorization: Bearer $TOKEN" | python -m json.tool | head -20
# Test settlement
curl -s "http://localhost:8000/households/$HID/settlement" -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Test category breakdown
curl -s "http://localhost:8000/households/$HID/category-breakdown" -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: address integration issues from e2e testing"
```
