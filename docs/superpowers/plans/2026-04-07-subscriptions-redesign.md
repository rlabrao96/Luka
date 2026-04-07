# Subscriptions Page Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the subscriptions page with currency awareness, pre-computed analysis, user overrides, and a modern UI matching the app's blue design system.

**Architecture:** Two new DB tables (`subscription_overrides`, `detected_subscriptions_cache`) replace the Redis cache. The detection runs via ARQ cron (every 10 days) or manual refresh, not on every page load. Overrides are merged at read time so edits don't trigger recomputation. Frontend adds currency toggle, redesigned alerts, generic-month timeline, summary table with expandable rows, and edit modal.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, ARQ, Next.js 14, React Query, Tailwind CSS, shadcn/ui, Lucide icons.

**Spec:** `docs/superpowers/specs/2026-04-07-subscriptions-redesign.md`

---

### Task 1: Alembic Migration — Create New Tables

**Files:**
- Create: `backend/alembic/versions/031_subscription_overrides_and_cache.py`

- [ ] **Step 1: Create the migration file**

```python
"""Add subscription_overrides and detected_subscriptions_cache tables

Revision ID: 031
Revises: 030
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("merchant_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("next_charge_day", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("user_id", "merchant_key", name="uq_subscription_override_user_merchant"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'dismissed')", name="ck_subscription_override_status"),
        sa.CheckConstraint("next_charge_day >= 1 AND next_charge_day <= 31", name="ck_subscription_override_day"),
    )

    op.create_table(
        "detected_subscriptions_cache",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("detected_subscriptions_cache")
    op.drop_table("subscription_overrides")
```

- [ ] **Step 2: Run migration locally**

Run: `cd backend && alembic upgrade head`
Expected: Tables created successfully, no errors.

- [ ] **Step 3: Verify tables exist**

Run: `cd backend && python -c "from sqlalchemy import inspect, create_engine; from core.config import settings; e = create_engine(settings.database_url.replace('+asyncpg', '')); i = inspect(e); print([t for t in i.get_table_names() if 'subscription' in t])"`
Expected: `['detected_subscriptions_cache', 'subscription_overrides']`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/031_subscription_overrides_and_cache.py
git commit -m "feat: add subscription_overrides and detected_subscriptions_cache tables"
```

---

### Task 2: Update Backend Schemas

**Files:**
- Modify: `backend/modules/subscriptions/schemas.py`

- [ ] **Step 1: Update schemas to match spec**

Replace the entire file with:

```python
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class RecentCharge(BaseModel):
    date: date
    amount: Decimal


class RecurringExpenseItem(BaseModel):
    merchant_name: str
    category: str | None
    average_amount: Decimal
    last_amount: Decimal
    previous_amount: Decimal | None
    last_charge_date: date
    next_charge_day: int
    frequency: str
    trend: str
    trend_pct: float | None
    months_seen: int
    split_type: str
    currency: str
    status: str
    recent_charges: list[RecentCharge]


class SubscriptionsSummary(BaseModel):
    total_recurring: Decimal
    monthly_total: Decimal
    pct_of_total: float
    count: int


class SubscriptionsResponse(BaseModel):
    items: list[RecurringExpenseItem]
    summary_by_currency: dict[str, SubscriptionsSummary]
    computed_at: datetime | None


class SubscriptionOverrideRequest(BaseModel):
    merchant_key: str
    status: str | None = None
    category: str | None = None
    next_charge_day: int | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/subscriptions/schemas.py
git commit -m "feat: update subscription schemas with currency, status, overrides"
```

---

### Task 3: Update `detect_from_rows()` — Add Currency and Recent Charges

**Files:**
- Modify: `backend/modules/subscriptions/service.py` (function `detect_from_rows`, lines 61-122)
- Modify: `backend/tests/test_subscriptions.py`

- [ ] **Step 1: Update existing tests to include `currency` field in test data**

Every test row dict in `backend/tests/test_subscriptions.py` needs `"currency": "CLP"` added. Also add new test for currency inclusion and recent_charges:

Append to `backend/tests/test_subscriptions.py`:

```python
def test_detect_from_rows_includes_currency():
    """Each detected subscription includes the currency from the latest transaction."""
    rows = [
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("1350"),
            "tx_date": date(2026, 3, 8),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "USD",
        },
        {
            "merchant_key": "Netflix",
            "category": "Streaming",
            "amount": Decimal("1350"),
            "tx_date": date(2026, 2, 8),
            "month": "2026-02",
            "split_type": "personal",
            "currency": "USD",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    assert result[0]["currency"] == "USD"
    assert result[0]["next_charge_day"] == 8
    assert "predicted_next_date" not in result[0]


def test_detect_from_rows_recent_charges():
    """Recent charges returns last 3 transactions sorted newest first."""
    rows = [
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 4, 1),
            "month": "2026-04",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("12000"),
            "tx_date": date(2026, 3, 1),
            "month": "2026-03",
            "split_type": "personal",
            "currency": "CLP",
        },
        {
            "merchant_key": "Gym",
            "category": "Deporte",
            "amount": Decimal("11500"),
            "tx_date": date(2026, 2, 1),
            "month": "2026-02",
            "split_type": "personal",
            "currency": "CLP",
        },
    ]
    result = detect_from_rows(rows)
    assert len(result) == 1
    charges = result[0]["recent_charges"]
    assert len(charges) == 3
    assert charges[0]["date"] == date(2026, 4, 1)
    assert charges[0]["amount"] == Decimal("12000")
```

Also add `"currency": "CLP"` to every existing test row dict (in `test_detect_from_rows_finds_recurring`, `test_detect_from_rows_skips_non_consecutive`, and both `rows_ok`/`rows_bad` in `test_detect_from_rows_amount_tolerance`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_subscriptions.py -v`
Expected: New tests FAIL (no `currency` key in result), existing tests still PASS.

- [ ] **Step 3: Update `detect_from_rows()` in `backend/modules/subscriptions/service.py`**

Replace the `results.append(...)` block (lines 104-118) with:

```python
        # Build recent charges (last 3 transactions)
        recent_charges = [
            {"date": t["tx_date"], "amount": t["amount"]}
            for t in sorted_txns[:3]
        ]

        results.append(
            {
                "merchant_name": merchant_key,
                "category": latest["category"],
                "average_amount": round(avg_amount, 0),
                "last_amount": last_amount,
                "previous_amount": previous_amount,
                "last_charge_date": latest["tx_date"],
                "next_charge_day": latest["tx_date"].day,
                "frequency": "monthly",
                "trend": trend,
                "trend_pct": change_pct,
                "months_seen": consecutive,
                "split_type": latest["split_type"],
                "currency": latest.get("currency", "CLP"),
                "status": "active",
                "recent_charges": recent_charges,
            }
        )
```

Also remove the `predict_next_date` import and function if nothing else uses it — actually keep it for now, the function is harmless and tested.

- [ ] **Step 4: Run all tests**

Run: `cd backend && python -m pytest tests/test_subscriptions.py -v`
Expected: ALL tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/subscriptions/service.py backend/tests/test_subscriptions.py
git commit -m "feat: add currency, next_charge_day, recent_charges to detect_from_rows"
```

---

### Task 4: Replace Redis Cache with DB Cache + Override Merging

**Files:**
- Modify: `backend/modules/subscriptions/service.py` (functions `get_detected_subscriptions`, `_compute_and_cache`, remove Redis deps)

- [ ] **Step 1: Rewrite the service layer**

Replace everything from `_cache_key` function (line 125) to end of file with:

```python
async def get_detected_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Read from DB cache, compute on first access. Merge overrides at read time."""
    # Check DB cache
    cache_row = await db.execute(
        text("SELECT result_json, computed_at FROM detected_subscriptions_cache WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    row = cache_row.first()

    if row:
        raw_items = row.result_json if isinstance(row.result_json, list) else row.result_json
        computed_at = row.computed_at
    else:
        # First access — compute and store
        raw_items, computed_at = await _compute_and_store(db, user_id, months_back)

    # Merge overrides
    items = await _merge_overrides(db, user_id, raw_items)

    # Filter out dismissed items
    visible_items = [i for i in items if i.get("status") != "dismissed"]

    # Compute summary per currency (only active items)
    summary_by_currency = await _compute_summary_by_currency(db, user_id, visible_items)

    return {
        "items": visible_items,
        "summary_by_currency": summary_by_currency,
        "computed_at": computed_at,
    }


async def refresh_subscriptions(db: AsyncSession, user_id, months_back: int = 6) -> dict:
    """Force recompute and return fresh data."""
    await _compute_and_store(db, user_id, months_back)
    return await get_detected_subscriptions(db, user_id, months_back)


async def upsert_override(db: AsyncSession, user_id, merchant_key: str, status: str | None, category: str | None, next_charge_day: int | None) -> None:
    """Create or update a subscription override."""
    await db.execute(
        text("""
            INSERT INTO subscription_overrides (user_id, merchant_key, status, category, next_charge_day, updated_at)
            VALUES (:uid, :mk, COALESCE(:status, 'active'), :cat, :day, NOW())
            ON CONFLICT (user_id, merchant_key)
            DO UPDATE SET
                status = COALESCE(:status, subscription_overrides.status),
                category = CASE WHEN :cat IS NOT NULL THEN :cat ELSE subscription_overrides.category END,
                next_charge_day = CASE WHEN :day IS NOT NULL THEN :day ELSE subscription_overrides.next_charge_day END,
                updated_at = NOW()
        """),
        {"uid": str(user_id), "mk": merchant_key, "status": status, "cat": category, "day": next_charge_day},
    )
    await db.commit()


async def _compute_and_store(db: AsyncSession, user_id, months_back: int = 6) -> tuple[list[dict], object]:
    """Heavy computation: query transactions, detect patterns, store in DB cache."""
    sql = text("""
        SELECT
            COALESCE(m.normalized_name, t.raw_merchant_name) AS merchant_key,
            t.category,
            ABS(t.amount) AS amount,
            t.transaction_date AS tx_date,
            TO_CHAR(t.transaction_date, 'YYYY-MM') AS month,
            COALESCE(ts.split_type, 'personal') AS split_type,
            t.currency
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
    items = detect_from_rows(rows)

    # Upsert into DB cache (store raw items, before override merging)
    import json
    items_json = json.dumps(items, default=str)
    await db.execute(
        text("""
            INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at)
            VALUES (:uid, :data::jsonb, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET result_json = :data::jsonb, computed_at = NOW()
        """),
        {"uid": str(user_id), "data": items_json},
    )
    await db.commit()

    # Get the computed_at timestamp
    ts_row = await db.execute(
        text("SELECT computed_at FROM detected_subscriptions_cache WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    computed_at = ts_row.scalar()

    return items, computed_at


async def _merge_overrides(db: AsyncSession, user_id, raw_items: list[dict]) -> list[dict]:
    """Apply subscription_overrides on top of raw detected items."""
    result = await db.execute(
        text("SELECT merchant_key, status, category, next_charge_day FROM subscription_overrides WHERE user_id = :uid"),
        {"uid": str(user_id)},
    )
    overrides = {row.merchant_key: row for row in result.all()}

    merged = []
    for item in raw_items:
        item = dict(item)  # copy
        override = overrides.get(item["merchant_name"])
        if override:
            item["status"] = override.status
            if override.category:
                item["category"] = override.category
            if override.next_charge_day:
                item["next_charge_day"] = override.next_charge_day
        merged.append(item)
    return merged


async def _compute_summary_by_currency(db: AsyncSession, user_id, active_items: list[dict]) -> dict:
    """Compute SubscriptionsSummary per currency."""
    from collections import defaultdict
    from decimal import Decimal

    by_currency: dict[str, list[dict]] = defaultdict(list)
    for item in active_items:
        if item.get("status") == "active":
            by_currency[item.get("currency", "CLP")].append(item)

    summary = {}
    for currency, items in by_currency.items():
        total_recurring = sum(Decimal(str(i["last_amount"])) for i in items)

        # Get total monthly expenses for this currency
        monthly_total_sql = text("""
            SELECT COALESCE(SUM(ABS(t.amount)), 0) AS total
            FROM transactions t
            WHERE t.user_id = :user_id
              AND t.transaction_type = 'expense'
              AND t.currency = :currency
              AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
        """)
        monthly_result = await db.execute(monthly_total_sql, {"user_id": str(user_id), "currency": currency})
        monthly_total = monthly_result.scalar() or Decimal("0")

        pct_of_total = round(float(total_recurring) / float(monthly_total) * 100, 1) if monthly_total > 0 else 0

        summary[currency] = {
            "total_recurring": total_recurring,
            "monthly_total": monthly_total,
            "pct_of_total": pct_of_total,
            "count": len(items),
        }

    return summary


async def invalidate_subscriptions_cache(user_id) -> None:
    """Legacy: kept for backward compat. Will clean up old Redis keys."""
    from core.cache import cache_delete
    await cache_delete(f"subscriptions:v2:{user_id}")
```

Also remove the unused imports at the top of the file: remove `from core.cache import cache_get, cache_set, cache_delete` and `CACHE_TTL`.

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_subscriptions.py -v`
Expected: All `detect_from_rows` and `predict_next_date` tests still PASS (service layer changes don't affect the pure function).

- [ ] **Step 3: Commit**

```bash
git add backend/modules/subscriptions/service.py
git commit -m "feat: replace Redis cache with DB cache + override merging"
```

---

### Task 5: Update Router — Add Override and Refresh Endpoints

**Files:**
- Modify: `backend/modules/subscriptions/router.py`

- [ ] **Step 1: Update the router**

Replace the entire file:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from . import service
from .schemas import SubscriptionsResponse, SubscriptionOverrideRequest

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/detected", response_model=SubscriptionsResponse)
async def detected_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_detected_subscriptions(db, current_user.id, months_back)


@router.put("/override")
async def upsert_override(
    body: SubscriptionOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.upsert_override(
        db, current_user.id,
        body.merchant_key, body.status, body.category, body.next_charge_day,
    )
    return {"ok": True}


@router.post("/refresh", response_model=SubscriptionsResponse)
async def refresh_subscriptions(
    months_back: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.refresh_subscriptions(db, current_user.id, months_back)
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/subscriptions/router.py
git commit -m "feat: add PUT /subscriptions/override and POST /subscriptions/refresh endpoints"
```

---

### Task 6: Update ARQ Worker — Periodic Cron + Bank Account Trigger

**Files:**
- Modify: `backend/jobs/tasks.py` (function `refresh_subscriptions_cache`, around line 570)
- Modify: `backend/worker.py` (cron schedule, line 44)
- Modify: `backend/modules/bank_accounts/router.py` (add trigger after bank account creation, line 86)

- [ ] **Step 1: Update `refresh_subscriptions_cache` in `backend/jobs/tasks.py`**

Replace the existing function (lines 570-582) with:

```python
async def refresh_subscriptions_cache(ctx: dict) -> None:
    """Periodic cron: recompute subscription detection for all active users (batched)."""
    from modules.subscriptions.service import _compute_and_store

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT DISTINCT u.id FROM users u
                JOIN bank_accounts ba ON ba.user_id = u.id
                WHERE ba.is_active = true
            """)
        )
        user_ids = [row[0] for row in result.all()]
        logger.info("Refreshing subscriptions cache for %d users", len(user_ids))

        batch_size = 50
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            for uid in batch:
                try:
                    await _compute_and_store(db, uid)
                except Exception:
                    logger.warning("Failed to refresh subscriptions for user %s", uid, exc_info=True)
            if i + batch_size < len(user_ids):
                import asyncio
                await asyncio.sleep(2)


async def refresh_subscriptions_for_user(ctx: dict, user_id: str) -> None:
    """Triggered after new bank account — recompute subscriptions for one user."""
    from modules.subscriptions.service import _compute_and_store

    async with AsyncSessionLocal() as db:
        try:
            await _compute_and_store(db, user_id)
            logger.info("Refreshed subscriptions for user %s after bank link", user_id)
        except Exception:
            logger.warning("Failed to refresh subscriptions for user %s", user_id, exc_info=True)
```

Add the `text` import at the top of `tasks.py` if not already present: `from sqlalchemy import select, text`

- [ ] **Step 2: Update ARQ cron schedule in `backend/worker.py`**

Change the cron line (line 44) from daily to every 10 days. ARQ doesn't support multi-day crons directly, so use `day={1, 11, 21}` to approximate every 10 days:

```python
cron(refresh_subscriptions_cache, day={1, 11, 21}, hour=5, minute=30),  # ~every 10 days
```

Also add `refresh_subscriptions_for_user` to the imports and to the `functions` list:

In imports (line 14), add:
```python
refresh_subscriptions_for_user,
```

Update `FastWorkerSettings.functions` (lines 34-37) to:
```python
    functions = [
        process_email,
        send_invite_email,
        refresh_subscriptions_for_user,
    ]
```

- [ ] **Step 3: Add bank account creation trigger in `backend/modules/bank_accounts/router.py`**

After line 87 (`await db.refresh(bank_account)`) in the `create_bank_account` endpoint, add:

```python
    # Trigger subscription recomputation 30 min after bank link
    from jobs.queue import enqueue_job
    await enqueue_job("refresh_subscriptions_for_user", str(current_user.id), _defer_by=1800)
```

- [ ] **Step 4: Commit**

```bash
git add backend/jobs/tasks.py backend/worker.py backend/modules/bank_accounts/router.py
git commit -m "feat: update ARQ cron to every 10 days + add bank-link trigger"
```

---

### Task 7: Update Frontend API Types and Hooks

**Files:**
- Modify: `frontend/app/lib/api.ts` (lines 237-262, 605-606)
- Modify: `frontend/app/lib/hooks/useSubscriptions.ts`

- [ ] **Step 1: Update types in `frontend/app/lib/api.ts`**

Replace the `RecurringExpense`, `SubscriptionsSummary`, and `SubscriptionsResponse` interfaces (lines 237-262) with:

```typescript
export interface RecentCharge {
  date: string;
  amount: number;
}

export interface RecurringExpense {
  merchant_name: string;
  category: string | null;
  average_amount: number;
  last_amount: number;
  previous_amount: number | null;
  last_charge_date: string;
  next_charge_day: number;
  frequency: string;
  trend: "stable" | "increased" | "decreased";
  trend_pct: number | null;
  months_seen: number;
  split_type: string;
  currency: string;
  status: string;
  recent_charges: RecentCharge[];
}

export interface SubscriptionsSummary {
  total_recurring: number;
  monthly_total: number;
  pct_of_total: number;
  count: number;
}

export interface SubscriptionsResponse {
  items: RecurringExpense[];
  summary_by_currency: Record<string, SubscriptionsSummary>;
  computed_at: string | null;
}

export interface SubscriptionOverrideBody {
  merchant_key: string;
  status?: string | null;
  category?: string | null;
  next_charge_day?: number | null;
}
```

Add two new API functions near the existing `getSubscriptions` (around line 605):

```typescript
  refreshSubscriptions: () =>
    apiFetch<SubscriptionsResponse>("/subscriptions/refresh", { method: "POST" }),

  upsertSubscriptionOverride: (body: SubscriptionOverrideBody) =>
    apiFetch<{ ok: boolean }>("/subscriptions/override", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
```

- [ ] **Step 2: Update hooks in `frontend/app/lib/hooks/useSubscriptions.ts`**

Replace the entire file:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SubscriptionOverrideBody } from "@/app/lib/api";

export function useSubscriptions() {
  const { data, isLoading } = useQuery({
    queryKey: ["subscriptions", "detected"],
    queryFn: () => api.getSubscriptions(),
    staleTime: 5 * 60_000,
  });
  return { data, isLoading };
}

export function useRefreshSubscriptions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.refreshSubscriptions(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}

export function useSubscriptionOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SubscriptionOverrideBody) => api.upsertSubscriptionOverride(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useSubscriptions.ts
git commit -m "feat: update subscription types, add override and refresh hooks"
```

---

### Task 8: Rewrite Subscriptions Page — Full Frontend Redesign

**Files:**
- Modify: `frontend/app/(dashboard)/subscriptions/page.tsx`

This is the largest task. The entire page component is rewritten.

- [ ] **Step 1: Rewrite the subscriptions page**

Replace the entire file `frontend/app/(dashboard)/subscriptions/page.tsx` with:

```tsx
"use client";

import { useState, useMemo, useEffect } from "react";
import { RefreshCw, ArrowUp, ArrowDown, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { CurrencyToggle } from "../components/CurrencyToggle";
import {
  useSubscriptions,
  useRefreshSubscriptions,
  useSubscriptionOverride,
} from "@/app/lib/hooks/useSubscriptions";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import type { RecurringExpense } from "@/app/lib/api";

/* ── Formatting ─────────────────────────────────────────── */

function formatAmount(n: number, currency: string) {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? n / 100 : n;
  if (currency === "USD")
    return `US$${Math.abs(displayVal).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  return `$${Math.round(Math.abs(displayVal)).toLocaleString("es-CL")}`;
}

function relativeTime(iso: string | null) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 1) return "hace menos de 1 hora";
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} día${days > 1 ? "s" : ""}`;
}

/* ── Main Page ──────────────────────────────────────────── */

export default function SubscriptionsPage() {
  const { data, isLoading } = useSubscriptions();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const refreshMutation = useRefreshSubscriptions();
  const overrideMutation = useSubscriptionOverride();

  const [currency, setCurrency] = useState("CLP");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<RecurringExpense | null>(null);

  // Sync currency from user preference
  const preferredCurrency = me?.preferred_currency;
  useEffect(() => {
    if (preferredCurrency) setCurrency(preferredCurrency);
  }, [preferredCurrency]);

  const allItems = data?.items ?? [];
  const summaryByCurrency = data?.summary_by_currency ?? {};
  const computedAt = data?.computed_at ?? null;

  // Filter by currency
  const items = useMemo(
    () => allItems.filter((s) => s.currency === currency),
    [allItems, currency],
  );

  const activeItems = useMemo(
    () => items.filter((s) => s.status === "active"),
    [items],
  );

  const summary = summaryByCurrency[currency];
  const alerts = activeItems.filter((s) => s.trend !== "stable");

  // Timeline sorted by next_charge_day
  const timelineSorted = useMemo(
    () => [...activeItems].sort((a, b) => a.next_charge_day - b.next_charge_day),
    [activeItems],
  );

  const today = new Date().getDate();

  if (isLoading) {
    return <p className="text-gray-400">Cargando...</p>;
  }

  if (allItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-lg font-semibold text-gray-700">
          No hemos detectado gastos recurrentes aún
        </p>
        <p className="text-sm text-gray-400 mt-2 max-w-xs">
          Necesitamos al menos 2 meses de transacciones para identificar patrones
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
            Suscripciones
          </h2>
          <p className="text-sm text-gray-400 mt-0.5">
            Gastos recurrentes detectados automáticamente
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            className="p-2 rounded-lg text-slate-400 hover:text-luka-primary hover:bg-blue-50 transition-colors disabled:opacity-50"
            title={`Última actualización: ${relativeTime(computedAt)}`}
          >
            <RefreshCw
              size={16}
              className={refreshMutation.isPending ? "animate-spin" : ""}
            />
          </button>
          <CurrencyToggle value={currency} onChange={setCurrency} />
        </div>
      </div>

      {/* Currency-specific empty state */}
      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-sm text-gray-400">
            No tienes suscripciones en {currency}
          </p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardContent className="p-4">
                <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                  Total mensual recurrente
                </p>
                <p className="text-[22px] font-bold text-gray-900 mt-1 tabular-nums">
                  {formatAmount(summary?.total_recurring ?? 0, currency)}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {summary?.count ?? 0} suscripciones activas
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                  % de gastos totales
                </p>
                <p className="text-[22px] font-bold text-blue-600 mt-1 tabular-nums">
                  {Math.round(summary?.pct_of_total ?? 0)}%
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  de {formatAmount(summary?.monthly_total ?? 0, currency)} este mes
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Price Change Alerts */}
          {alerts.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Cambios de precio
              </p>
              <div className="space-y-2">
                {alerts.map((sub) => {
                  const isUp = sub.trend === "increased";
                  const prev = sub.previous_amount ?? sub.average_amount;
                  return (
                    <div
                      key={`alert-${sub.merchant_name}`}
                      className={`flex items-center gap-3 bg-white rounded-lg border border-slate-200 p-3 ${
                        isUp ? "border-l-[3px] border-l-red-500" : "border-l-[3px] border-l-emerald-500"
                      }`}
                    >
                      <div
                        className={`flex items-center justify-center w-7 h-7 rounded-md shrink-0 ${
                          isUp ? "bg-red-50" : "bg-emerald-50"
                        }`}
                      >
                        {isUp ? (
                          <ArrowUp size={14} className="text-red-500" />
                        ) : (
                          <ArrowDown size={14} className="text-emerald-500" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-gray-900">
                          {sub.merchant_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatAmount(prev, currency)} → {formatAmount(sub.last_amount, currency)}
                        </p>
                      </div>
                      <span
                        className={`text-xs font-semibold whitespace-nowrap ${
                          isUp ? "text-red-500" : "text-emerald-500"
                        }`}
                      >
                        {isUp ? "+" : "-"}
                        {Math.abs(Math.round(sub.trend_pct ?? 0))}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Generic Month Timeline */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-4">
              Calendario de cobros
            </p>
            <div className="relative border-l-2 border-blue-100 ml-3 pl-6 space-y-4">
              {timelineSorted.map((sub, idx) => {
                const isBeforeToday = sub.next_charge_day <= today;
                const nextIsAfterToday =
                  idx < timelineSorted.length - 1 &&
                  timelineSorted[idx + 1].next_charge_day > today;
                const isLastBeforeToday =
                  isBeforeToday &&
                  (nextIsAfterToday || idx === timelineSorted.length - 1);

                return (
                  <div key={sub.merchant_name}>
                    <div className="relative">
                      <div
                        className={`absolute -left-[31px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white ${
                          isBeforeToday ? "bg-blue-600" : "bg-blue-400"
                        }`}
                      />
                      <p
                        className={`text-[11px] font-bold uppercase ${
                          isBeforeToday ? "text-blue-600" : "text-blue-400"
                        }`}
                      >
                        Día {sub.next_charge_day}
                      </p>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-sm text-gray-700">
                          {sub.merchant_name}
                        </span>
                        <span className="text-sm font-bold text-gray-900 tabular-nums">
                          {formatAmount(sub.last_amount, currency)}
                        </span>
                      </div>
                    </div>

                    {/* Today marker — after last item before today */}
                    {isLastBeforeToday && (
                      <div className="relative mt-4 mb-2">
                        <div className="absolute -left-[36px] flex items-center gap-0 right-0">
                          <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center">
                            <span className="text-[8px] font-extrabold text-white">
                              {today}
                            </span>
                          </div>
                          <div className="flex-1 h-0.5 bg-gradient-to-r from-blue-600 to-transparent" />
                        </div>
                        <p className="pl-1 pt-0.5 text-[10px] font-bold text-blue-600 uppercase tracking-wide">
                          ← Hoy
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Summary Table */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
              Detalle de suscripciones
            </p>
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              {/* Table header */}
              <div className="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr_60px] gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">
                  Servicio
                </span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">
                  Monto
                </span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">
                  Último cobro
                </span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">
                  Categoría
                </span>
                <span />
              </div>

              {/* Rows */}
              {items
                .filter((s) => s.status !== "dismissed")
                .map((sub) => {
                  const isExpanded = expandedRow === sub.merchant_name;
                  const isInactive = sub.status === "inactive";

                  return (
                    <div
                      key={sub.merchant_name}
                      className={`border-b border-slate-100 last:border-b-0 ${
                        isInactive ? "opacity-55" : ""
                      }`}
                    >
                      {/* Main row */}
                      <div
                        className="grid grid-cols-[2fr_1fr_1fr_1fr_60px] gap-2 px-4 py-3 items-center cursor-pointer hover:bg-slate-50 transition-colors"
                        onClick={() =>
                          setExpandedRow(isExpanded ? null : sub.merchant_name)
                        }
                      >
                        <div className="flex items-center gap-1.5">
                          <div>
                            <div className="flex items-center gap-1.5">
                              <p className="text-[13px] font-semibold text-gray-900">
                                {sub.merchant_name}
                              </p>
                              {isInactive && (
                                <span className="text-[9px] font-semibold text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded uppercase">
                                  Inactiva
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400">
                              {sub.months_seen} meses · {sub.frequency}
                            </p>
                          </div>
                          {isExpanded ? (
                            <ChevronUp size={14} className="text-slate-300 ml-auto" />
                          ) : (
                            <ChevronDown size={14} className="text-slate-300 ml-auto" />
                          )}
                        </div>
                        <span className="text-[13px] font-semibold text-gray-900 tabular-nums">
                          {formatAmount(sub.last_amount, currency)}
                        </span>
                        <span className="text-xs text-slate-500">
                          {new Date(sub.last_charge_date + "T00:00:00").toLocaleDateString(
                            "es-CL",
                            { day: "numeric", month: "short", year: "numeric" },
                          )}
                        </span>
                        <span className="text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded text-center truncate">
                          {sub.category ?? "—"}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingItem(sub);
                          }}
                          className="text-[11px] text-blue-600 font-medium hover:underline"
                        >
                          Editar
                        </button>
                      </div>

                      {/* Expanded recent charges */}
                      {isExpanded && sub.recent_charges.length > 0 && (
                        <div className="px-4 pb-3 ml-2 border-l-2 border-blue-100">
                          {sub.recent_charges.map((charge, i) => (
                            <div
                              key={i}
                              className="flex justify-between py-1 pl-3"
                            >
                              <span className="text-[11px] text-slate-400">
                                {new Date(charge.date + "T00:00:00").toLocaleDateString(
                                  "es-CL",
                                  { day: "numeric", month: "short", year: "numeric" },
                                )}
                              </span>
                              <span className="text-[11px] font-medium text-gray-700 tabular-nums">
                                {formatAmount(charge.amount, currency)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        </>
      )}

      {/* Edit Modal */}
      {editingItem && (
        <EditModal
          item={editingItem}
          currency={currency}
          onClose={() => setEditingItem(null)}
          onSave={(body) => {
            overrideMutation.mutate(body, {
              onSuccess: () => setEditingItem(null),
            });
          }}
        />
      )}
    </div>
  );
}

/* ── Edit Modal ─────────────────────────────────────────── */

function EditModal({
  item,
  currency,
  onClose,
  onSave,
}: {
  item: RecurringExpense;
  currency: string;
  onClose: () => void;
  onSave: (body: { merchant_key: string; status?: string; category?: string; next_charge_day?: number | null }) => void;
}) {
  const [status, setStatus] = useState(item.status);
  const [category, setCategory] = useState(item.category ?? "");
  const [chargeDay, setChargeDay] = useState<string>(
    item.next_charge_day ? String(item.next_charge_day) : "",
  );

  const { data: categories } = useQuery({
    queryKey: ["categories", "preferences"],
    queryFn: () => api.getCategoryPreferences(),
  });

  const categoryList: string[] = useMemo(() => {
    if (!categories) return [];
    return [
      ...new Set([
        ...(categories.visible_expense ?? []),
        ...(categories.visible_income ?? []),
      ]),
    ].sort();
  }, [categories]);

  const statusOptions = [
    { value: "active", label: "Activa" },
    { value: "inactive", label: "Inactiva" },
    { value: "dismissed", label: "No es suscripción" },
  ] as const;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
      <div className="bg-white rounded-xl border border-slate-200 p-5 w-full max-w-sm shadow-xl">
        <p className="text-[15px] font-bold text-gray-900 mb-4">
          Editar — {item.merchant_name}
        </p>

        {/* Category */}
        <div className="mb-3">
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Categoría
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-[13px] text-gray-700 bg-white"
          >
            <option value="">— Sin cambio —</option>
            {categoryList.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div className="mb-3">
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Estado
          </label>
          <div className="flex gap-1.5">
            {statusOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatus(opt.value)}
                className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  status === opt.value
                    ? "bg-luka-primary text-white"
                    : "bg-slate-100 text-slate-500 border border-slate-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Next Charge Day */}
        <div className="mb-4">
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Día del mes (opcional)
          </label>
          <input
            type="number"
            min={1}
            max={31}
            value={chargeDay}
            onChange={(e) => setChargeDay(e.target.value)}
            placeholder={String(item.next_charge_day)}
            className="w-full border border-slate-200 rounded-lg px-3 py-2 text-[13px] text-gray-700"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={() =>
              onSave({
                merchant_key: item.merchant_name,
                status,
                category: category || undefined,
                next_charge_day: chargeDay ? Number(chargeDay) : null,
              })
            }
            className="flex-1 px-4 py-2 rounded-lg bg-luka-primary text-white text-[13px] font-semibold hover:bg-blue-700 transition-colors"
          >
            Guardar
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-50 text-slate-500 border border-slate-200 text-[13px] font-medium hover:bg-slate-100 transition-colors"
          >
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors. If `getCategoryPreferences` doesn't exist in `api.ts`, check for the actual function name — it may be `getCategoryPrefs` or similar. Grep for it:
`grep -n "categor" frontend/app/lib/api.ts | head -10`

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/subscriptions/page.tsx
git commit -m "feat: redesign subscriptions page — currency toggle, timeline, table, edit modal"
```

---

### Task 9: Manual Testing Checklist

No code changes — just verification steps.

- [ ] **Step 1: Run backend locally**

Run: `cd backend && uvicorn main:app --reload --port 8000`

- [ ] **Step 2: Run frontend locally**

Run: `cd frontend && npm run dev`

- [ ] **Step 3: Test the page**

Open the subscriptions page in the browser. Verify:
1. Currency toggle shows and filters subscriptions
2. CLP amounts format as `$388.880` (no decimals)
3. USD amounts format as `US$5.00` (2 decimals, divided by 100)
4. Alert cards use white background with colored left borders (no yellow)
5. Timeline shows "Día N" labels with "Hoy" marker at today's date
6. Summary table shows all subscriptions with expand/collapse
7. Clicking "Editar" opens the modal with category, status, and day-of-month
8. Saving an override works (changes reflected after refetch)
9. Marking as "Inactiva" dims the row and removes from timeline
10. Marking as "No es suscripción" hides the row completely
11. Refresh button triggers recomputation with spinner
12. Empty state shows when toggling to a currency with no subscriptions

- [ ] **Step 4: Push all changes**

```bash
git push origin main
```

---

### Summary of Files Changed

| File | Action |
|------|--------|
| `backend/alembic/versions/031_subscription_overrides_and_cache.py` | Create |
| `backend/modules/subscriptions/schemas.py` | Modify |
| `backend/modules/subscriptions/service.py` | Modify |
| `backend/modules/subscriptions/router.py` | Modify |
| `backend/jobs/tasks.py` | Modify |
| `backend/worker.py` | Modify |
| `backend/modules/bank_accounts/router.py` | Modify |
| `backend/tests/test_subscriptions.py` | Modify |
| `frontend/app/lib/api.ts` | Modify |
| `frontend/app/lib/hooks/useSubscriptions.ts` | Modify |
| `frontend/app/(dashboard)/subscriptions/page.tsx` | Modify |
