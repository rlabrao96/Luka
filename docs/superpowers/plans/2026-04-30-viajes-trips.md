# Viajes (Trips) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a v1 Splitwise-style "Viajes" section that lets Luka users tag transactions to trips, split costs among attendees (Luka users + external name stubs), see smart balances, and auto-detect Zelle/Venmo settlements.

**Architecture:** Backend-first behind a per-user feature flag `feature_trips_enabled`. New module `backend/modules/trips/` mirrors existing `households` and `subscriptions` patterns (models / schemas / service / router). Eight new tables with RLS, mutual-exclusivity triggers vs. `transaction_splits`, and a `SECURITY DEFINER` membership function. Balance algorithm computes server-side in trip base currency with frozen FX rates. Frontend section under `frontend/app/(dashboard)/viajes/` follows existing dashboard patterns (TanStack Query, shadcn/ui, mobile-first sheets).

**Tech Stack:** Python 3.12, FastAPI 0.111, SQLAlchemy 2.0 async, Alembic, Supabase Postgres 15, Next.js 16, React 19, Tailwind 4, shadcn/ui, TanStack Query 5, Zustand 5. Tests: pytest (`asyncio_mode = auto`) with real Supabase + Hypothesis for property tests. No frontend test infra in v1 (verify via `/browser-use`).

**Spec:** `docs/superpowers/specs/2026-04-30-viajes-trips-design.md` (commit `75e3263`).

**TDD note:** every task uses red-green-refactor: write the failing test first, run it to confirm it fails, implement, run again, commit. The only exception is **schema/migration tasks** (1.1, 1.2, 1.3, 1.4): there the "test" is a metadata smoke check (does the table/column/policy exist?) — write the test first, run it red, then add the migration code, run green. Same discipline, mechanically a little different because the unit under test is a DDL artifact.

**Discovery tasks** (lookups that must happen before certain phases): clearly marked at phase entry. Don't skip them; many concrete decisions in later tasks depend on what the discovery uncovers.

**Phases (each independently mergeable behind the feature flag):**
1. Feature flag + DB migration (tables, indexes, RLS, triggers, functions)
2. Trip + attendee CRUD (models, schemas, service, router, RLS tests)
3. Trip expenses + splits (mutual exclusivity, sign convention, validation)
4. Balance computation + settlements + smart-settle plan (FX, base-currency change)
5. Invite link (hashed token, generate/rotate/revoke/join, rate-limit)
6. Suggestions inbox + settlement auto-detect (post-insert hook, dismissals)
7. Frontend section (list, detail with 4 tabs, add expense sheet, browser verification)

---

## Phase 1 — Foundation: feature flag + migration

### Task 1.1: Feature flag column on `users`

**Files:**
- Create: `backend/alembic/versions/XXXX_add_feature_trips_enabled.py` (Alembic auto-numbers)
- Modify: `backend/modules/auth/models.py` (add column to `User` SQLAlchemy model)
- Test: `backend/tests/test_feature_trips_flag.py`

- [ ] **Step 1: Generate migration skeleton**

```bash
cd backend && uv run alembic revision -m "add_feature_trips_enabled_to_users"
```

- [ ] **Step 2: Edit migration**

```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "feature_trips_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

def downgrade() -> None:
    op.drop_column("users", "feature_trips_enabled")
```

- [ ] **Step 3: Add column to ORM**

In `backend/modules/auth/models.py`, on `User`:

```python
feature_trips_enabled: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default=text("false")
)
```

- [ ] **Step 4: Write failing test**

```python
# backend/tests/test_feature_trips_flag.py
import pytest
from modules.auth.models import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_feature_trips_enabled_defaults_false(db_session, make_user):
    user = await make_user()
    fetched = (await db_session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert fetched.feature_trips_enabled is False
```

- [ ] **Step 5: Run migration + test**

```bash
cd backend && uv run alembic upgrade head && uv run pytest tests/test_feature_trips_flag.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/*feature_trips_enabled*.py backend/modules/auth/models.py backend/tests/test_feature_trips_flag.py
git commit -m "feat(trips): add feature_trips_enabled flag column to users"
```

---

### Task 1.2: Migration — eight new tables (DDL only, no constraints between them yet)

**Files:**
- Create: `backend/alembic/versions/YYYY_create_trips_tables.py`
- Test: `backend/tests/test_trips_migration.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && uv run alembic revision -m "create_trips_tables"
```

- [ ] **Step 2: Write upgrade()** — see spec §3 for the canonical schema.

Tables in order (FK dependencies dictate creation order):
1. `trips` (no FK to other trip tables)
2. `trip_attendees` (FK trips, FK users)
3. `trip_expenses` (FK trips, FK trip_attendees, FK transactions, FK users)
4. `trip_expense_splits` (FK trip_expenses, FK trip_attendees)
5. `trip_settlements` (FK trips, FK trip_attendees ×2, FK transactions, FK users)
6. `trip_suggestion_dismissals` (FK users, FK trips, FK transactions)
7. `trip_settlement_dismissals` (FK users, FK transactions)
8. `trip_base_currency_changes` (FK trips, FK users)

For `trips` use `invite_token_hash TEXT` (not the raw token). Add all CHECK constraints listed in the spec:
- `trip_expenses.amount > 0`
- `trip_settlements.amount > 0`
- `trip_settlements.from_attendee_id <> to_attendee_id`
- `trips.end_date >= trips.start_date`

**Critical columns the reviewer flagged — do not omit:**
- `trip_expenses.version int NOT NULL DEFAULT 1` (powers `If-Match` optimistic concurrency in Task 3.3 — spec §3.3).
- `trip_settlements.write_off boolean NOT NULL DEFAULT false` (force-remove audit flag in Task 4.6 — spec §3.5).

Indexes:
- Unique partial: `trip_expenses(transaction_id) WHERE transaction_id IS NOT NULL AND deleted_at IS NULL`
- Unique partial: `trip_attendees(trip_id, user_id) WHERE user_id IS NOT NULL`
- Unique: `trip_expense_splits(trip_expense_id, attendee_id)`
- Unique partial: `trips(invite_token_hash) WHERE invite_token_hash IS NOT NULL`
- Plain: `trip_id` on every child table.

- [ ] **Step 3: Write downgrade()** — drop in reverse order.

- [ ] **Step 4: Write failing schema test**

```python
# backend/tests/test_trips_migration.py
import pytest
from sqlalchemy import text

TRIP_TABLES = [
    "trips", "trip_attendees", "trip_expenses", "trip_expense_splits",
    "trip_settlements", "trip_suggestion_dismissals",
    "trip_settlement_dismissals", "trip_base_currency_changes",
]

@pytest.mark.asyncio
async def test_all_trip_tables_exist(db_session):
    for t in TRIP_TABLES:
        result = await db_session.execute(
            text("SELECT to_regclass(:n)").bindparams(n=f"public.{t}")
        )
        assert result.scalar() is not None, f"{t} missing"
```

- [ ] **Step 5: Run migration + test**

```bash
cd backend && uv run alembic upgrade head && uv run pytest tests/test_trips_migration.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/*create_trips_tables*.py backend/tests/test_trips_migration.py
git commit -m "feat(trips): create eight trip tables with constraints + indexes"
```

---

### Task 1.3: Migration — SECURITY DEFINER membership functions + RLS

**Files:**
- Create: `backend/alembic/versions/ZZZZ_create_trips_rls.py`
- Test: extend `backend/tests/test_trips_migration.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && uv run alembic revision -m "create_trips_rls_policies"
```

- [ ] **Step 2: Define helper functions and policies**

```python
def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION is_trip_member(p_trip_id uuid, p_user_id uuid)
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM trip_attendees
                WHERE trip_id = p_trip_id AND user_id = p_user_id
            );
        $$;

        CREATE OR REPLACE FUNCTION is_active_trip_member(p_trip_id uuid, p_user_id uuid)
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM trip_attendees
                WHERE trip_id = p_trip_id
                  AND user_id = p_user_id
                  AND left_at IS NULL
            );
        $$;
    """)

    # Enable RLS on all trip_* tables
    for t in TRIP_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")

    # trips: SELECT for members; UPDATE/DELETE creator-only
    op.execute("""
        CREATE POLICY trips_select ON trips FOR SELECT
            USING (is_trip_member(id, auth.uid()));
        CREATE POLICY trips_insert ON trips FOR INSERT
            WITH CHECK (creator_user_id = auth.uid());
        CREATE POLICY trips_update ON trips FOR UPDATE
            USING (creator_user_id = auth.uid());
        CREATE POLICY trips_delete ON trips FOR DELETE
            USING (creator_user_id = auth.uid());
    """)

    # trip_attendees policies
    op.execute("""
        CREATE POLICY ta_select ON trip_attendees FOR SELECT
            USING (is_trip_member(trip_id, auth.uid()));
        CREATE POLICY ta_insert ON trip_attendees FOR INSERT
            WITH CHECK (is_active_trip_member(trip_id, auth.uid()));
        CREATE POLICY ta_update_self ON trip_attendees FOR UPDATE
            USING (user_id = auth.uid()
                   OR EXISTS (SELECT 1 FROM trips WHERE id = trip_id AND creator_user_id = auth.uid()));
        CREATE POLICY ta_delete_creator ON trip_attendees FOR DELETE
            USING (EXISTS (SELECT 1 FROM trips WHERE id = trip_id AND creator_user_id = auth.uid()));
    """)

    # trip_expenses, trip_expense_splits, trip_settlements: read=members, write=active members
    for t in ["trip_expenses", "trip_expense_splits", "trip_settlements"]:
        # splits don't have trip_id directly — join via expense
        if t == "trip_expense_splits":
            op.execute(f"""
                CREATE POLICY {t}_select ON {t} FOR SELECT
                    USING (EXISTS (
                        SELECT 1 FROM trip_expenses te
                        WHERE te.id = trip_expense_id AND is_trip_member(te.trip_id, auth.uid())
                    ));
                CREATE POLICY {t}_write ON {t} FOR ALL
                    USING (EXISTS (
                        SELECT 1 FROM trip_expenses te
                        WHERE te.id = trip_expense_id AND is_active_trip_member(te.trip_id, auth.uid())
                    ));
            """)
        else:
            op.execute(f"""
                CREATE POLICY {t}_select ON {t} FOR SELECT
                    USING (is_trip_member(trip_id, auth.uid()));
                CREATE POLICY {t}_write ON {t} FOR ALL
                    USING (is_active_trip_member(trip_id, auth.uid()));
            """)

    # Per-user dismissal tables
    for t in ["trip_suggestion_dismissals", "trip_settlement_dismissals"]:
        op.execute(f"""
            CREATE POLICY {t}_owner ON {t} FOR ALL
                USING (user_id = auth.uid());
        """)

    op.execute("""
        CREATE POLICY tbcc_select ON trip_base_currency_changes FOR SELECT
            USING (is_trip_member(trip_id, auth.uid()));
        CREATE POLICY tbcc_insert ON trip_base_currency_changes FOR INSERT
            WITH CHECK (EXISTS (SELECT 1 FROM trips WHERE id = trip_id AND creator_user_id = auth.uid()));
    """)
```

`downgrade()`: drop all policies, drop functions.

- [ ] **Step 3: Write RLS smoke test**

```python
@pytest.mark.asyncio
async def test_rls_enabled_on_trip_tables(db_session):
    for t in TRIP_TABLES:
        result = await db_session.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = :n").bindparams(n=t)
        )
        assert result.scalar() is True, f"RLS not enabled on {t}"
```

- [ ] **Step 4: Run + commit**

```bash
cd backend && uv run alembic upgrade head && uv run pytest tests/test_trips_migration.py -v
git add backend/alembic/versions/*create_trips_rls*.py backend/tests/test_trips_migration.py
git commit -m "feat(trips): RLS policies + is_(active_)trip_member helper functions"
```

---

### Task 1.4: Migration — mutual exclusivity triggers (trip_expenses ↔ transaction_splits)

**Files:**
- Create: `backend/alembic/versions/AAAA_trips_mutual_exclusivity_triggers.py`
- Test: `backend/tests/test_trips_mutual_exclusivity.py`

- [ ] **Step 1: Generate migration**

- [ ] **Step 2: Define both triggers**

```python
def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_split_if_trip_linked()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM trip_expenses
                WHERE transaction_id = NEW.transaction_id AND deleted_at IS NULL
            ) THEN
                RAISE EXCEPTION 'transaction is linked to a trip; dual-split is not supported in v1'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;

        CREATE TRIGGER trg_reject_split_if_trip_linked
            BEFORE INSERT OR UPDATE ON transaction_splits
            FOR EACH ROW EXECUTE FUNCTION reject_split_if_trip_linked();

        CREATE OR REPLACE FUNCTION reject_trip_link_if_split_exists()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.transaction_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM transaction_splits WHERE transaction_id = NEW.transaction_id
            ) THEN
                RAISE EXCEPTION 'transaction has household splits; cannot tag to a trip in v1'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;

        CREATE TRIGGER trg_reject_trip_link_if_split_exists
            BEFORE INSERT OR UPDATE OF transaction_id ON trip_expenses
            FOR EACH ROW EXECUTE FUNCTION reject_trip_link_if_split_exists();
    """)
```

- [ ] **Step 3: Write a *trigger-existence* smoke test** (cheap, doesn't depend on `make_trip` fixtures from Phase 2):

```python
# backend/tests/test_trips_migration.py
@pytest.mark.asyncio
async def test_mutual_exclusivity_triggers_exist(db_session):
    rows = (await db_session.execute(text(
        "SELECT tgname FROM pg_trigger "
        "WHERE tgname IN ('trg_reject_split_if_trip_linked', "
        "'trg_reject_trip_link_if_split_exists')"
    ))).all()
    assert len(rows) == 2
```

The full behavior test (insert + expect raise) ships in **Phase 3 Task 3.2** because it needs `make_trip` and `make_attendee` fixtures from Phase 2.

- [ ] **Step 4: Run + commit**

```bash
cd backend && uv run alembic upgrade head && uv run pytest tests/test_trips_migration.py -v
git add backend/alembic/versions/*mutual_exclusivity* backend/tests/test_trips_migration.py
git commit -m "feat(trips): mutual-exclusivity triggers between trip_expenses and transaction_splits"
```

---

## Phase 2 — Trip + attendee CRUD

### Task 2.0 (DISCOVERY): RLS test mechanism

Before writing any RLS test, find how the existing test suite authenticates as a specific user. RLS uses `auth.uid()`, which is NULL on a raw service-role `db_session` — silently denying everything.

- [ ] **Step 1:** Inspect `backend/tests/conftest.py` and any `backend/tests/helpers/` modules for an existing pattern:
  - Search: `grep -rn "auth.uid\|set_config.*auth\|jwt\|rls_client\|user_client" backend/tests/`
  - Look for fixtures that return an HTTP client or DB session bound to a specific user (likely setting `request.jwt.claims` via `SET LOCAL` or hitting endpoints with a real JWT).
- [ ] **Step 2:** Document the chosen mechanism in a short comment at the top of the new `backend/tests/test_trips_rls.py` file (e.g., "RLS scoping uses `<existing_fixture>` from `conftest.py:LXX`").
- [ ] **Step 3:** If no existing mechanism, add a fixture that issues a `SET LOCAL request.jwt.claims = '{"sub":"<user_id>"}'` on the session. Commit it as part of `backend/tests/conftest.py` (or `helpers/`).

This task is documentation/discovery only — no application code changes.

---

### Task 2.1: Module skeleton + SQLAlchemy models

**Files:**
- Create: `backend/modules/trips/__init__.py`
- Create: `backend/modules/trips/models.py`
- Test: `backend/tests/test_trips_models.py`

- [ ] **Step 1: Write models**

Mirror `backend/modules/households/models.py` style. Eight models matching the eight tables:

```python
# backend/modules/trips/models.py
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    creator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[date]
    end_date: Mapped[date]
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    invite_token_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    invite_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    attendees: Mapped[list["TripAttendee"]] = relationship(back_populates="trip", cascade="all, delete-orphan")
    expenses: Mapped[list["TripExpense"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class TripAttendee(Base):
    __tablename__ = "trip_attendees"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    trip: Mapped[Trip] = relationship(back_populates="attendees")
```

Continue with `TripExpense`, `TripExpenseSplit`, `TripSettlement`, `TripSuggestionDismissal`, `TripSettlementDismissal`, `TripBaseCurrencyChange` following spec §3.

- [ ] **Step 2: Write smoke test**

```python
@pytest.mark.asyncio
async def test_can_insert_and_query_trip(db_session, make_user):
    user = await make_user()
    trip = Trip(
        creator_user_id=user.id, name="Test", start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 7), base_currency="USD",
    )
    db_session.add(trip)
    await db_session.commit()
    fetched = (await db_session.execute(select(Trip).where(Trip.id == trip.id))).scalar_one()
    assert fetched.name == "Test"
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && uv run pytest tests/test_trips_models.py -v
git add backend/modules/trips/{__init__.py,models.py} backend/tests/test_trips_models.py
git commit -m "feat(trips): SQLAlchemy models for all trip tables"
```

---

### Task 2.2: Test fixtures (`make_trip`, `make_attendee`)

**Files:**
- Modify: `backend/tests/fixtures/__init__.py` (or wherever fixtures live; check `backend/tests/conftest.py`)

- [ ] **Step 1: Inspect existing fixture pattern** (e.g., `make_user`, `make_transaction`).

- [ ] **Step 2: Add fixtures** following the same pattern. `make_trip(creator, attendees=None, base_currency="USD")` creates a trip with creator auto-added as a Luka attendee. `make_attendee(trip, user=None, display_name=None)` adds an attendee.

- [ ] **Step 3: Commit**

```bash
git commit -m "test(trips): add make_trip and make_attendee fixtures"
```

---

### Task 2.3: Pydantic schemas (request + response models)

**Files:**
- Create: `backend/modules/trips/schemas.py`

- [ ] **Step 1: Write schemas**

Match spec §4 endpoint bodies exactly. Key types:

Imports: `from pydantic import BaseModel, EmailStr, Field, model_validator` and `from datetime import date` and `from uuid import UUID`.

```python
class CreateAttendeeInput(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one(self):
        if not (self.email or self.phone or self.display_name):
            raise ValueError("provide email, phone, or display_name")
        return self

class CreateTripRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date
    base_currency: str = Field(min_length=3, max_length=3)
    attendees: list[CreateAttendeeInput] = Field(default_factory=list)

class TripResponse(BaseModel):
    id: UUID
    name: str
    # ...

class TripDetailResponse(BaseModel):
    # full detail incl. attendees, expenses, settlements, balances
    ...
```

Add `SplitInput`, `CreateExpenseRequest`, `UpdateExpenseRequest`, `CreateSettlementRequest`, `BalancesResponse`, `SettleSuggestion`, etc.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(trips): pydantic schemas for trip endpoints"
```

---

### Task 2.4: Service layer — create trip + add attendees

**Files:**
- Create: `backend/modules/trips/service.py`
- Test: `backend/tests/test_trips_service.py`

- [ ] **Step 1: Write failing tests first (TDD)**

```python
@pytest.mark.asyncio
async def test_create_trip_adds_creator_as_attendee(db_session, make_user):
    user = await make_user()
    trip = await trips_service.create_trip(
        db_session, creator=user,
        payload=CreateTripRequest(
            name="Cartagena", start_date=date(2026,5,1), end_date=date(2026,5,7),
            base_currency="USD", attendees=[],
        ),
    )
    attendees = list((await db_session.execute(
        select(TripAttendee).where(TripAttendee.trip_id == trip.id)
    )).scalars())
    assert len(attendees) == 1
    assert attendees[0].user_id == user.id

@pytest.mark.asyncio
async def test_add_attendee_by_email_resolves_existing_user(db_session, make_user):
    creator = await make_user()
    other = await make_user(email="other@example.com")
    trip = await trips_service.create_trip(db_session, creator, basic_payload)
    a = await trips_service.add_attendee(db_session, trip, user=creator,
        payload=CreateAttendeeInput(email="other@example.com"))
    assert a.user_id == other.id
    assert a.display_name  # snapshot of name

@pytest.mark.asyncio
async def test_add_attendee_unknown_email_creates_external_stub(db_session, make_user):
    creator = await make_user()
    trip = await trips_service.create_trip(db_session, creator, basic_payload)
    a = await trips_service.add_attendee(db_session, trip, user=creator,
        payload=CreateAttendeeInput(email="ghost@nowhere.test", display_name="Ghost"))
    assert a.user_id is None
    assert a.display_name == "Ghost"
```

- [ ] **Step 2: Run tests — expect FAIL**

- [ ] **Step 3: Implement `create_trip`, `add_attendee`, `remove_attendee`, `list_trips`, `get_trip`**

Follow `backend/modules/households/service.py` patterns. Resolve email/phone via SELECT on `users`.

- [ ] **Step 4: Run + commit**

```bash
git commit -m "feat(trips): service layer — create trip, add/remove attendees"
```

---

### Task 2.5: Router — `POST /trips`, `GET /trips`, `GET /trips/{id}`, `PATCH/DELETE /trips/{id}`

**Files:**
- Create: `backend/modules/trips/router.py`
- Modify: `backend/main.py` (register router)
- Test: `backend/tests/test_trips_router.py`

- [ ] **Step 1: Add `feature_trips_enabled` gate dependency**

```python
async def require_trips_feature(user: User = Depends(get_current_user)) -> User:
    if not user.feature_trips_enabled:
        raise HTTPException(status_code=403, detail="feature_trips_enabled is off")
    return user
```

Apply to every trips endpoint.

- [ ] **Step 2: Write router tests** for happy paths + 403 when flag off + 403 on PATCH/DELETE by non-creator.

- [ ] **Step 3: Implement router** following `households/router.py`.

- [ ] **Step 4: Register in `main.py`**

```python
from modules.trips.router import router as trips_router
app.include_router(trips_router)
```

- [ ] **Step 5: Run + commit**

```bash
git commit -m "feat(trips): router for trip CRUD with feature flag gate"
```

---

### Task 2.6: Attendee endpoints + remove-with-balance check

**Files:**
- Modify: `backend/modules/trips/router.py`, `service.py`
- Test: extend `backend/tests/test_trips_router.py`, `test_trips_service.py`

- [ ] **Step 1: Tests for `POST /trips/{id}/attendees`, `DELETE /trips/{id}/attendees/{aid}`**

Cover: Luka match, external fallback, self-leave allowed, creator can remove others, non-creator cannot remove others, removal blocked when balance > $0.50 (test gets phase-4 balance computation; for now the service can stub-return 0 and the unsettled-balance test ships in Phase 4).

- [ ] **Step 2: Implement endpoints + service methods.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): attendee endpoints with creator-only remove + self-leave"
```

---

### Task 2.7: RLS integration test — non-member cannot read

**Files:**
- Create: `backend/tests/test_trips_rls.py`

- [ ] **Step 1: Write test using user-scoped Supabase client (matches existing RLS test pattern, e.g., `test_household_rls.py` if present, else `test_categories_router.py`).**

```python
@pytest.mark.asyncio
async def test_non_member_cannot_read_trip(rls_client_factory, make_user, make_trip):
    creator = await make_user(feature_trips_enabled=True)
    outsider = await make_user(feature_trips_enabled=True)
    trip = await make_trip(creator=creator)

    outsider_client = rls_client_factory(outsider)
    resp = await outsider_client.get(f"/trips/{trip.id}")
    assert resp.status_code in (403, 404)
```

- [ ] **Step 2: Add test for left member retains read access** (per spec §3.11).

- [ ] **Step 3: Commit**

```bash
git commit -m "test(trips): RLS membership boundaries"
```

---

## Phase 3 — Expenses + splits

### Task 3.1: Service `create_expense` with sign convention + split-sum normalization

**Files:**
- Modify: `backend/modules/trips/service.py`
- Test: `backend/tests/test_trip_expenses.py`

- [ ] **Step 1: Write tests for sign convention + equal-split rounding**

```python
@pytest.mark.asyncio
async def test_create_expense_from_negative_transaction_stores_positive(
    db_session, make_user, make_transaction, make_trip_with_attendees
):
    user, trip, attendees = await make_trip_with_attendees(n_attendees=4)
    txn = await make_transaction(user_id=user.id, amount=Decimal("-400.00"), currency="USD")
    expense = await trips_service.create_expense(
        db_session, trip=trip, user=user,
        payload=CreateExpenseRequest(
            payer_attendee_id=attendees[0].id, description="Dinner",
            amount=Decimal("400.00"), currency="USD",
            expense_date=date(2026,5,2), transaction_id=txn.id,
            splits=[SplitInput(attendee_id=a.id, share_type="equal") for a in attendees],
        ),
    )
    assert expense.amount == Decimal("400.00")  # positive
    splits = sorted([s.share_amount for s in expense.splits])
    assert splits == [Decimal("100.00")] * 4

@pytest.mark.asyncio
async def test_equal_split_with_rounding_payer_absorbs_remainder(...):
    # 100.00 / 3 = 33.33 each, payer gets 33.34 (absorbs 0.01)
```

- [ ] **Step 2: Implement** with the §3.10 rules: amount = `abs(amount)`, equal split = `floor(amount/n)` each + remainder to payer, custom_amount must sum to amount exactly (else raise), custom_percent normalized to amounts and any residual to payer.

- [ ] **Step 3: Run + commit**

```bash
git commit -m "feat(trips): create_expense with sign + split-sum + equal-rounding rules"
```

---

### Task 3.2: Mutual-exclusivity surfacing as 409

**Files:**
- Modify: `backend/modules/trips/router.py`, `service.py`

- [ ] **Step 1: Write test** — joint-account transaction (with `transaction_splits`) tagged to trip → 409 with code `joint_account_dual_split_not_supported`.

```python
@pytest.mark.asyncio
async def test_tagging_joint_account_transaction_returns_409(...):
    # set up txn with transaction_splits row
    resp = await client.post(f"/trips/{trip.id}/expenses", json={...})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "joint_account_dual_split_not_supported"
```

- [ ] **Step 2: Catch the trigger error in the service layer** (Postgres error code `23514` from our trigger) and re-raise as `HTTPException(409, detail={"code": "joint_account_dual_split_not_supported", "message": "..."})`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): surface mutual-exclusivity trigger as 409 with code"
```

---

### Task 3.3: PATCH expense with `If-Match` version + DELETE soft-delete

**Files:**
- Modify: `service.py`, `router.py`
- Test: `test_trip_expenses.py`

- [ ] **Step 1: Tests**

- 200 on matching `If-Match: <version>` header, version increments
- 409 when stale `If-Match`
- DELETE sets `deleted_at`, balances exclude deleted

- [ ] **Step 2: Implement** with `Header(...)` dependency for `If-Match`, parse to int, compare to row version, increment in same query.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): PATCH/DELETE expense with optimistic concurrency"
```

---

## Phase 4 — Balance computation + settlements

### Task 4.0 (DISCOVERY): FX service interface

- [ ] **Step 1:** Locate the FX service used by Plaid + email parser:
  - `grep -rn "fx_rate\|exchange_rate\|to_base_currency\|currency.*conversion" backend/modules/`
  - Likely under `backend/modules/currencies/` (per project memory). Identify the function signature for "given currency A → currency B at date D, return rate."
- [ ] **Step 2:** Document the exact import path and signature at the top of `backend/modules/trips/balances.py` (write a docstring comment) before writing the FX integration code in Task 4.1.
- [ ] **Step 3:** If the existing service exposes only a synchronous interface or only "today's rate" without historical, flag it back to the user — the spec assumes "rate at expense date" is available. Don't proceed without resolution.

---

### Task 4.1: FX service integration for `fx_rate_to_base`

**Files:**
- Modify: `backend/modules/trips/service.py`
- Reuse: existing FX module (check `backend/modules/currencies/`)

- [ ] **Step 1: Write test**

```python
@pytest.mark.asyncio
async def test_fx_rate_stored_at_creation_when_currency_differs(...):
    # trip base USD, expense currency MXN → fx_rate_to_base != None and matches today's MXN→USD
```

- [ ] **Step 2: In `create_expense`, when `currency != base_currency`:**
  - If `transaction_id` provided, copy stored FX from the transaction.
  - Else fetch rate via FX service, store on row.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): FX rate frozen at expense creation"
```

---

### Task 4.2: Balance computation function

**Files:**
- Create: `backend/modules/trips/balances.py`
- Test: `backend/tests/test_trip_balances.py`

- [ ] **Step 1: Write tests**

Cover: 2-attendee single-currency, 3-attendee mixed currency, settlement reduces balance, deleted expenses excluded.

- [ ] **Step 2: Implement `compute_balances(trip_id, db) -> dict[attendee_id, Decimal]`** per spec §5.1.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): balance computation in trip base currency"
```

---

### Task 4.3: Smart-settle plan + property-based test

**Files:**
- Modify: `backend/modules/trips/balances.py`
- Test: `backend/tests/test_trip_balances.py`

- [ ] **Step 1: Property-based tests using Hypothesis**

```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    nets=st.lists(
        st.decimals(min_value=Decimal("-10000"), max_value=Decimal("10000"), places=2),
        min_size=2, max_size=8,
    ).filter(lambda lst: sum(lst) == 0)
)
def test_smart_settle_invariants(nets):
    plan = smart_settle(dict(enumerate(nets)))
    # 1) sum of transfers = 0 (per pair)
    # 2) len(plan) <= n - 1
    # 3) applying plan zeroes all nets within 0.01
    ...
```

- [ ] **Step 2: Implement** — sort, while any |net| > 0.01: pair max creditor with max debtor, emit `min(|c|, |d|)`, reduce, remove zeros.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): smart-settle plan with property-based invariants"
```

---

### Task 4.4: Settlement endpoint + balances in `GET /trips/{id}`

**Files:**
- Modify: `service.py`, `router.py`
- Test: `test_trip_router.py`, `test_trip_balances.py`

- [ ] **Step 1: Tests**

- POST settlement requires `from != to`, `amount > 0` (validates DB CHECK).
- `GET /trips/{id}` includes `balances` and `settle_suggestions` keys.
- `GET /trips/{id}/settle-suggestions` returns the plan.

- [ ] **Step 2: Implement** `create_settlement`, `get_settle_plan`, expand `get_trip_detail` to include balances.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): settlements + balances in trip detail"
```

---

### Task 4.5: Base-currency change with cross-rate re-anchor

**Files:**
- Modify: `service.py`, `router.py`
- Test: `backend/tests/test_trip_base_currency_change.py`

- [ ] **Step 1: Test — switching base currency preserves zeroed balances**

```python
@pytest.mark.asyncio
async def test_base_currency_change_preserves_zeroed_balance(...):
    # Create trip USD, expenses + settlement that zero balances exactly
    # PATCH base_currency to MXN
    # Assert balances still zero (within 0.01)
    # Assert trip_base_currency_changes row created
```

- [ ] **Step 2: Implement** — fetch cross-rate via FX service, multiply every `fx_rate_to_base` on `trip_expenses` and `trip_settlements`, insert audit row, all in one transaction.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): base-currency change uses cross-rate re-anchor"
```

---

### Task 4.6: Force-remove with write-off

**Files:**
- Modify: `service.py`, `router.py`
- Test: `test_trip_router.py`

- [ ] **Step 1: Test** — creator force-removes attendee with $0.20 net; service inserts zeroing settlement with `write_off=true`; attendee `left_at` set.

- [ ] **Step 2: Implement `POST /trips/{id}/attendees/{aid}/force-remove`** — creator-only, writes settlement that zeroes the net (direction = whichever zeroes), sets `left_at`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): force-remove attendee with write-off settlement"
```

---

## Phase 5 — Invite link

### Task 5.0 (DISCOVERY): Rate-limit middleware

- [ ] **Step 1:** Check for existing rate-limit infrastructure:
  - `grep -rn "rate.?limit\|slowapi\|RateLimiter" backend/`
  - Inspect FastAPI middleware setup in `backend/main.py`.
- [ ] **Step 2:** Spec §4.3 requires **two scopes**: per-IP (10/min) and per-user (30/hour).
  - If `slowapi` is already wired, confirm it supports user-scoped keys (it does via custom `key_func`). Use it.
  - If nothing is wired, install `slowapi` and add it as middleware in `backend/main.py`. Define two limiters: `Limiter(key_func=get_remote_address)` for IP, and `Limiter(key_func=lambda req: req.state.user.id)` for user.
- [ ] **Step 3:** Document the chosen approach at the top of `backend/modules/trips/router.py` (single line comment) so Task 5.2 has a concrete reference.

---

### Task 5.1: Token generation + hashed storage

**Files:**
- Modify: `backend/modules/trips/service.py`, `models.py` (none — column exists)
- Test: `backend/tests/test_trip_invite_security.py`

- [ ] **Step 1: Tests**

- Generated token is ≥32 chars (urlsafe-base64 of 32 random bytes).
- Stored value in `invite_token_hash` is `sha256(token).hexdigest()`, never the raw token.
- Lookup by raw token works; lookup by anything else fails.

```python
def test_token_stored_as_sha256(...):
    token = await trips_service.generate_invite_link(db_session, trip, user=creator)
    fetched_trip = ...
    import hashlib
    assert fetched_trip.invite_token_hash == hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 2: Implement `generate_invite_link(trip, user)` (creator-only), `revoke_invite_link(trip, user)`, `lookup_trip_by_token(token, db)`.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): invite-token generate/rotate/revoke with SHA-256 storage"
```

---

### Task 5.2: Endpoints + rate-limiting

**Files:**
- Modify: `router.py`
- Reuse: existing rate-limit middleware (check `backend/core/` or middleware path; if absent, use `slowapi`).

- [ ] **Step 1: Tests for `POST /trips/{id}/invite-link` (creator-only), `DELETE`, `POST /trips/join/{token}`, `GET /trips/preview/{token}`.**

- [ ] **Step 2: Tests for rate-limit** — 11th call to `/join/{token}` within a minute returns 429.

- [ ] **Step 3: Implement endpoints, attach rate-limit decorators.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(trips): invite endpoints with rate-limit"
```

---

### Task 5.3: Join landing data endpoint

- [ ] **Step 1: Test** — `GET /trips/preview/{token}` returns trip name + dates + attendee count, requires auth.

- [ ] **Step 2: Implement.**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): preview endpoint for invite landing"
```

---

## Phase 6 — Suggestions inbox + settlement auto-detect

### Task 6.0 (DISCOVERY): Post-insert hook surface + notifications module

Two integrations to locate before any code:

- [ ] **Step 1: Find the transactions post-insert hook surface.** Spec §4.7 says "hooked into existing post-insert pipeline" but doesn't name a file. Search:
  - `grep -rn "after_insert\|on_transaction_inserted\|post_insert\|transaction_created" backend/modules/transactions/ backend/jobs/`
  - Likely candidates: a SQLAlchemy event listener on `Transaction`, an ARQ job dispatched after transaction commits, or an explicit "post-process transaction" function called by the email parser + Plaid sync. Document the exact file:line where new transactions are emitted.
- [ ] **Step 2: Find the notifications module.**
  - `grep -rn "notification\|Notification" backend/modules/notifications/`
  - Identify the function for "create notification of type X for user Y with payload P" and the schema for `notifications` rows. Confirm a new type `trip_settlement_suggestion` is just a string value (not an enum that needs a migration). If it's an enum, add a migration to extend it as a substep of Task 6.2.
- [ ] **Step 3:** Document both findings at the top of `backend/modules/trips/auto_detect.py` (file created in Task 6.2). Don't proceed without resolution.

---

### Task 6.1: Suggestions inbox query + endpoint

**Files:**
- Modify: `service.py`, `router.py`
- Test: `backend/tests/test_trip_suggestions.py`

- [ ] **Step 1: Tests**

- In-window expense surfaces.
- Subscription-linked transaction excluded.
- Transfer transaction excluded.
- Already-linked transaction excluded.
- Dismissed transaction excluded.
- Per-user isolation (other Luka attendee sees their own).
- **Undismiss restores visibility:** `DELETE /trips/{id}/suggested-transactions/{txn_id}/dismiss` removes the dismissal row; subsequent GET includes the transaction again.

- [ ] **Step 2: Implement `GET /trips/{id}/suggested-transactions`**, `POST/DELETE …/dismiss`.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): suggestions inbox with dismissal"
```

---

### Task 6.2: Settlement auto-detect post-insert hook

**Files:**
- Modify: existing post-insert pipeline on `transactions` (find via `grep -r "post_insert" backend/modules/transactions`); add hook
- Create: `backend/modules/trips/auto_detect.py`
- Test: `backend/tests/test_trip_settlement_autodetect.py`

- [ ] **Step 1: Tests**

- Zelle to a Luka attendee with $80 outstanding, transaction $80 → notification fires.
- $200 → no notification (outside tolerance).
- External attendee → no match.
- Dismissed → suppressed.

- [ ] **Step 2: Implement `try_match_settlement(transaction, db)`** — runs after transaction insert; iterates user's active trips with non-zero balances; emits `notifications` row of type `trip_settlement_suggestion` on match.

- [ ] **Step 3: Wire into post-insert pipeline.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(trips): settlement auto-detect from Zelle/Venmo transactions"
```

---

### Task 6.3: Confirm/dismiss settlement suggestion endpoints

- [ ] **Step 1: Tests + implement** `POST /trips/settlement-suggestions/confirm` (creates settlement with `transaction_id`), `POST /trips/settlement-suggestions/dismiss`.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(trips): confirm/dismiss settlement suggestions"
```

---

### Task 6.4: Budget integration test

**Files:**
- Test: `backend/tests/test_trip_budget_integration.py`

- [ ] **Step 1: Test** — transaction tagged to trip with split → user's category total reflects only their `share_amount`, not the full transaction amount.

- [ ] **Step 2: If existing budget aggregator needs update**, modify it to consider `trip_expense_splits` for trip-linked transactions (mirroring the existing `transaction_splits` path).

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(trips): budget aggregator respects trip_expense_splits"
```

---

## Phase 7 — Frontend section

> No frontend test infra in v1. Verify each phase with `/browser-use` golden-path scripts (described in spec §9.2). Commit after each task; ship behind the per-user feature flag.

### Task 7.1: Sidebar/bottom-nav entry + route stub

**Files:**
- Modify: `frontend/app/(dashboard)/layout.tsx` (or wherever the nav lives — search for "Subscriptions" / "Suscripciones")
- Create: `frontend/app/(dashboard)/viajes/page.tsx` (empty stub)

- [ ] **Step 1: Add `Viajes` between Suscripciones and Hogar in sidebar + bottom nav, gated by user's `feature_trips_enabled` flag (read from existing user-context provider or fetch from `/users/me`).**

- [ ] **Step 2: Stub page renders "Viajes coming soon".**

- [ ] **Step 3: Verify via `/browser-use` — flag-on user sees nav, flag-off does not.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(trips): nav entry behind feature flag"
```

---

### Task 7.2: API client + TanStack Query hooks

**Files:**
- Create: `frontend/lib/api/trips.ts`
- Create: `frontend/lib/hooks/useTrips.ts`, `useTrip.ts`

- [ ] **Step 0: 403 handling.** All `useTrips*` hooks must treat 403 from the backend (feature flag off) as "not enabled" — render the section as if the user has no access rather than crashing. Centralize this in the fetch wrapper.

- [ ] **Step 1: Write typed fetch wrappers and React Query hooks for every endpoint** (`useTrips`, `useTrip(id)`, `useCreateTrip`, `useUpdateTrip`, `useArchiveTrip`, `useAddAttendee`, `useRemoveAttendee`, `useCreateExpense`, `useUpdateExpense`, `useDeleteExpense`, `useCreateSettlement`, `useSettleSuggestions`, `useSuggestedTransactions`, `useDismissSuggestion`, `useGenerateInviteLink`, `useJoinTrip`).**

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(trips): API client + TanStack Query hooks"
```

---

### Task 7.3: Trip list page

**Files:**
- Modify: `frontend/app/(dashboard)/viajes/page.tsx`
- Create: `frontend/app/(dashboard)/viajes/components/TripCard.tsx`, `TripList.tsx`, `EmptyState.tsx`, `NewTripDialog.tsx`

- [ ] **Step 1: Render Active / Próximos / Pasados sections**, per-card net balance, "+ Nuevo viaje" CTA.

- [ ] **Step 2: NewTripDialog** with name / dates / base_currency / initial attendees (typeahead + name-stub fallback).

- [ ] **Step 3: Verify via `/browser-use` — create trip, see it on list.**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(trips): list page with create dialog"
```

---

### Task 7.4: Trip detail — Resumen + Gastos tabs

**Files:**
- Create: `frontend/app/(dashboard)/viajes/[id]/page.tsx`
- Create: `frontend/app/(dashboard)/viajes/components/TripHeader.tsx`, `ResumenTab.tsx`, `GastosTab.tsx`, `ExpenseRow.tsx`, `AddExpenseSheet.tsx`

- [ ] **Step 1: TripHeader with name/dates/base currency.** Tabs: Resumen | Gastos | Saldos | Asistentes (Saldos + Asistentes stubbed in next task).

- [ ] **Step 2: AddExpenseSheet** — bottom sheet with all spec §6.5 fields: payer, amount + currency, date, vincular-a-transacción picker (typeahead against suggested transactions), split-mode toggle, attendee chips, per-attendee inputs in custom modes with sum validation.

- [ ] **Step 3: ExpenseRow** with description, payer avatar, amount in base currency, original currency in subtext, category chip.

- [ ] **Step 4: Verify** — add expense (yours, real-tx-backed), add expense (manual stub for external), see both in Gastos.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(trips): trip detail Resumen + Gastos tabs + add expense sheet"
```

---

### Task 7.5: Saldos tab + settle suggestions

**Files:**
- Create: `frontend/app/(dashboard)/viajes/components/SaldosTab.tsx`, `BalanceGrid.tsx`, `SettleSuggestionList.tsx`, `MarkSettledDialog.tsx`

- [ ] **Step 1: BalanceGrid with per-attendee net (color-coded).**

- [ ] **Step 2: SettleSuggestionList — minimum-transactions plan with `Marcar como pagado` per row.**

- [ ] **Step 3: Auto-detected suggestions banner** — read from notifications, show `Auto-detectado` chip.

- [ ] **Step 4: Verify** — settle one pair manually, see balance update; trigger an auto-detect by seeding a Zelle transaction in the test DB and confirm the chip appears.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(trips): Saldos tab with smart-settle plan and auto-detect"
```

---

### Task 7.6: Asistentes tab + invite link UI

**Files:**
- Create: `frontend/app/(dashboard)/viajes/components/AsistentesTab.tsx`, `AttendeeManager.tsx`, `ShareInviteDialog.tsx`
- Create: `frontend/app/(dashboard)/viajes/join/[token]/page.tsx`

- [ ] **Step 1: AttendeeManager** — list, add (typeahead + name-stub), remove (creator-only), self-leave.

- [ ] **Step 2: ShareInviteDialog** — generate link, copy-to-clipboard, rotate, revoke (creator-only buttons hidden otherwise).

- [ ] **Step 3: Join landing page** at `/viajes/join/[token]` — calls `/trips/preview/{token}`, shows trip name + dates + attendee count, "Unirme" button → `POST /trips/join/{token}` → redirects to `/viajes/[id]`.

- [ ] **Step 4: Verify on two accounts** — generate link on Account A, paste in Account B, accept, see Account B as new attendee.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(trips): Asistentes tab + invite link share + join landing"
```

---

### Task 7.7: Suggestions banner + inline `+ Agregar a Trip` chips on `/transactions`

**Files:**
- Modify: trip detail (banner) + `/transactions` rows (chip)
- Create: `frontend/app/(dashboard)/viajes/components/TripSuggestionsBanner.tsx`

- [ ] **Step 1: Banner on trip detail Resumen + Gastos tabs:** "N transacciones durante este viaje no agregadas". Expands to list with three actions per row.

- [ ] **Step 2: On `/transactions` rows in any active trip date window, render `+ Agregar a [Trip]` chip; click opens AddExpenseSheet pre-filled.**

- [ ] **Step 3: Verify** — create a transaction in the trip window, see banner + chip, accept via banner, confirm expense created.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(trips): suggestions banner + inline chips on transactions"
```

---

### Task 7.8: Final browser walkthrough + docs update

- [ ] **Step 1: Run the full `/browser-use` golden path from spec §9.2.**

- [ ] **Step 2: Update `README.md`, `ARCHITECTURE.md`, `NEXT-STEPS.md`, `CLAUDE.md`** per spec §10.

- [ ] **Step 3: Enable `feature_trips_enabled = true` for founders only** (manual SQL update on prod / use Supabase dashboard).

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(trips): update README, ARCHITECTURE, NEXT-STEPS, CLAUDE.md"
```

---

## Verification checklist before flipping flag for beta

- [ ] All backend tests pass (`uv run pytest backend/tests/ -v`).
- [ ] Coverage on `backend/modules/trips/` ≥ 90% (`uv run pytest --cov=modules/trips`). If `pytest-cov` isn't installed, add it: `uv add --dev pytest-cov`.
- [ ] Property-based balance test runs ≥ 200 examples without failure.
- [ ] RLS test confirms non-member 403/404.
- [ ] Joint-account 409 surfaces in browser as friendly Spanish copy.
- [ ] Smart-settle plan shows ≤ n−1 transfers in dogfood trip.
- [ ] Auto-detect fires on a real Zelle/Venmo transaction in dogfood.
- [ ] Invite link generated → joined on a second account → both accounts see each other in Asistentes.
- [ ] Trip-tagged transaction appears in user's category totals at split share, not full amount.
- [ ] No regressions in `transactions`, `households`, `budgets`, `subscriptions` test suites.

---

## Out of scope (v2 backlog — see NEXT-STEPS.md after merge)

- WhatsApp invites, expense actions, settlement confirmations
- Native mobile contact-picker integration
- Itemized splits within a single transaction
- Recurring trips
- Receipt photo attachments
- CSV / PDF export
- External-attendee → real Luka user merge
- Dual-split (household + trip on same transaction)
- Per-user currency display preference
- Frontend test infrastructure (Vitest + RTL + Playwright) — separate ~2-day initiative
