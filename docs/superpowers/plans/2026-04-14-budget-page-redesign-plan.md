# Budget Page Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `/budgets` into a prevent-overspend + clarity-first page with a Sankey flow, contribution-mode privacy for couples, cuotas, savings target, risk alerts, and runway card — shipping in 1 week via parallel subagents.

**Architecture:** Additive. A new `GET /budgets/v2/{household_id}` endpoint + new page implementation live alongside the existing `/budgets/personal` endpoint. Existing page stays until Day 7 cutover. New tables `user_budget_settings` and `cuota_purchases`; new columns on `household_members`. Math engine v1 is heuristic (3-month mean/std, linear pace, `P > 0.70` alerts) with the same function signatures the Phase 2 Bayesian engine will swap into.

**Tech Stack:** FastAPI 0.111 + SQLAlchemy 2.0 async + Alembic; Next.js 16 + React 19 + Tailwind 4 + Recharts 3.8 (Sankey primitive, first use); TanStack Query 5; Redis for risk-category caching; `chrome-devtools-mcp` + `browser-use` skills for agent verification.

**Spec (source of truth for all architectural decisions):**
`docs/superpowers/specs/2026-04-14-budget-page-redesign-design.md`

**Referenced skills:**
- `@superpowers:test-driven-development` — red → green → refactor for every task with a testable output
- `@superpowers:systematic-debugging` — when a test unexpectedly fails or behavior surprises you
- `@superpowers:subagent-driven-development` — for parallel execution of Tasks A–H
- `@chrome-devtools-mcp` + `browser-use` — for the verification checkpoints in Tasks A, B, D, E, F, G, H, J

---

## Pre-Flight Checks (before any task)

- [ ] **P1. Confirm spec is merged to main and the `main` branch is clean**
  ```bash
  cd "/Users/rlabrao/Documents/Proyectos AI/Finanzas Personales"
  git status
  git log -2 --oneline
  ```
  Expected: working tree clean (ignoring known `.superpowers` untracked + `test-scraper/open-banking-chile-fork` modification); `ff4ec56 docs(spec): add agent-driven verification...` is visible.

- [ ] **P2. Confirm Python env + backend boots**
  ```bash
  cd backend && source .venv/bin/activate
  python -c "import sqlalchemy, alembic, fastapi, arq; print('ok')"
  ```
  Expected: `ok`. If venv missing, `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.

- [ ] **P3. Confirm frontend env**
  ```bash
  cd frontend && node -v && cat package.json | grep '"recharts"'
  ```
  Expected: Node ≥18 and `"recharts": "^3.8.0"`.

- [ ] **P4. Confirm Alembic is at head**
  ```bash
  cd backend && alembic current
  ```
  Expected: `034 (head)`.

- [ ] **P5. Confirm `backend/tests/conftest.py` exposes an async `db` fixture**
  ```bash
  grep -n "def db" backend/tests/conftest.py
  ```
  Expected: an async fixture using a SAVEPOINT rollback (around lines 17–33). If the fixture is not present under the name `db`, **stop** and align on the actual harness name before proceeding — Task 0.5 and every backend test in this plan depend on it.

- [ ] **P6. Worktree strategy**
  Task 0 runs on `main` (or a dedicated `budget-v2-task-0` branch) because its output is the blocker for everyone. **Each of Tasks A–H runs in its own worktree** (`git worktree add ../luka-budget-chunk-<letter> main` after Task 0 merges), so parallel subagents don't clobber each other on the three shared files noted in "Global notes" below. `superpowers:subagent-driven-development` automates this.

---

## Task 0 — Migrations, Seed Fixtures, Verification Orchestrator (blocker)

**⚠️ This task blocks every other task. It must land on `main` before A–H start.**

**Files:**
- Create: `backend/alembic/versions/035_budget_redesign_schema.py`
- Create: `backend/modules/budgets/savings_categories.py`
- Create: `backend/scripts/seed_budget_test_fixtures.py`
- Create: `backend/scripts/run_chunk_verifications.sh`
- Modify: `backend/modules/households/models.py` (add `contribution_mode`, `fixed_contribution_amount`, `fixed_contribution_currency` to `HouseholdMember`)
- Create: `backend/modules/budgets/user_budget_settings_models.py` (new `UserBudgetSettings` model — kept inside the budgets module because the table is exclusively owned by budget code)
- Create: `backend/modules/budgets/cuota_models.py` (new `CuotaPurchase` SQLAlchemy model)
- Test: `backend/tests/test_budget_migration_035.py`

**Style requirement:** all new SQLAlchemy models MUST use SQLAlchemy 2.0 `Mapped[...] = mapped_column(...)` style to match the rest of the codebase (see `backend/modules/households/models.py:13-31` for the canonical pattern). Do not paste `Column(...)` definitions — they are inconsistent and will drift from the house style.

### Steps

- [ ] **0.1 — Draft the Alembic migration file**

  Create `backend/alembic/versions/035_budget_redesign_schema.py` following the format of `034_household_members_active_unique.py`. The migration must:

  1. Add columns to `household_members`:
     - `contribution_mode VARCHAR(16) NOT NULL DEFAULT 'full' CHECK (contribution_mode IN ('full','fixed','reimbursement'))`
     - `fixed_contribution_amount NUMERIC(14,2)` nullable
     - `fixed_contribution_currency CHAR(3)` nullable
     - Backfill existing rows: all existing members get `contribution_mode='full'` (covered by the DEFAULT on add)
  2. Create `user_budget_settings` table with columns exactly per spec §5.2:
     - `user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE`
     - `savings_target_amount NUMERIC(14,2)` nullable
     - `savings_target_currency CHAR(3)` nullable
     - `payday_day_of_month INT` nullable with `CHECK (payday_day_of_month BETWEEN 1 AND 31)`
     - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
     - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
  3. Create `cuota_purchases` table with columns exactly per spec §5.3 (see spec for full column list)
     - Indexes: `(user_id, status)`, `(household_id, status)`, `(last_cuota_date)`
  4. **No changes** to `household_budget_allocations` or `categories` (we use a hardcoded savings-category set in code — decided per spec §5.4 Open Question #2 based on exploration finding that Transaction.category is free text).

  Use this skeleton:
  ```python
  """Budget redesign — contribution modes, user_budget_settings, cuota_purchases

  Revision ID: 035
  Revises: 034
  Create Date: 2026-04-14
  """
  from alembic import op
  import sqlalchemy as sa
  from sqlalchemy.dialects import postgresql

  revision = "035"
  down_revision = "034"
  branch_labels = None
  depends_on = None


  def upgrade() -> None:
      # household_members
      op.add_column(
          "household_members",
          sa.Column(
              "contribution_mode",
              sa.String(16),
              nullable=False,
              server_default="full",
          ),
      )
      op.create_check_constraint(
          "ck_household_members_contribution_mode",
          "household_members",
          "contribution_mode IN ('full','fixed','reimbursement')",
      )
      op.add_column("household_members", sa.Column("fixed_contribution_amount", sa.Numeric(14, 2), nullable=True))
      op.add_column("household_members", sa.Column("fixed_contribution_currency", sa.String(3), nullable=True))

      # user_budget_settings
      op.create_table(
          "user_budget_settings",
          sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
          sa.Column("savings_target_amount", sa.Numeric(14, 2), nullable=True),
          sa.Column("savings_target_currency", sa.String(3), nullable=True),
          sa.Column("payday_day_of_month", sa.Integer(), nullable=True),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.CheckConstraint("payday_day_of_month BETWEEN 1 AND 31", name="ck_user_budget_settings_payday"),
      )

      # cuota_purchases
      op.create_table(
          "cuota_purchases",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
          sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
          sa.Column("origin_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True),
          sa.Column("merchant_name", sa.Text, nullable=False),
          sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
          sa.Column("currency", sa.String(3), nullable=False),
          sa.Column("installments_total", sa.Integer, nullable=False),
          sa.Column("installments_paid", sa.Integer, nullable=False, server_default="0"),
          sa.Column("monthly_amount", sa.Numeric(14, 2), nullable=False),
          sa.Column("first_cuota_date", sa.Date, nullable=False),
          sa.Column("last_cuota_date", sa.Date, nullable=False),
          sa.Column("status", sa.String(16), nullable=False, server_default="active"),
          sa.Column("split_type", sa.String(16), nullable=False, server_default="personal"),
          sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.CheckConstraint("installments_total > 0", name="ck_cuota_installments_total_positive"),
          sa.CheckConstraint("installments_paid >= 0 AND installments_paid <= installments_total", name="ck_cuota_installments_paid_range"),
          sa.CheckConstraint("status IN ('active','completed','cancelled')", name="ck_cuota_status"),
          sa.CheckConstraint("split_type IN ('personal','shared')", name="ck_cuota_split_type"),
      )
      op.create_index("ix_cuota_purchases_user_status", "cuota_purchases", ["user_id", "status"])
      op.create_index("ix_cuota_purchases_household_status", "cuota_purchases", ["household_id", "status"])
      op.create_index("ix_cuota_purchases_last_cuota_date", "cuota_purchases", ["last_cuota_date"])


  def downgrade() -> None:
      op.drop_index("ix_cuota_purchases_last_cuota_date", table_name="cuota_purchases")
      op.drop_index("ix_cuota_purchases_household_status", table_name="cuota_purchases")
      op.drop_index("ix_cuota_purchases_user_status", table_name="cuota_purchases")
      op.drop_table("cuota_purchases")
      op.drop_table("user_budget_settings")
      op.drop_constraint("ck_household_members_contribution_mode", "household_members", type_="check")
      op.drop_column("household_members", "fixed_contribution_currency")
      op.drop_column("household_members", "fixed_contribution_amount")
      op.drop_column("household_members", "contribution_mode")
  ```

- [ ] **0.2 — Run the migration up and down to verify clean rollback**

  ```bash
  cd backend && alembic upgrade head && alembic current
  ```
  Expected: `035 (head)`.

  ```bash
  alembic downgrade -1 && alembic current
  ```
  Expected: `034 (head)`.

  ```bash
  alembic upgrade head && alembic current
  ```
  Expected: `035 (head)` again. **Do not proceed if any step errors.**

- [ ] **0.3 — Write the SQLAlchemy model files (2.0 `Mapped[...]` style)**

  Create `backend/modules/budgets/user_budget_settings_models.py`:
  ```python
  import uuid
  from datetime import datetime
  from decimal import Decimal
  from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
  from sqlalchemy.dialects.postgresql import UUID
  from sqlalchemy.orm import Mapped, mapped_column
  from core.database import Base


  class UserBudgetSettings(Base):
      __tablename__ = "user_budget_settings"

      user_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
      )
      savings_target_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
      savings_target_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
      payday_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )

      __table_args__ = (
          CheckConstraint(
              "payday_day_of_month BETWEEN 1 AND 31",
              name="ck_user_budget_settings_payday",
          ),
      )
  ```

  Create `backend/modules/budgets/cuota_models.py`:
  ```python
  import uuid
  from datetime import date, datetime
  from decimal import Decimal
  from sqlalchemy import (
      CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func,
  )
  from sqlalchemy.dialects.postgresql import UUID
  from sqlalchemy.orm import Mapped, mapped_column
  from core.database import Base


  class CuotaPurchase(Base):
      __tablename__ = "cuota_purchases"

      id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      user_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
      )
      household_id: Mapped[uuid.UUID] = mapped_column(
          UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
      )
      origin_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
          UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
      )
      merchant_name: Mapped[str] = mapped_column(Text, nullable=False)
      total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
      currency: Mapped[str] = mapped_column(String(3), nullable=False)
      installments_total: Mapped[int] = mapped_column(Integer, nullable=False)
      installments_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
      monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
      first_cuota_date: Mapped[date] = mapped_column(Date, nullable=False)
      last_cuota_date: Mapped[date] = mapped_column(Date, nullable=False)
      status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
      split_type: Mapped[str] = mapped_column(String(16), nullable=False, default="personal")
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )

      __table_args__ = (
          CheckConstraint("installments_total > 0", name="ck_cuota_installments_total_positive"),
          CheckConstraint(
              "installments_paid >= 0 AND installments_paid <= installments_total",
              name="ck_cuota_installments_paid_range",
          ),
          CheckConstraint(
              "status IN ('active','completed','cancelled')", name="ck_cuota_status"
          ),
          CheckConstraint(
              "split_type IN ('personal','shared')", name="ck_cuota_split_type"
          ),
          Index("ix_cuota_purchases_user_status", "user_id", "status"),
          Index("ix_cuota_purchases_household_status", "household_id", "status"),
          Index("ix_cuota_purchases_last_cuota_date", "last_cuota_date"),
      )
  ```

  Modify `backend/modules/households/models.py` — find `class HouseholdMember(Base):` (line 23) and add **inside the class body** after `left_at`, matching the existing `Mapped[...]` style used throughout the file:
  ```python
      contribution_mode: Mapped[str] = mapped_column(
          String(16), nullable=False, server_default="full"
      )
      fixed_contribution_amount: Mapped[Decimal | None] = mapped_column(
          Numeric(14, 2), nullable=True
      )
      fixed_contribution_currency: Mapped[str | None] = mapped_column(
          String(3), nullable=True
      )
  ```
  `Numeric` is already imported at line 4. Add `from decimal import Decimal` at the top of the file if not already present.

- [ ] **0.4 — Create the savings-category set**

  Create `backend/modules/budgets/savings_categories.py`:
  ```python
  """Single source of truth for which transaction categories are 'savings-equivalent'.

  Transactions in these categories are excluded from `spendable.spent`
  and counted toward `savings_target.progress`. See spec §5.4.

  Normalization: `is_savings_category` strips, lowercases, and removes
  common accents so new contributors can add `"Inversión"`, `"APV"`,
  `"Ahorro"` in any natural casing without introducing near-duplicates.
  """

  SAVINGS_EQUIVALENT_CATEGORIES: frozenset[str] = frozenset({
      "inversion",
      "ahorro",
      "apv",
  })


  def _normalize(value: str) -> str:
      return (
          value.strip()
          .lower()
          .replace("á", "a")
          .replace("é", "e")
          .replace("í", "i")
          .replace("ó", "o")
          .replace("ú", "u")
      )


  def is_savings_category(category: str | None) -> bool:
      if not category:
          return False
      return _normalize(category) in SAVINGS_EQUIVALENT_CATEGORIES
  ```

- [ ] **0.5 — Write a migration smoke test**

  Create `backend/tests/test_budget_migration_035.py`:
  ```python
  import pytest
  from sqlalchemy import text


  @pytest.mark.asyncio
  async def test_035_adds_expected_columns(db):
      result = await db.execute(text("""
          SELECT column_name FROM information_schema.columns
          WHERE table_name = 'household_members'
            AND column_name IN ('contribution_mode', 'fixed_contribution_amount', 'fixed_contribution_currency')
      """))
      cols = {row[0] for row in result}
      assert cols == {"contribution_mode", "fixed_contribution_amount", "fixed_contribution_currency"}


  @pytest.mark.asyncio
  async def test_035_creates_user_budget_settings(db):
      result = await db.execute(text("SELECT to_regclass('public.user_budget_settings')"))
      assert result.scalar() == "user_budget_settings"


  @pytest.mark.asyncio
  async def test_035_creates_cuota_purchases(db):
      result = await db.execute(text("SELECT to_regclass('public.cuota_purchases')"))
      assert result.scalar() == "cuota_purchases"


  @pytest.mark.asyncio
  async def test_035_contribution_mode_default_is_full(db):
      result = await db.execute(text("""
          SELECT column_default FROM information_schema.columns
          WHERE table_name = 'household_members' AND column_name = 'contribution_mode'
      """))
      default = result.scalar() or ""
      assert "full" in default
  ```

  Run: `cd backend && pytest tests/test_budget_migration_035.py -v`
  Expected: 4 passed.

- [ ] **0.6 — Write the seed fixture script**

  Create `backend/scripts/seed_budget_test_fixtures.py`. It should be idempotent (re-runnable) and create:
  - User `rafa-full@luka.test` with a partner, contribution_mode=`full`/`full`, household "HOGAR FULL"
  - User `rafa-fixed@luka.test` with `fixed` partner, real incomes $1,800,000 vs $2,100,000, partner's `fixed_contribution_amount=$800,000 CLP`, household "HOGAR FIXED"
  - User `rafa-reimb@luka.test` with `reimbursement` partner, household "HOGAR REIMB"
  - User `rafa-solo@luka.test` individual household, "HOGAR SOLO"
  - For each household: 3 months of seed transactions across categories (Restaurantes, Supermercado, Transporte, Vivienda, Servicios, Streaming, Inversión) in CLP; the HOGAR FIXED user also gets 1 month of USD transactions so mixed-currency verification has real data
  - One active `cuota_purchase` for HOGAR FULL: 12 installments, $50k/mo, `first_cuota_date` = today − 2 months

  Keep the script under ~200 lines. Use the existing `create_household`, `Transaction`, `BankAccount` helpers. Run it at the end of the script:
  ```python
  if __name__ == "__main__":
      import asyncio
      asyncio.run(seed_all())
      print("✅ Seeded budget test fixtures")
  ```

  Run: `python backend/scripts/seed_budget_test_fixtures.py`
  Expected: `✅ Seeded budget test fixtures` (idempotent — safe to re-run).

- [ ] **0.7 — Write the verification orchestrator script**

  Create `backend/scripts/run_chunk_verifications.sh`:
  ```bash
  #!/usr/bin/env bash
  # Usage: ./run_chunk_verifications.sh <chunk-letter>
  #   A|B|C|D|E|F|G|H  - run that chunk's §11.4 checkpoint
  #   day4              - integration verification
  #   day6              - UX consistency pass
  set -euo pipefail

  CHUNK="${1:-}"
  if [ -z "$CHUNK" ]; then
    echo "Usage: $0 <A|B|C|D|E|F|G|H|day4|day6>"
    exit 1
  fi

  ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
  cd "$ROOT_DIR"

  echo "→ Seeding budget test fixtures..."
  python backend/scripts/seed_budget_test_fixtures.py

  echo "→ Starting dev backend on :8000 (background)..."
  (cd backend && uvicorn main:app --port 8000 > /tmp/luka-verify-backend.log 2>&1) &
  BACKEND_PID=$!
  trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

  echo "→ Starting dev frontend on :3000 (background)..."
  (cd frontend && npm run dev > /tmp/luka-verify-frontend.log 2>&1) &
  FRONTEND_PID=$!
  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT

  echo "→ Waiting 6s for servers..."
  sleep 6

  echo "→ Chunk $CHUNK checkpoint — dispatch the corresponding verification agent per spec §11.4"
  echo "→ Backend log: /tmp/luka-verify-backend.log"
  echo "→ Frontend log: /tmp/luka-verify-frontend.log"
  ```
  ```bash
  chmod +x backend/scripts/run_chunk_verifications.sh
  ```

- [ ] **0.8 — Commit Task 0**
  ```bash
  git add backend/alembic/versions/035_budget_redesign_schema.py \
          backend/modules/households/models.py \
          backend/modules/budgets/user_budget_settings_models.py \
          backend/modules/budgets/cuota_models.py \
          backend/modules/budgets/savings_categories.py \
          backend/scripts/seed_budget_test_fixtures.py \
          backend/scripts/run_chunk_verifications.sh \
          backend/tests/test_budget_migration_035.py
  git commit -m "feat(budget-v2): chunk 0 — migrations, models, seed fixtures, verification orchestrator

  Adds Alembic 035 (contribution_mode, user_budget_settings, cuota_purchases),
  SQLAlchemy models, savings-category set, seed script for all 4 test households,
  and verification orchestrator script. Blocker for chunks A–H.

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task A — Currency formatter + page scaffolding

> Runs in parallel with B, C, D, E, F. Subagent, own worktree.

**Files:**
- Create: `frontend/app/lib/format.ts`
- Modify: `frontend/app/(dashboard)/budgets/page.tsx` (rewrite)
- Test: manual via Chunk A verification agent (§11.4)

### Steps

- [ ] **A.1 — Write `formatMoney` helper**

  Create `frontend/app/lib/format.ts`:
  ```typescript
  export type Currency = "CLP" | "USD";

  export function formatMoney(amount: number, currency: Currency): string {
    if (currency === "CLP") {
      return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
      }).format(Math.round(amount));
    }
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  }
  ```

- [ ] **A.2 — Rewrite the budget page to a scaffolded two-section layout**

  Replace `frontend/app/(dashboard)/budgets/page.tsx` with the new scaffold. It should:
  - Keep the month selector
  - Add a currency toggle using the **existing** `<CurrencyToggle>` component at `frontend/app/(dashboard)/components/CurrencyToggle.tsx`, wired to page-local `selectedCurrency` state seeded from `me.preferred_currency`
  - **Auto-hide the toggle** when `budgetV2Data?.currencies_available.length <= 1`. The `currencies_available` field is added to the `/budgets/v2/` response by Chunk C (coordination note: Chunk C must include this field; it's a simple `SELECT DISTINCT currency FROM transactions WHERE user_id = ... AND transaction_date ∈ month`). Until Chunk C lands, the toggle shows unconditionally — this is acceptable during the parallel sprint and auto-corrects when C merges.
  - Render two empty `<section>` placeholders with headings `"HOGAR"` and `"PERSONAL"` — other chunks fill them in
  - Remove all references to the old `CLP()` function and `usePersonalBudget`/`useAllocation` hooks
  - Use `formatMoney(x, selectedCurrency)` throughout

  Template skeleton:
  ```tsx
  "use client";
  import { useState } from "react";
  import { useQuery } from "@tanstack/react-query";
  import { ChevronLeft, ChevronRight } from "lucide-react";
  import { api } from "@/app/lib/api";
  import { formatMoney, type Currency } from "@/app/lib/format";
  import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";

  function getMonthParam(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
  }

  export default function BudgetsPage() {
    const [selectedMonth, setSelectedMonth] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
    const { data: me } = useQuery({
      queryKey: ["me"],
      queryFn: () => api.getMe(),
      staleTime: 5 * 60 * 1000,
    });
    const [selectedCurrency, setSelectedCurrency] = useState<Currency>((me?.preferred_currency ?? "CLP") as Currency);
    // TODO(Chunk C): wire real data. For now, sections are empty placeholders.
    return (
      <div className="space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Presupuesto</h2>
            <p className="text-sm text-gray-400 mt-0.5">Control de ingresos y gastos</p>
          </div>
          <CurrencyToggle value={selectedCurrency} onChange={setSelectedCurrency} />
        </div>
        {/* Month selector (existing pattern) */}
        {/* ... */}
        <section aria-labelledby="household-budget-heading" className="space-y-4">
          <h3 id="household-budget-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-400">Hogar</h3>
          <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-[var(--shadow-card)]">
            <p className="text-sm text-slate-400">Sankey Hogar — Chunk B</p>
          </div>
        </section>
        <section aria-labelledby="personal-budget-heading" className="space-y-4">
          <h3 id="personal-budget-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-400">Personal</h3>
          <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-[var(--shadow-card)]">
            <p className="text-sm text-slate-400">Sankey Personal — Chunk B</p>
          </div>
        </section>
      </div>
    );
  }
  ```

- [ ] **A.3 — Verify the page compiles and loads**

  ```bash
  cd frontend && npm run build
  ```
  Expected: build succeeds with no TypeScript errors. If `CurrencyToggle` is not already exported by name, change its definition at `frontend/app/(dashboard)/components/CurrencyToggle.tsx` to a named export — do not rename the file.

- [ ] **A.4 — Dispatch Chunk A verification agent** (§11.4 row)

  Use the `browser-use` skill or dispatch a general-purpose agent with a brief pointing at spec §11.4 "Chunk A" row. The agent must verify formatter output, toggle DOM presence rules, and re-render behavior. **Do not merge** until it reports pass.

- [ ] **A.5 — Commit Task A**
  ```bash
  git add frontend/app/lib/format.ts frontend/app/(dashboard)/budgets/page.tsx
  git commit -m "feat(budget-v2): chunk A — currency formatter + scaffolded two-section page

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task B — Sankey component (frontend only)

> Runs in parallel with A, C, D, E, F. Subagent, own worktree.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetSankey.tsx`
- Create: `frontend/app/(dashboard)/components/__sankey-dev.tsx` (dev-only test page, **gitignored after B merges**)
- Create: `docs/superpowers/specs/screenshots/` (directory for verification screenshots)

### Steps

- [ ] **B.1 — Write a minimal failing test via visual assertion**

  Since Luka has no frontend test infra, the "test" for this chunk is the verification agent screenshotting the dev page and asserting the DOM contains 8 expected nodes. Build the dev fixture first.

  Create `frontend/app/(dashboard)/components/__sankey-dev.tsx`:
  ```tsx
  "use client";
  import BudgetSankey from "./BudgetSankey";

  const fakePayload = {
    nodes: [
      { id: "income", label: "Ingresos", value: 1800000 },
      { id: "known_bills", label: "Gastos fijos", value: 520000 },
      { id: "cuotas", label: "Cuotas del mes", value: 120000 },
      { id: "savings_target", label: "Meta de ahorro", value: 300000 },
      { id: "spendable", label: "Disponible", value: 860000 },
      { id: "spent_restaurants", label: "Restaurantes", value: 142000, risk: true },
      { id: "spent_groceries", label: "Supermercado", value: 180000, risk: true },
      { id: "spent_other", label: "Otros", value: 95000 },
    ],
    links: [
      { source: "income", target: "known_bills", value: 520000 },
      { source: "income", target: "cuotas", value: 120000 },
      { source: "income", target: "savings_target", value: 300000 },
      { source: "income", target: "spendable", value: 860000 },
      { source: "spendable", target: "spent_restaurants", value: 142000 },
      { source: "spendable", target: "spent_groceries", value: 180000 },
      { source: "spendable", target: "spent_other", value: 95000 },
    ],
  };

  export default function SankeyDev() {
    return <BudgetSankey nodes={fakePayload.nodes} links={fakePayload.links} currency="CLP" />;
  }
  ```

- [ ] **B.2 — Write the `BudgetSankey` component using Recharts**

  Create `frontend/app/(dashboard)/components/BudgetSankey.tsx`:
  ```tsx
  "use client";
  import { Sankey, Tooltip, ResponsiveContainer, Rectangle, Layer } from "recharts";
  import { formatMoney, type Currency } from "@/app/lib/format";

  type Node = { id: string; label: string; value: number; risk?: boolean };
  type Link = { source: string; target: string; value: number };

  interface Props {
    nodes: Node[];
    links: Link[];
    currency: Currency;
  }

  const NODE_COLOR = {
    income: "#2563EB",       // luka-primary
    known_bills: "#94A3B8",  // slate-400
    cuotas: "#F59E0B",       // luka-warning amber
    savings_target: "#10B981", // luka-success emerald
    spendable: "#60A5FA",    // luka-sky
    other: "#CBD5E1",        // slate-300
    risk: "#EF4444",         // luka-danger red
  };

  function colorFor(node: Node): string {
    if (node.risk) return NODE_COLOR.risk;
    if (node.id in NODE_COLOR) return NODE_COLOR[node.id as keyof typeof NODE_COLOR];
    return NODE_COLOR.other;
  }

  export default function BudgetSankey({ nodes, links, currency }: Props) {
    // Recharts Sankey expects `{ nodes: [{name}], links: [{source: idx, target: idx, value}] }`
    const idToIndex = new Map(nodes.map((n, i) => [n.id, i]));
    const data = {
      nodes: nodes.map((n) => ({ name: n.label, ...n })),
      links: links.map((l) => ({
        source: idToIndex.get(l.source)!,
        target: idToIndex.get(l.target)!,
        value: l.value,
      })),
    };

    return (
      <div className="w-full overflow-x-auto">
        <div className="min-w-[720px] h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <Sankey
              data={data}
              nodePadding={24}
              nodeWidth={16}
              linkCurvature={0.5}
              iterations={32}
              node={(props: any) => {
                const { x, y, width, height, index } = props;
                const node = nodes[index];
                return (
                  <Layer key={`node-${index}`}>
                    <Rectangle x={x} y={y} width={width} height={height} fill={colorFor(node)} fillOpacity={0.9} />
                    <text x={x + width + 6} y={y + height / 2} dy="0.35em" className="text-xs fill-slate-700">
                      {node.label}
                    </text>
                    <text x={x + width + 6} y={y + height / 2 + 14} className="text-[10px] fill-slate-400 tabular-nums">
                      {formatMoney(node.value, currency)}
                    </text>
                  </Layer>
                );
              }}
              link={{ stroke: "#CBD5E1", strokeOpacity: 0.4 }}
            >
              <Tooltip
                formatter={(value: number) => formatMoney(value, currency)}
              />
            </Sankey>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }
  ```

- [ ] **B.3 — Temporarily mount the dev page**

  Add a dev route at `frontend/app/(dashboard)/__dev/sankey/page.tsx`:
  ```tsx
  import SankeyDev from "@/app/(dashboard)/components/__sankey-dev";
  export default function Page() { return <div className="p-6"><SankeyDev /></div>; }
  ```

- [ ] **B.4 — Visual smoke check locally**

  ```bash
  cd frontend && npm run dev
  ```
  Open `http://localhost:3000/__dev/sankey` — expect a rendered Sankey with 8 nodes and 7 links. Risk-tagged nodes (Restaurantes, Supermercado) render red.

- [ ] **B.5 — Dispatch Chunk B verification agent** (§11.4 row)

  Agent opens `/__dev/sankey` at desktop (1440×900) and mobile (375×667) viewports, takes screenshots, asserts horizontal scroll on mobile, commits PNGs to `docs/superpowers/specs/screenshots/sankey-v1-desktop.png` and `sankey-v1-mobile.png`.

- [ ] **B.6 — Commit Task B**
  ```bash
  git add frontend/app/(dashboard)/components/BudgetSankey.tsx \
          frontend/app/(dashboard)/components/__sankey-dev.tsx \
          frontend/app/(dashboard)/__dev/sankey/page.tsx \
          docs/superpowers/specs/screenshots/
  git commit -m "feat(budget-v2): chunk B — BudgetSankey component + dev fixture

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task C — Backend `/budgets/v2` endpoint + forecast engine

> **Critical path.** Runs in parallel with A, B, D, E, F (after Task 0). Subagent.

**Files:**
- Create: `backend/modules/budgets/forecast.py`
- Create: `backend/modules/budgets/cuota_service.py`
- Create: `backend/modules/budgets/v2_service.py`
- Create: `backend/modules/budgets/v2_schemas.py`
- Modify: `backend/modules/budgets/router.py` (add new route)
- Create: `backend/tests/fixtures/budget_v2_sample_response.json` (Day 1 contract fixture — see spec §9 Chunk C)
- Test: `backend/tests/test_budget_forecast.py`
- Test: `backend/tests/test_budget_v2_endpoint.py`

### Steps

- [ ] **C.1 — Commit the contract fixture FIRST** (Day 1 deliverable per spec)

  Create `backend/tests/fixtures/budget_v2_sample_response.json` with this exact content. Chunks B, G, H consume it as a fake before C's endpoint is wired — **this JSON is the frozen contract between C and every frontend consumer**.

  ```json
  {
    "view": "personal",
    "month": "2026-04-01",
    "currency": "CLP",
    "currencies_available": ["CLP", "USD"],
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
      },
      {
        "name": "Supermercado",
        "spent": 180000,
        "cap": 220000,
        "historical_mean": 215000,
        "historical_std": 28000,
        "p_overshoot": 0.71,
        "projected_final": 248000,
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

  C.5 (Pydantic schemas) must include a test that loads this fixture and validates it with `BudgetV2Response.model_validate_json(...)` — this locks the schema against drift.

  ```bash
  git add backend/tests/fixtures/budget_v2_sample_response.json
  git commit -m "feat(budget-v2): chunk C — commit /budgets/v2 API contract fixture

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

- [ ] **C.2 — Write failing forecast.py tests**

  Create `backend/tests/test_budget_forecast.py` with tests for each pure function. Example:
  ```python
  from decimal import Decimal
  from modules.budgets.forecast import (
      category_stats, select_risk_categories, pace_forecast,
      overshoot_probability, runway_days, spendable_ceiling,
  )

  def test_category_stats_three_month_mean_and_std():
      # Given 3 months [100, 200, 300] -> mean 200, std 100
      monthly_spends = [Decimal("100"), Decimal("200"), Decimal("300")]
      mean, std, n = category_stats(monthly_spends)
      assert mean == Decimal("200")
      assert abs(std - Decimal("100")) < Decimal("0.01")
      assert n == 3

  def test_select_risk_categories_top_5_by_share_times_cv():
      # Category A: huge + stable (low CV) -> not risk
      # Category B: huge + chaotic -> risk
      # Category C: tiny + chaotic -> not risk
      stats = {
          "A": (Decimal("1000000"), Decimal("10000"), 3),
          "B": (Decimal("500000"), Decimal("200000"), 3),
          "C": (Decimal("20000"), Decimal("10000"), 3),
      }
      risks = select_risk_categories(stats, top_n=2)
      assert risks[0][0] == "B"

  def test_pace_forecast_linear_with_day_guard():
      # Day 1 spent 100, 30-day month -> guarded to day 3 -> 100 * 30/3 = 1000
      projected, _ = pace_forecast(
          spent_so_far=Decimal("100"),
          current_day=1,
          days_in_month=30,
          historical_std=Decimal("50"),
      )
      assert projected == Decimal("1000")

  def test_overshoot_probability_over_cap():
      p = overshoot_probability(
          projected=Decimal("200000"),
          cap=Decimal("100000"),
          std=Decimal("20000"),
      )
      assert p > Decimal("0.99")

  def test_overshoot_probability_well_under_cap():
      p = overshoot_probability(
          projected=Decimal("50000"),
          cap=Decimal("200000"),
          std=Decimal("20000"),
      )
      assert p < Decimal("0.01")

  def test_runway_days_basic():
      assert runway_days(Decimal("400000"), Decimal("50000")) == 8

  def test_spendable_ceiling_subtracts_all_carveouts():
      ceiling = spendable_ceiling(
          income=Decimal("2000000"),
          known_bills=Decimal("500000"),
          cuotas_this_month=Decimal("100000"),
          savings_target=Decimal("300000"),
      )
      assert ceiling == Decimal("1100000")
  ```

  Run: `pytest tests/test_budget_forecast.py -v`
  Expected: all fail with ImportError.

- [ ] **C.3 — Implement `forecast.py` pure functions**

  Create `backend/modules/budgets/forecast.py`:
  ```python
  """Budget forecast engine — v1 heuristic implementation.

  Same function signatures as the future Bayesian engine (spec §6.2 / §6.3).
  Phase 2 swaps internals; the contract is stable.
  """
  from decimal import Decimal
  from math import sqrt, erf
  from statistics import mean, pstdev
  from typing import Iterable


  def category_stats(monthly_spends: Iterable[Decimal]) -> tuple[Decimal, Decimal, int]:
      vals = [v for v in monthly_spends]
      if len(vals) == 0:
          return Decimal("0"), Decimal("0"), 0
      m = Decimal(str(mean(float(v) for v in vals)))
      s = Decimal(str(pstdev(float(v) for v in vals))) if len(vals) > 1 else Decimal("0")
      return m, s, len(vals)


  def select_risk_categories(
      stats: dict[str, tuple[Decimal, Decimal, int]],
      top_n: int = 5,
  ) -> list[tuple[str, Decimal]]:
      """Top N categories by (share_of_total × coefficient_of_variation)."""
      total = sum((m for m, _, _ in stats.values()), Decimal("0"))
      if total == 0:
          return []
      scored: list[tuple[str, Decimal]] = []
      for cat, (m, s, _) in stats.items():
          if m == 0:
              continue
          share = m / total
          cv = s / m
          scored.append((cat, share * cv))
      scored.sort(key=lambda x: x[1], reverse=True)
      return scored[:top_n]


  def pace_forecast(
      spent_so_far: Decimal,
      current_day: int,
      days_in_month: int,
      historical_std: Decimal,
  ) -> tuple[Decimal, Decimal]:
      """Linear pace projection with day-3 guard (spec §6.2)."""
      effective_day = max(current_day, 3)
      projected = spent_so_far * Decimal(days_in_month) / Decimal(effective_day)
      return projected, historical_std  # std passed through for downstream overshoot calc


  def _norm_cdf(x: float) -> float:
      return 0.5 * (1.0 + erf(x / sqrt(2.0)))


  def overshoot_probability(projected: Decimal, cap: Decimal, std: Decimal) -> Decimal:
      if std <= 0:
          return Decimal("1") if projected > cap else Decimal("0")
      z = float((cap - projected) / std)
      p = 1.0 - _norm_cdf(z)
      return Decimal(str(round(p, 4)))


  def runway_days(spendable_remaining: Decimal, daily_burn_14: Decimal) -> int:
      if daily_burn_14 <= 0:
          return 999
      return int(spendable_remaining / daily_burn_14)


  def spendable_ceiling(
      income: Decimal,
      known_bills: Decimal,
      cuotas_this_month: Decimal,
      savings_target: Decimal,
  ) -> Decimal:
      return income - known_bills - cuotas_this_month - savings_target
  ```

  Run: `pytest tests/test_budget_forecast.py -v`
  Expected: all pass.

- [ ] **C.4 — Write `cuota_service.py`**

  Create `backend/modules/budgets/cuota_service.py` with `get_active_cuotas_summary(db, user_id, month, currency)` and household variant. Returns `{this_month: Decimal, future_total: Decimal, active_count: int}` per spec §7.1. Sum cuota installments where `first_cuota_date <= month_end` and `last_cuota_date >= month_start` and `status='active'`.

- [ ] **C.5 — Write `v2_schemas.py` (Pydantic response models) and fixture-lock test**

  Create `backend/modules/budgets/v2_schemas.py` with Pydantic models matching spec §7.1 exactly. One nested model per top-level key: `SankeyNode`, `SankeyLink`, `SankeyBlock`, `SpendableBlock`, `RiskCategory`, `RunwayBlock`, `CuotasBlock`, `SavingsTargetBlock`, `BudgetV2Response`. The `BudgetV2Response` must include `currencies_available: list[str]` (coordination with Chunk A — the frontend uses this to auto-hide the currency toggle).

  Add to `backend/tests/test_budget_v2_endpoint.py` a fixture-lock test:
  ```python
  import json
  from pathlib import Path
  from modules.budgets.v2_schemas import BudgetV2Response

  def test_contract_fixture_matches_pydantic_schema():
      """Prevents drift between the committed contract fixture and the live schema.

      Chunks B, G, H build against the fixture; if the schema changes without
      updating the fixture (or vice versa), frontend breaks mid-sprint.
      """
      fixture = Path(__file__).parent / "fixtures" / "budget_v2_sample_response.json"
      with open(fixture) as f:
          data = json.load(f)
      BudgetV2Response.model_validate(data)  # raises if drift
  ```

- [ ] **C.5.5 — Add a household-scoped known_bills helper to the subscriptions module**

  **Gap discovered during plan review:** `backend/modules/subscriptions/service.py:127 get_detected_subscriptions(db, user_id, months_back)` is strictly **user-scoped**. No household variant exists. The v2 endpoint needs both (personal view → single user; household view → sum across members respecting contribution_mode).

  Create `backend/modules/subscriptions/read.py`:
  ```python
  from datetime import date
  from decimal import Decimal
  from sqlalchemy.ext.asyncio import AsyncSession
  from modules.subscriptions.service import get_detected_subscriptions
  from modules.households.models import HouseholdMember


  async def get_user_known_bills(
      db: AsyncSession, user_id, currency: str
  ) -> Decimal:
      """Monthly total of recurring bills for one user in one currency."""
      result = await get_detected_subscriptions(db, user_id, months_back=6)
      summary = result.get("summary_by_currency", {}).get(currency, {})
      return Decimal(str(summary.get("monthly_total", 0)))


  async def get_household_known_bills(
      db: AsyncSession, household_id, currency: str
  ) -> Decimal:
      """Sum of active members' recurring bills in one currency.

      Note: does NOT filter by contribution_mode here — the v2_service is
      responsible for deciding whether each member's bills count toward
      the household pot (full + fixed) or their own personal view only
      (reimbursement). This function is just the raw per-member sum.
      """
      from sqlalchemy import select
      stmt = select(HouseholdMember.user_id).where(
          HouseholdMember.household_id == household_id,
          HouseholdMember.left_at.is_(None),
      )
      result = await db.execute(stmt)
      member_ids = [row[0] for row in result]
      total = Decimal("0")
      for uid in member_ids:
          total += await get_user_known_bills(db, uid, currency)
      return total
  ```

  Unit test in `backend/tests/test_subscriptions_read.py` — mock `get_detected_subscriptions` and assert the household helper sums correctly across 2 seeded members.

- [ ] **C.6 — Write `v2_service.py`**

  Create `backend/modules/budgets/v2_service.py` with `async def get_budget_v2(db, household_id, user_id, month, currency, view)`. Responsibilities:
  1. Resolve known_bills:
     - `view=personal` → `get_user_known_bills(db, user_id, currency)`
     - `view=household` → `get_household_known_bills(db, household_id, currency)` — **but skip `reimbursement` members' bills from the household total** (their bills are their own personal concern, not the household pot)
  2. Resolve cuotas via `cuota_service.get_active_cuotas_summary`
  3. Resolve savings target from `user_budget_settings`:
     - `view=personal` → the caller's own row
     - `view=household` → sum of savings targets for all members whose `contribution_mode IN ('full','fixed')` (spec §5.2 rule — reimbursement members don't contribute to the household pot, so their personal savings is excluded)
  4. Resolve income per spec §6.2 table (full vs fixed vs reimbursement per view) — **delegate to `backend/modules/households/contribution_service.py` (created by Chunk D)**; until D lands, inline the logic and refactor on merge
  5. Resolve spent via the existing transaction aggregates, **excluding categories where `is_savings_category(category)` is True** (from `savings_categories.py`)
  6. Call `forecast.py` primitives to build risk_categories and runway blocks
  7. Cache the risk category set in Redis under `budget:risk:{user_id}:{YYYY-MM}` with month-long TTL
  8. Populate `currencies_available` via `SELECT DISTINCT currency FROM transactions WHERE user_id = ? AND transaction_date BETWEEN ? AND ?` (plus household-member union when `view=household`)
  9. Assemble the `BudgetV2Response` — the Sankey nodes/links are derived from the same aggregates in the same request (contract guarantee per spec §7.1)

- [ ] **C.7 — Write endpoint + integration test**

  Modify `backend/modules/budgets/router.py` to add:
  ```python
  from modules.budgets.v2_service import get_budget_v2
  from modules.budgets.v2_schemas import BudgetV2Response

  @router.get("/v2/{household_id}", response_model=BudgetV2Response)
  async def budget_v2(
      household_id: uuid.UUID,
      month: date | None = None,
      currency: str | None = Query(default=None),
      view: str = Query(default="personal", regex="^(personal|household)$"),
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(get_current_user),
  ):
      if month is None:
          month = date.today().replace(day=1)
      return await get_budget_v2(db, household_id, current_user.id, month, currency, view)
  ```

  Create `backend/tests/test_budget_v2_endpoint.py` with:
  - Test: seeded household returns valid schema
  - Test: `view=personal` for a `fixed`-mode caller returns their **real income** (not fixed_contribution)
  - Test: `view=household` for a `fixed`-mode member returns only the `fixed_contribution_amount` — **recursively walk the JSON and assert no field equals the real income value ($1,800,000)**
  - Test: `Inversión`-categorized transactions do NOT count in `spendable.spent`
  - Test: cuotas block returns the correct `this_month` and `future_total` for the seeded cuota

  Run: `pytest tests/test_budget_v2_endpoint.py -v`
  Expected: all pass.

- [ ] **C.8 — Dispatch Chunk C verification agent** (§11.4 row)

  Bash-only agent runs `curl` against the endpoint for all 4 seeded test users and validates with the committed JSON schema. Also runs the privacy recursive walk on the HOGAR FIXED household response.

- [ ] **C.9 — Commit Task C**
  ```bash
  git add backend/modules/budgets/forecast.py \
          backend/modules/budgets/cuota_service.py \
          backend/modules/budgets/v2_schemas.py \
          backend/modules/budgets/v2_service.py \
          backend/modules/budgets/router.py \
          backend/modules/subscriptions/read.py \
          backend/tests/test_budget_forecast.py \
          backend/tests/test_budget_v2_endpoint.py \
          backend/tests/test_subscriptions_read.py
  git commit -m "feat(budget-v2): chunk C — /budgets/v2 endpoint + forecast engine (v1 heuristics)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task D — Contribution modes (backend + Settings UI)

> Runs in parallel with B, C, E, F. Subagent.

**Files:**
- Create: `backend/modules/households/contribution_service.py`
- Modify: `backend/modules/households/router.py` (add `PATCH /settings/contribution`)
- Modify: `backend/modules/budgets/v2_service.py` (coordinate with Chunk C — use the contribution_service helper when computing household income)
- Create: `frontend/app/(dashboard)/settings/components/ContributionSection.tsx`
- Modify: `frontend/app/(dashboard)/settings/page.tsx` (mount the new section)
- Modify: `frontend/app/lib/api.ts` (add `updateContribution`)
- Test: `backend/tests/test_contribution_modes.py`

### Steps

- [ ] **D.1 — Write the privacy test first (TDD red)**

  Create `backend/tests/helpers/json_walk.py` (shared test helper — also used by Task C's privacy test):
  ```python
  from decimal import Decimal


  def walk_json(obj):
      """Yield every leaf value in a JSON-parsed structure."""
      if isinstance(obj, dict):
          for v in obj.values():
              yield from walk_json(v)
      elif isinstance(obj, list):
          for v in obj:
              yield from walk_json(v)
      else:
          yield obj


  def assert_value_absent(obj, forbidden_value: Decimal | int | float):
      """Raise AssertionError if any leaf equals `forbidden_value` (Decimal-aware)."""
      forbidden = Decimal(str(forbidden_value))
      for leaf in walk_json(obj):
          if leaf is None:
              continue
          try:
              if Decimal(str(leaf)) == forbidden:
                  raise AssertionError(
                      f"Forbidden value {forbidden} found in response JSON"
                  )
          except (ValueError, ArithmeticError):
              continue  # not numeric — skip
  ```

  Create `backend/tests/test_contribution_modes.py` (per spec §11.1):
  ```python
  import pytest
  from tests.helpers.json_walk import assert_value_absent

  # Seeded fixture constants — must not drift from seed_budget_test_fixtures.py
  REAL_INCOME_FIXED_MEMBER = 1_800_000
  FIXED_CONTRIBUTION = 800_000
  PARTNER_REAL_INCOME = 2_100_000


  @pytest.mark.asyncio
  async def test_fixed_mode_does_not_leak_real_income(
      db, http_client, seeded_fixed_household, authenticated_partner_client,
  ):
      """Per spec §7.3 — fixed-mode member's real income must never appear in view=household."""
      resp = await authenticated_partner_client.get(
          f"/budgets/v2/{seeded_fixed_household.id}?view=household"
      )
      assert resp.status_code == 200
      payload = resp.json()

      # (a) real income value must not appear anywhere in the response
      assert_value_absent(payload, REAL_INCOME_FIXED_MEMBER)

      # (b) household income = partner's real income + fixed contribution
      assert payload["spendable"]["amount"] is not None
      # (The exact field to check depends on schema; adjust to the `income` node in sankey.)
      income_node = next(n for n in payload["sankey"]["nodes"] if n["id"] == "income")
      assert int(income_node["value"]) == PARTNER_REAL_INCOME + FIXED_CONTRIBUTION
  ```

  Run: `pytest tests/test_contribution_modes.py -v`
  Expected: fails (fixtures or endpoint not wired).

- [ ] **D.2 — Implement `contribution_service.py`**

  Create the service with two helpers:
  - `async def income_for_household_view(db, household_id, currency, month) -> Decimal` — sums real income for `full` members, fixed amount for `fixed` members, skips `reimbursement`
  - `async def income_for_personal_view(db, user_id, currency, month) -> Decimal` — always the caller's real income
  - `async def update_contribution(db, user_id, household_id, mode, fixed_amount, fixed_currency)` — validates mode and writes to `household_members`

- [ ] **D.3 — Implement the settings endpoint**

  Modify `backend/modules/households/router.py` (or create a new `settings_router.py` if cleaner):
  ```python
  @router.patch("/settings/contribution")
  async def update_contribution_mode(
      payload: ContributionUpdateRequest,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(get_current_user),
  ):
      ...
  ```

- [ ] **D.4 — Wire Chunk C's `v2_service` to use `contribution_service`**

  Coordinate with Chunk C agent: import `income_for_household_view` / `income_for_personal_view` and replace any inline income computation in `v2_service.py`.

- [ ] **D.5 — Frontend Settings section**

  Create `frontend/app/(dashboard)/settings/components/ContributionSection.tsx` with 3-way radio (`Completa` / `Fija` / `Sólo reembolso`), amount + currency inputs shown only when `Fija`, and a `useMutation` hook wired to `api.updateContribution`.

  Mount it in `frontend/app/(dashboard)/settings/page.tsx` after `<CompartidoSection />`.

- [ ] **D.6 — Run the privacy test and verify green**

  ```bash
  cd backend && pytest tests/test_contribution_modes.py -v
  ```
  Expected: pass.

- [ ] **D.7 — Dispatch Chunk D verification agent** (§11.4 row)

- [ ] **D.8 — Commit Task D**
  ```bash
  git add backend/modules/households/contribution_service.py \
          backend/modules/households/router.py \
          backend/modules/budgets/v2_service.py \
          backend/tests/test_contribution_modes.py \
          frontend/app/(dashboard)/settings/components/ContributionSection.tsx \
          frontend/app/(dashboard)/settings/page.tsx \
          frontend/app/lib/api.ts
  git commit -m "feat(budget-v2): chunk D — contribution modes (full/fixed/reimbursement)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task E — Cuotas (manual entry)

> Runs in parallel with B, C, D, F. Subagent.

**Files:**
- Create: `backend/modules/budgets/cuota_router.py`
- Create: `backend/modules/budgets/cuota_schemas.py`
- Modify: `backend/main.py` (register cuota router)
- Create: `frontend/app/(dashboard)/components/MarkAsCuotaDialog.tsx`
- Modify: `frontend/app/(dashboard)/components/TransactionCard.tsx` (add "Marcar como cuota" action to the transaction detail view)
- Modify: `frontend/app/lib/hooks/useCuotas.ts` (new file)
- Modify: `frontend/app/lib/api.ts` (add `createCuota`, `listCuotas`, `cancelCuota`)
- Test: `backend/tests/test_cuota_service.py`

### Steps

- [ ] **E.1 — Write failing tests for `cuota_service`**

  Create `backend/tests/test_cuota_service.py` covering:
  - `create` persists a row with computed `monthly_amount` and `last_cuota_date`
  - `get_active_cuotas_summary` returns correct `this_month`, `future_total`, `active_count` for a seeded cuota
  - Month-boundary edge cases (first cuota last month, last cuota this month)

- [ ] **E.2 — Implement the service layer**

  Extend `backend/modules/budgets/cuota_service.py` (created in Task C) with CRUD functions:
  ```python
  async def create_cuota(db, user_id, household_id, data: CuotaCreate) -> CuotaPurchase
  async def list_active_cuotas(db, user_id_or_household_id) -> list[CuotaPurchase]
  async def cancel_cuota(db, cuota_id, user_id) -> None
  ```

- [ ] **E.3 — Write CRUD router + schemas**

  `cuota_router.py` exposes:
  - `POST /cuotas`
  - `GET /cuotas`
  - `PATCH /cuotas/{id}` (status update only)
  - `DELETE /cuotas/{id}`

  Register in `main.py`.

- [ ] **E.4 — Frontend: add dialog + action**

  `MarkAsCuotaDialog.tsx` — modal with total_amount (pre-filled), installments_total input, first_cuota_date date picker, currency select. Submit via `useCuotas` hook.

  In `TransactionCard.tsx` (or wherever the transaction detail opens), add a "Marcar como cuota" button that opens the dialog with the transaction's amount/merchant/currency.

- [ ] **E.5 — Dispatch Chunk E verification agent** (§11.4 row)

- [ ] **E.6 — Commit Task E**
  ```bash
  git add backend/modules/budgets/cuota_router.py \
          backend/modules/budgets/cuota_schemas.py \
          backend/modules/budgets/cuota_service.py \
          backend/main.py \
          backend/tests/test_cuota_service.py \
          frontend/app/(dashboard)/components/MarkAsCuotaDialog.tsx \
          frontend/app/(dashboard)/components/TransactionCard.tsx \
          frontend/app/lib/hooks/useCuotas.ts \
          frontend/app/lib/api.ts
  git commit -m "feat(budget-v2): chunk E — cuotas (manual entry, CRUD, dialog)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task F — Savings target + investment-as-savings

> Runs in parallel with B, C, D, E. Subagent.

**Files:**
- Create: `backend/modules/budgets/user_budget_settings_service.py`
- Create: `backend/modules/budgets/user_budget_settings_router.py`
- Modify: `backend/main.py` (register router)
- Modify: `backend/modules/budgets/v2_service.py` (coordinate with Chunk C — subtract savings_target, exclude savings categories from spent)
- Create: `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx`
- Modify: `frontend/app/(dashboard)/settings/page.tsx`
- Modify: `frontend/app/lib/api.ts`
- Test: `backend/tests/test_user_budget_settings.py`

### Steps

- [ ] **F.1 — Write failing tests**

  `backend/tests/test_user_budget_settings.py`:
  ```python
  @pytest.mark.asyncio
  async def test_savings_target_reduces_spendable_ceiling(db, seeded_full_user):
      # Set savings_target = 300_000 -> spendable.amount should drop by 300_000
      ...

  @pytest.mark.asyncio
  async def test_inversion_category_excluded_from_spent(db, seeded_full_user):
      # Seed a $500_000 Inversión transaction and a $100_000 Restaurantes tx
      # Assert spent == 100_000, savings_target.progress includes 500_000
      ...
  ```

- [ ] **F.2 — Implement service + router**

  `user_budget_settings_service.py` — `get_or_create`, `update_savings_target`, `update_payday_day_of_month`
  `user_budget_settings_router.py` — `PATCH /settings/budget` (writes savings_target_amount, currency, payday_day_of_month)

- [ ] **F.3 — Coordination patch for `v2_service.py` (applied after Chunk C lands)**

  **Dependency:** `v2_service.py` is created by Chunk C. Chunk F must wait for C's merge before applying this step — **F.1 and F.2 can proceed in parallel with C**, but F.3 is a post-C rebase.

  After Chunk C lands on main:
  1. Rebase Chunk F's worktree on latest main
  2. In `v2_service.py`, ensure the `spent` computation calls `is_savings_category(tx.category)` to exclude savings transactions from `spendable_spent`, and sums them into `savings_target.progress`
  3. Ensure the `savings_target` block reads from `user_budget_settings` via the new `user_budget_settings_service.get_or_create(user_id)` helper
  4. Run Chunk C's endpoint test suite (`pytest tests/test_budget_v2_endpoint.py -v`) to confirm the post-rebase behavior is still green
  5. Run Chunk F's new test suite (`pytest tests/test_user_budget_settings.py -v`) to confirm the savings carve-out works

- [ ] **F.4 — Frontend Settings section**

  `BudgetSettingsSection.tsx` — amount + currency + payday_day_of_month (1–31 select) inputs. Wires to `api.updateBudgetSettings`.

  (Note: `payday_day_of_month` is owned here but consumed by Chunk H — coordinate with Chunk H agent on field names.)

- [ ] **F.5 — Dispatch Chunk F verification agent** (§11.4 row)

- [ ] **F.6 — Commit Task F**
  ```bash
  git add backend/modules/budgets/user_budget_settings_service.py \
          backend/modules/budgets/user_budget_settings_router.py \
          backend/main.py \
          backend/modules/budgets/v2_service.py \
          backend/tests/test_user_budget_settings.py \
          frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx \
          frontend/app/(dashboard)/settings/page.tsx \
          frontend/app/lib/api.ts
  git commit -m "feat(budget-v2): chunk F — savings target + investment-as-savings

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task G — Risk alert band (frontend)

> Runs after Chunk C fixture exists. Subagent.

**Files:**
- Create: `frontend/app/(dashboard)/components/RiskAlertBand.tsx`
- Modify: `frontend/app/(dashboard)/budgets/page.tsx`

### Steps

- [ ] **G.1 — Implement the component**

  Create `RiskAlertBand.tsx` that takes `risk_categories: RiskCategory[]` and renders only entries with `alert: true`. Silent when empty. Tailwind:
  ```tsx
  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-[var(--shadow-card)]">
    {alertsToShow.map((rc) => (
      <p key={rc.name} className="text-sm text-amber-900">
        ⚠️ <span className="font-semibold">{rc.name}</span> va al {Math.round(rc.p_overshoot * 100)}% · Al ritmo actual cerraría en {formatMoney(rc.projected_final, currency)} (límite {formatMoney(rc.cap, currency)}).
      </p>
    ))}
  </div>
  ```

- [ ] **G.2 — Mount in the budget page**

  Modify `budgets/page.tsx` to render `<RiskAlertBand>` at the top of the page when `budgetV2Data?.risk_categories.some(c => c.alert)`.

- [ ] **G.3 — Dispatch Chunk G verification agent** (§11.4 row)

- [ ] **G.4 — Commit Task G**
  ```bash
  git add frontend/app/(dashboard)/components/RiskAlertBand.tsx \
          frontend/app/(dashboard)/budgets/page.tsx
  git commit -m "feat(budget-v2): chunk G — risk alert band (silent by default)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task H — Runway card (frontend)

> Runs after Chunk C fixture + Chunk F settings exist. Subagent.

**Files:**
- Create: `frontend/app/(dashboard)/components/RunwayCard.tsx`
- Modify: `frontend/app/(dashboard)/budgets/page.tsx`

### Steps

- [ ] **H.1 — Implement the component**

  Create `RunwayCard.tsx`:
  ```tsx
  <div className={`rounded-xl border p-4 shadow-[var(--shadow-card)] ${isAtRisk ? "border-red-200 bg-red-50" : "border-slate-100 bg-white"}`}>
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Próximo sueldo</p>
    <p className={`text-lg font-bold tabular-nums ${isAtRisk ? "text-red-700" : "text-luka-dark"}`}>
      {daysToPayday} días
    </p>
    <p className="text-xs text-slate-500 mt-1 tabular-nums">Runway actual: {runwayDays} días</p>
  </div>
  ```

- [ ] **H.2 — Mount in both Hogar and Personal sections**

- [ ] **H.3 — Dispatch Chunk H verification agent** (§11.4 row)

- [ ] **H.4 — Commit Task H**
  ```bash
  git add frontend/app/(dashboard)/components/RunwayCard.tsx \
          frontend/app/(dashboard)/budgets/page.tsx
  git commit -m "feat(budget-v2): chunk H — runway card (days to payday)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task I — Day 4 Integration verification

> Serial. Runs after all A–H are merged to `main`.

**Responsibility:** full end-to-end check described in spec §11.4 "Day 4 — Integration verification agent".

### Steps

- [ ] **I.1 — Pull main, run migrations, seed fixtures, start services**
  ```bash
  git checkout main && git pull
  cd backend && alembic upgrade head && python scripts/seed_budget_test_fixtures.py
  ./scripts/run_chunk_verifications.sh day4
  ```

- [ ] **I.2 — Dispatch the Day-4 integration agent** per spec §11.4 — it runs all per-chunk checkpoints sequentially in one session, performs the end-to-end flow, inspects the Network tab for 4xx/5xx + PII leaks, and runs a Lighthouse audit (LCP < 2.5s, CLS < 0.1, no serious a11y).

- [ ] **I.3 — File bugs for any failures as separate commits**. Only proceed to Day 5 when all checkpoints green.

- [ ] **I.4 — Commit the integration report**
  ```bash
  git add docs/superpowers/specs/reviews/2026-04-14-day4-integration-report.md
  git commit -m "test(budget-v2): day 4 integration verification report (all checkpoints green)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task J — Day 6 UX / design consistency pass

> Serial. Runs after Day 5 UAT bug-fix pass.

### Steps

- [ ] **J.1 — Start services and seed fixtures**
  ```bash
  ./backend/scripts/run_chunk_verifications.sh day6
  ```

- [ ] **J.2 — Dispatch the UX consistency agent** per spec §11.4 "Day 6" procedure. Agent compares `/budgets` against `/`, `/transactions`, `/household`, `/settings` at desktop and mobile viewports. Produces `docs/superpowers/specs/reviews/2026-04-14-budget-ux-review.md` with pass/fail and screenshots.

- [ ] **J.3 — Fix any blocking fails**. Any `fail` on contrast ratio, typography scale, color token drift, or card treatment blocks Day 7.

- [ ] **J.4 — Commit the UX review**
  ```bash
  git add docs/superpowers/specs/reviews/2026-04-14-budget-ux-review.md \
          docs/superpowers/specs/screenshots/
  git commit -m "test(budget-v2): day 6 UX consistency review (approved)

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

---

## Task K — Day 7 ship

### Steps

- [ ] **K.1 — Final sanity check on main**
  ```bash
  git checkout main && git pull
  cd backend && pytest -x -q
  cd ../frontend && npm run build
  ```
  Expected: all backend tests pass; frontend build succeeds.

- [ ] **K.2 — Remove the `__dev/sankey` route**

  **Note:** paths containing `(dashboard)` must be quoted in zsh/bash — the parentheses are shell metacharacters.
  ```bash
  git rm -r 'frontend/app/(dashboard)/__dev/'
  git rm 'frontend/app/(dashboard)/components/__sankey-dev.tsx'
  git commit -m "chore(budget-v2): remove chunk B dev fixtures before ship

  Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
  git push origin main
  ```

- [ ] **K.3 — Deploy backend (Railway picks up from main)** and **frontend (Vercel auto-deploys)**. Watch logs for migration application.

- [ ] **K.4 — Post-ship smoke check in production** — log in with Rafael's real account, navigate to `/budgets`, verify Hogar + Personal sections render, currency toggle works, cuota can be created.

- [ ] **K.5 — Update `NEXT-STEPS.md`** — mark budget redesign as shipped; surface Phase 2 parking lot items (spec §13) to the active roadmap.

---

## Global notes for executing agents

1. **Do not duplicate architectural decisions from the spec** — if something is ambiguous, read the spec (§ numbers referenced throughout). The plan is execution-level only.

2. **Every chunk ends with its §11.4 verification agent passing** — that's the merge gate.

3. **Parallel chunks coordinate on FOUR shared files.** Use `git rebase` on each chunk worktree before merging; changes are additive, conflicts should be textual, not semantic:
   - `backend/modules/budgets/v2_service.py` — **created by C, patched by D (contribution helpers) and F (savings exclusion)**. F.3 and D.4 are explicit post-C rebase steps.
   - `backend/modules/budgets/cuota_service.py` — **created by C (aggregates), extended by E (CRUD)**. E.2 explicitly "extends" C's file.
   - `frontend/app/lib/api.ts` — A, D, E, F all add methods. Append-only by each chunk; rebase resolves textual conflicts.
   - `frontend/app/(dashboard)/budgets/page.tsx` — A creates the scaffold, G mounts the risk band, H mounts the runway card. A lands first; G and H rebase onto it.

4. **Merge order when all chunks are ready:**
   1. Task 0 (serial blocker — already merged before anyone else starts)
   2. **C** (unblocks contract for B, G, H consumers since fixture is already committed, but must land for backend coordination patches)
   3. A, B (frontend, independent of each other once fixture is committed)
   4. D (contribution modes — rebases on C)
   5. E (cuotas CRUD — rebases on C)
   6. F (savings target — rebases on C, F.3 is the post-C coordination patch)
   7. G, H (frontend cards — rebase on A and C)

5. **Commit frequency** — at least one commit per numbered step in Task 0, and at least one commit per sub-task (C.2, C.3, etc.) for the rest. Frequent commits make the subagent's work auditable.

6. **If a verification agent reports failure**, invoke `@superpowers:systematic-debugging` before patching — don't reach for the easiest fix.

7. **If a chunk's scope balloons past its estimate**, stop and escalate to Rafael. The 1-week sprint is non-negotiable; scope must absorb the overrun.

8. **Worktree management:** Task 0 runs on `main`. Each A–H chunk runs in its own worktree `../luka-budget-chunk-<letter>` created from `main` after Task 0 lands. `superpowers:subagent-driven-development` automates the create/cleanup/rebase cycle.
