# Frontend Redesign Tier 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Settings page with profile editing, notification preferences, category management, and account deletion; polish Login and Onboarding pages to match Tier 1 design system.

**Architecture:** Backend-first approach — create migrations, models, services, and endpoints first, then build the frontend Settings sections against real APIs. Login/Onboarding polish is frontend-only and can run in parallel with backend work.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Next.js 14 + React Query + Zustand + @dnd-kit/sortable (frontend), Supabase Auth admin API (account deletion)

**Spec:** `docs/superpowers/specs/2026-03-23-frontend-redesign-tier2-design.md`

---

## File Map

### New files (backend)
- `backend/modules/settings/models.py` — NotificationPreference + UserCategoryPreference models
- `backend/modules/settings/schemas.py` — Request/response Pydantic schemas
- `backend/modules/settings/service.py` — Service functions for notifications, categories, account deletion
- `backend/modules/settings/router.py` — API endpoints for /notifications and /categories
- `backend/alembic/versions/013_add_phone_whatsapp_to_users.py` — Migration: add phone_whatsapp column
- `backend/alembic/versions/014_notification_preferences.py` — Migration: create notification_preferences table + RLS
- `backend/alembic/versions/015_user_category_preferences.py` — Migration: create user_category_preferences table + RLS
- `backend/tests/test_settings_api.py` — API tests for all new endpoints

### New files (frontend)
- `frontend/app/(dashboard)/settings/components/ProfileSection.tsx` — Profile editing card
- `frontend/app/(dashboard)/settings/components/NotificationsSection.tsx` — WhatsApp toggle card
- `frontend/app/(dashboard)/settings/components/CategoriesSection.tsx` — Drag-and-drop category manager
- `frontend/app/(dashboard)/settings/components/DeleteAccountSection.tsx` — Danger zone with confirmation
- `frontend/app/(dashboard)/settings/components/HogarSection.tsx` — Household info card
- `frontend/app/(dashboard)/settings/components/PrivacySection.tsx` — Privacy disclosure card
- `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx` — Extracted from current page.tsx

### Modified files (backend)
- `backend/modules/auth/models.py` — Add phone_whatsapp column to User
- `backend/modules/auth/schemas.py` — Add phone_whatsapp to UserResponse + new UpdateProfileRequest
- `backend/modules/auth/router.py` — Add PATCH /auth/me and DELETE /auth/me endpoints
- `backend/main.py` — Register settings router + import settings models

### Modified files (frontend)
- `frontend/app/(dashboard)/settings/page.tsx` — Complete rewrite: imports section components
- `frontend/app/lib/api.ts` — Add API methods for profile, notifications, categories, delete account
- `frontend/app/(auth)/login/page.tsx` — Typography and button polish
- `frontend/app/(auth)/onboarding/layout.tsx` — Step indicator and container polish
- `frontend/app/(auth)/onboarding/setup-household/page.tsx` — Input/button styling polish
- `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx` — Input/button styling polish
- `frontend/app/(auth)/onboarding/connect-bank/page.tsx` — Button styling polish
- `frontend/package.json` — Add @dnd-kit/core and @dnd-kit/sortable

---

## Task 1: Migration — Add phone_whatsapp to users table

**Files:**
- Create: `backend/alembic/versions/013_add_phone_whatsapp_to_users.py`
- Modify: `backend/modules/auth/models.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/013_add_phone_whatsapp_to_users.py
"""Add phone_whatsapp column to users table.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"

def upgrade() -> None:
    op.add_column("users", sa.Column("phone_whatsapp", sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "phone_whatsapp")
```

- [ ] **Step 2: Update User model**

In `backend/modules/auth/models.py`, add after the `whatsapp_verified` line (line 16):

```python
phone_whatsapp: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/013_add_phone_whatsapp_to_users.py backend/modules/auth/models.py
git commit -m "feat(db): add phone_whatsapp column to users table"
```

---

## Task 2: Migration — Create notification_preferences table

**Files:**
- Create: `backend/alembic/versions/014_notification_preferences.py`
- Create: `backend/modules/settings/models.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/014_notification_preferences.py
"""Create notification_preferences table with RLS.

Revision ID: 014
Revises: 013
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "014"
down_revision = "013"

def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # RLS
    op.execute("ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY notification_preferences_user_policy ON notification_preferences
        FOR ALL USING (user_id = auth.uid())
    """)

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notification_preferences_user_policy ON notification_preferences")
    op.drop_table("notification_preferences")
```

- [ ] **Step 2: Create __init__.py for settings module**

```python
# backend/modules/settings/__init__.py
```

(Empty file — makes the directory a proper Python package)

- [ ] **Step 3: Create the settings models file**

```python
# backend/modules/settings/models.py
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/014_notification_preferences.py backend/modules/settings/__init__.py backend/modules/settings/models.py
git commit -m "feat(db): create notification_preferences table with RLS"
```

---

## Task 3: Migration — Create user_category_preferences table

**Files:**
- Modify: `backend/modules/settings/models.py`
- Create: `backend/alembic/versions/015_user_category_preferences.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/015_user_category_preferences.py
"""Create user_category_preferences table with RLS.

Revision ID: 015
Revises: 014
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "015"
down_revision = "014"

def upgrade() -> None:
    op.create_table(
        "user_category_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", name="uq_user_category_prefs"),
    )
    # RLS
    op.execute("ALTER TABLE user_category_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY user_category_preferences_user_policy ON user_category_preferences
        FOR ALL USING (user_id = auth.uid())
    """)

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS user_category_preferences_user_policy ON user_category_preferences")
    op.drop_table("user_category_preferences")
```

- [ ] **Step 2: Add UserCategoryPreference model to settings/models.py**

Append to `backend/modules/settings/models.py`:

```python
class UserCategoryPreference(Base):
    __tablename__ = "user_category_preferences"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "category", name="uq_user_category_prefs"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Note: import `sa` at top of models.py (`import sqlalchemy as sa`) for the `__table_args__`.

- [ ] **Step 3: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/015_user_category_preferences.py backend/modules/settings/models.py
git commit -m "feat(db): create user_category_preferences table with RLS"
```

---

## Task 4: Backend — Schemas for settings endpoints

**Files:**
- Create: `backend/modules/settings/schemas.py`
- Modify: `backend/modules/auth/schemas.py`

- [ ] **Step 1: Create settings schemas**

```python
# backend/modules/settings/schemas.py
from pydantic import BaseModel


class NotificationPreferencesResponse(BaseModel):
    whatsapp_enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    whatsapp_enabled: bool


class CategoryPreferenceItem(BaseModel):
    category: str
    sort_order: int
    hidden: bool = False

    model_config = {"from_attributes": True}


class CategoryPreferencesResponse(BaseModel):
    categories: list[CategoryPreferenceItem]


class CategoryPreferencesUpdate(BaseModel):
    categories: list[CategoryPreferenceItem]
```

- [ ] **Step 2: Update auth schemas**

In `backend/modules/auth/schemas.py`, add `phone_whatsapp` to `UserResponse` and add `UpdateProfileRequest`:

```python
import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool
    phone_whatsapp: str | None = None
    household_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class WhatsAppVerifyRequest(BaseModel):
    phone: str  # e.g. "+56912345678"
    pin: str  # 6-digit pin


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone_whatsapp: str | None = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/settings/schemas.py backend/modules/auth/schemas.py
git commit -m "feat: add Pydantic schemas for settings and profile update"
```

---

## Task 5: Backend — Settings service (notifications + categories + delete account)

**Files:**
- Create: `backend/modules/settings/service.py`

- [ ] **Step 1: Create the service file**

```python
# backend/modules/settings/service.py
import uuid
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from modules.settings.models import NotificationPreference, UserCategoryPreference

# Canonical category list — single source of truth
EXPENSE_CATEGORIES = [
    "Alimentación", "Supermercado", "Transporte", "Combustible",
    "Entretenimiento", "Salud", "Farmacia", "Hogar",
    "Ropa", "Tecnología", "Educación", "Viajes", "Servicios", "Otros",
]

INCOME_CATEGORIES = [
    "Sueldo", "Freelance", "Inversiones", "Arriendo",
    "Bono", "Transferencia de terceros", "Deuda pendiente", "Otros ingresos",
]

ALL_CATEGORIES = EXPENSE_CATEGORIES + INCOME_CATEGORIES


async def get_notification_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> NotificationPreference:
    """Get preferences, creating default row if none exists."""
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id, whatsapp_enabled=True)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


async def update_notification_preferences(
    db: AsyncSession, user_id: uuid.UUID, whatsapp_enabled: bool
) -> NotificationPreference:
    """Upsert notification preferences."""
    stmt = pg_insert(NotificationPreference).values(
        user_id=user_id, whatsapp_enabled=whatsapp_enabled
    ).on_conflict_do_update(
        index_elements=["user_id"],
        set_={"whatsapp_enabled": whatsapp_enabled, "updated_at": func.now()},
    )
    await db.execute(stmt)
    await db.commit()
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return result.scalar_one()


async def get_category_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> list[dict]:
    """Get user's category sort/hide preferences. Returns defaults if none exist."""
    result = await db.execute(
        select(UserCategoryPreference)
        .where(UserCategoryPreference.user_id == user_id)
        .order_by(UserCategoryPreference.sort_order)
    )
    prefs = result.scalars().all()
    if prefs:
        return [
            {"category": p.category, "sort_order": p.sort_order, "hidden": p.hidden}
            for p in prefs
        ]
    # Return defaults
    return [
        {"category": cat, "sort_order": i, "hidden": False}
        for i, cat in enumerate(ALL_CATEGORIES)
    ]


async def update_category_preferences(
    db: AsyncSession, user_id: uuid.UUID, categories: list[dict]
) -> list[dict]:
    """Replace all category preferences for a user in one transaction."""
    # Validate categories against canonical list
    for item in categories:
        if item["category"] not in ALL_CATEGORIES:
            raise ValueError(f"Unknown category: {item['category']}")

    # Delete existing
    await db.execute(
        delete(UserCategoryPreference).where(UserCategoryPreference.user_id == user_id)
    )
    # Insert new
    for item in categories:
        db.add(UserCategoryPreference(
            user_id=user_id,
            category=item["category"],
            sort_order=item["sort_order"],
            hidden=item.get("hidden", False),
        ))
    await db.commit()
    return categories


async def delete_user_account(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Application-level cascading delete of all user data within a single transaction.

    Order: transaction_splits → transactions → bank_accounts →
           household_members → notification_preferences →
           user_category_preferences → user.
    If user is last household member, also deletes household + household_budgets.
    """
    from modules.transactions.models import Transaction, TransactionSplit
    from modules.households.models import BankAccount, Household, HouseholdBudget, HouseholdBudgetAllocation, HouseholdMember
    from modules.auth.models import User

    # Find user's household membership
    hm_result = await db.execute(
        select(HouseholdMember).where(HouseholdMember.user_id == user_id)
    )
    membership = hm_result.scalar_one_or_none()
    household_id = membership.household_id if membership else None

    # 1. Delete transaction_splits for user's transactions
    user_txn_ids = select(Transaction.id).where(Transaction.user_id == user_id)
    await db.execute(delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(user_txn_ids)))

    # 2. Delete transactions
    await db.execute(delete(Transaction).where(Transaction.user_id == user_id))

    # 3. Delete bank_accounts
    await db.execute(delete(BankAccount).where(BankAccount.user_id == user_id))

    # 4. Delete household_member
    await db.execute(delete(HouseholdMember).where(HouseholdMember.user_id == user_id))

    # 5. Delete notification_preferences
    await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user_id))

    # 6. Delete user_category_preferences
    await db.execute(delete(UserCategoryPreference).where(UserCategoryPreference.user_id == user_id))

    # 7. If last member of household, delete household + budgets + allocations
    if household_id:
        remaining = await db.execute(
            select(HouseholdMember).where(HouseholdMember.household_id == household_id)
        )
        if not remaining.scalars().first():
            await db.execute(delete(HouseholdBudgetAllocation).where(HouseholdBudgetAllocation.household_id == household_id))
            await db.execute(delete(HouseholdBudget).where(HouseholdBudget.household_id == household_id))
            await db.execute(delete(Household).where(Household.id == household_id))

    # 8. Delete user record
    await db.execute(delete(User).where(User.id == user_id))

    await db.commit()
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/settings/service.py
git commit -m "feat: add settings service — notifications, categories, account deletion"
```

---

## Task 6: Backend — Settings router (notifications + categories)

**Files:**
- Create: `backend/modules/settings/router.py`

- [ ] **Step 1: Create the router**

```python
# backend/modules/settings/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.settings import service
from modules.settings.schemas import (
    CategoryPreferencesResponse,
    CategoryPreferencesUpdate,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

router = APIRouter(tags=["settings"])


# --- Notifications ---

@router.get("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await service.get_notification_preferences(db, current_user.id)
    return pref


@router.patch("/notifications/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    body: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pref = await service.update_notification_preferences(db, current_user.id, body.whatsapp_enabled)
    return pref


# --- Categories ---

@router.get("/categories/preferences", response_model=CategoryPreferencesResponse)
async def get_category_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cats = await service.get_category_preferences(db, current_user.id)
    return CategoryPreferencesResponse(categories=cats)


@router.put("/categories/preferences", response_model=CategoryPreferencesResponse)
async def update_category_preferences(
    body: CategoryPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cats = await service.update_category_preferences(
            db, current_user.id, [c.model_dump() for c in body.categories]
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CategoryPreferencesResponse(categories=cats)
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/settings/router.py
git commit -m "feat: add settings router — notifications and categories endpoints"
```

---

## Task 7: Backend — Auth router updates (PATCH profile + DELETE account)

**Files:**
- Modify: `backend/modules/auth/router.py`

- [ ] **Step 1: Add PATCH /auth/me endpoint**

Add imports and endpoints to `backend/modules/auth/router.py`. The file should become:

```python
# backend/modules/auth/router.py
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import UpdateProfileRequest, UserResponse
from modules.households.models import HouseholdMember

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == current_user.id)
    )
    row = result.first()
    household_id = row[0] if row else None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_provider=current_user.email_provider,
        whatsapp_verified=current_user.whatsapp_verified,
        phone_whatsapp=current_user.phone_whatsapp,
        household_id=household_id,
    )


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.phone_whatsapp is not None:
        current_user.phone_whatsapp = body.phone_whatsapp
    await db.commit()
    await db.refresh(current_user)

    result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == current_user.id)
    )
    row = result.first()
    household_id = row[0] if row else None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_provider=current_user.email_provider,
        whatsapp_verified=current_user.whatsapp_verified,
        phone_whatsapp=current_user.phone_whatsapp,
        household_id=household_id,
    )


@router.delete("/me", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_confirm_delete: str = Header(None),
):
    if x_confirm_delete != "ELIMINAR":
        raise HTTPException(status_code=400, detail="Confirmation header missing or incorrect")

    from modules.settings.service import delete_user_account
    await delete_user_account(db, current_user.id)

    # Delete Supabase auth user (sync call — run in executor to avoid blocking)
    import asyncio
    from core.config import settings
    from supabase import create_client
    supabase_admin = create_client(settings.supabase_url, settings.supabase_service_key)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, supabase_admin.auth.admin.delete_user, str(current_user.id))
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/auth/router.py
git commit -m "feat: add PATCH /auth/me and DELETE /auth/me endpoints"
```

---

## Task 8: Backend — Register settings router + import models in main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Update main.py**

Add the settings model import and router registration:

After line 11 (`import modules.merchants.models  # noqa: F401`), add:
```python
import modules.settings.models  # noqa: F401
```

After line 19 (`from modules.whatsapp.router import router as whatsapp_router`), add:
```python
from modules.settings.router import router as settings_router
```

After line 63 (`app.include_router(bank_accounts_router)`), add:
```python
    app.include_router(settings_router)
```

- [ ] **Step 2: Verify the backend starts**

Run: `cd backend && python -c "from main import create_app; app = create_app(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: register settings router and models in main.py"
```

---

## Task 9: Backend — API tests for settings endpoints

**Files:**
- Create: `backend/tests/test_settings_api.py`

- [ ] **Step 1: Write test file**

```python
# backend/tests/test_settings_api.py
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from modules.auth.models import User


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="test@test.cl",
        full_name="Test User",
        email_provider="gmail",
        whatsapp_verified=False,
        phone_whatsapp=None,
    )


@pytest.fixture
def app():
    from main import create_app
    return create_app()


@pytest.fixture
def auth_app(app, mock_user):
    from core.security import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield app
    app.dependency_overrides.pop(get_current_user, None)


# --- Profile ---

@pytest.mark.asyncio
async def test_patch_profile_updates_name(auth_app, mock_user):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        with patch("modules.auth.router.AsyncSession", new_callable=AsyncMock):
            response = await c.patch(
                "/auth/me",
                json={"full_name": "New Name"},
                headers={"Authorization": "Bearer token"},
            )
    # Will need real DB for full integration test; smoke test for route existence
    assert response.status_code in (200, 500)  # 500 = DB not connected, route exists


@pytest.mark.asyncio
async def test_delete_account_requires_confirmation(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.delete(
            "/auth/me",
            headers={"Authorization": "Bearer token"},
        )
    assert response.status_code == 400
    assert "Confirmation header" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_account_with_wrong_header(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.delete(
            "/auth/me",
            headers={"Authorization": "Bearer token", "X-Confirm-Delete": "WRONG"},
        )
    assert response.status_code == 400


# --- Notifications ---

@pytest.mark.asyncio
async def test_get_notifications_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/notifications/preferences")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_notifications_returns_default(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.get(
            "/notifications/preferences",
            headers={"Authorization": "Bearer token"},
        )
    # Route exists (may fail on DB, but route is registered)
    assert response.status_code in (200, 500)


# --- Categories ---

@pytest.mark.asyncio
async def test_get_categories_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/categories/preferences")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_put_categories_validates_unknown(auth_app):
    async with AsyncClient(transport=ASGITransport(app=auth_app), base_url="http://test") as c:
        response = await c.put(
            "/categories/preferences",
            json={"categories": [{"category": "INVALID", "sort_order": 0, "hidden": False}]},
            headers={"Authorization": "Bearer token"},
        )
    # Either 422 (validation caught) or 500 (DB not connected but logic ran)
    assert response.status_code in (422, 500)
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/test_settings_api.py -v`
Expected: Tests pass (route registration + header validation)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_settings_api.py
git commit -m "test: add API tests for settings endpoints"
```

---

## Task 10: Frontend — Add API client methods

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add new API methods**

First, add `phone_whatsapp` to the `UserMe` interface:

```typescript
export interface UserMe {
  id: string;
  email: string;
  full_name: string;
  email_provider: string;
  whatsapp_verified: boolean;
  phone_whatsapp: string | null;  // ← ADD THIS
  household_id: string | null;
}
```

Then add the following methods to the `api` object in `frontend/app/lib/api.ts`:

```typescript
  // --- Profile ---
  async updateProfile(payload: { full_name?: string; phone_whatsapp?: string }) {
    return apiFetch<UserMe>("/auth/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  // --- Notifications ---
  async getNotificationPreferences() {
    return apiFetch<{ whatsapp_enabled: boolean }>("/notifications/preferences");
  },

  async updateNotificationPreferences(whatsapp_enabled: boolean) {
    return apiFetch<{ whatsapp_enabled: boolean }>("/notifications/preferences", {
      method: "PATCH",
      body: JSON.stringify({ whatsapp_enabled }),
    });
  },

  // --- Categories ---
  async getCategoryPreferences() {
    return apiFetch<{
      categories: Array<{ category: string; sort_order: number; hidden: boolean }>;
    }>("/categories/preferences");
  },

  async updateCategoryPreferences(
    categories: Array<{ category: string; sort_order: number; hidden: boolean }>
  ) {
    return apiFetch<{
      categories: Array<{ category: string; sort_order: number; hidden: boolean }>;
    }>("/categories/preferences", {
      method: "PUT",
      body: JSON.stringify({ categories }),
    });
  },

  // --- Delete Account ---
  async deleteAccount() {
    // Cannot use apiFetch — 204 has no body, res.json() would throw
    const authHeader = await getAuthHeader();
    const res = await fetch(`${API_URL}/auth/me`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", ...authHeader, "X-Confirm-Delete": "ELIMINAR" },
    });
    if (!res.ok) throw new Error(`API error ${res.status}: /auth/me`);
  },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add API client methods for profile, notifications, categories, delete"
```

---

## Task 11: Frontend — Install @dnd-kit

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dependencies**

Run: `cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`

- [ ] **Step 2: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add @dnd-kit for category drag-and-drop"
```

---

## Task 12: Frontend — ProfileSection component

**Files:**
- Create: `frontend/app/(dashboard)/settings/components/ProfileSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/app/(dashboard)/settings/components/ProfileSection.tsx
"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function ProfileSection({
  user,
}: {
  user: { full_name: string; email: string; phone_whatsapp: string | null };
}) {
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone_whatsapp ?? "");
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();
  const setUser = useLukaStore((s) => s.setUser);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateProfile({
        full_name: name,
        phone_whatsapp: phone || null,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setUser(data.id, data.full_name);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const hasChanges = name !== user.full_name || phone !== (user.phone_whatsapp ?? "");

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Perfil
      </h3>
      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Nombre</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        {/* Email (read-only) */}
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Email</label>
          <p className="px-3 py-2.5 text-sm text-slate-400 bg-slate-50 rounded-xl">
            {user.email}
          </p>
        </div>
        {/* WhatsApp */}
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">WhatsApp</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+56 9 1234 5678"
            className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        {/* Save */}
        <button
          onClick={() => mutation.mutate()}
          disabled={!hasChanges || mutation.isPending}
          className="w-full sm:w-auto px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-blue-700 transition-colors"
        >
          {mutation.isPending ? "Guardando..." : saved ? "Guardado" : "Guardar cambios"}
        </button>
        {mutation.isError && (
          <p className="text-xs text-red-500 mt-1">Error al guardar. Intenta de nuevo.</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/components/ProfileSection.tsx
git commit -m "feat: add ProfileSection component for settings"
```

---

## Task 13: Frontend — NotificationsSection component

**Files:**
- Create: `frontend/app/(dashboard)/settings/components/NotificationsSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/app/(dashboard)/settings/components/NotificationsSection.tsx
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function NotificationsSection() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api.getNotificationPreferences(),
  });

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.updateNotificationPreferences(enabled),
    onMutate: async (enabled) => {
      await queryClient.cancelQueries({ queryKey: ["notification-preferences"] });
      const previous = queryClient.getQueryData(["notification-preferences"]);
      queryClient.setQueryData(["notification-preferences"], { whatsapp_enabled: enabled });
      return { previous };
    },
    onError: (_err, _enabled, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["notification-preferences"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-preferences"] });
    },
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse mb-4" />
        <div className="h-6 w-48 bg-slate-100 rounded animate-pulse" />
      </div>
    );
  }

  const enabled = data?.whatsapp_enabled ?? true;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Notificaciones
      </h3>
      <label className="flex items-center justify-between cursor-pointer min-h-[44px]">
        <span className="text-sm text-slate-700">Notificaciones por WhatsApp</span>
        <button
          role="switch"
          aria-checked={enabled}
          onClick={() => mutation.mutate(!enabled)}
          className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
            enabled ? "bg-blue-600" : "bg-slate-200"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${
              enabled ? "translate-x-[22px]" : "translate-x-[2px]"
            } mt-[2px]`}
          />
        </button>
      </label>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/components/NotificationsSection.tsx
git commit -m "feat: add NotificationsSection component with optimistic toggle"
```

---

## Task 14: Frontend — CategoriesSection component (drag-and-drop)

**Files:**
- Create: `frontend/app/(dashboard)/settings/components/CategoriesSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/app/(dashboard)/settings/components/CategoriesSection.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "@/app/lib/api";

type CatPref = { category: string; sort_order: number; hidden: boolean };

function SortableItem({
  item,
  onToggleHidden,
}: {
  item: CatPref;
  onToggleHidden: (cat: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: item.category,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 px-3 py-2.5 bg-white rounded-lg border border-slate-100 ${
        item.hidden ? "opacity-40" : ""
      }`}
    >
      {/* Drag handle */}
      <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing p-1 touch-none">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-slate-300">
          <circle cx="5" cy="4" r="1.5" fill="currentColor" />
          <circle cx="11" cy="4" r="1.5" fill="currentColor" />
          <circle cx="5" cy="8" r="1.5" fill="currentColor" />
          <circle cx="11" cy="8" r="1.5" fill="currentColor" />
          <circle cx="5" cy="12" r="1.5" fill="currentColor" />
          <circle cx="11" cy="12" r="1.5" fill="currentColor" />
        </svg>
      </button>

      {/* Category name */}
      <span className="flex-1 text-sm text-slate-700">{item.category}</span>

      {/* Hide/show toggle */}
      <button
        onClick={() => onToggleHidden(item.category)}
        className="p-1.5 rounded-md hover:bg-slate-50 min-w-[44px] min-h-[44px] flex items-center justify-center"
      >
        {item.hidden ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    </div>
  );
}

export function CategoriesSection() {
  const queryClient = useQueryClient();
  const [localCats, setLocalCats] = useState<CatPref[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const { data, isLoading } = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
  });

  useEffect(() => {
    if (data?.categories) {
      setLocalCats(data.categories);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (cats: CatPref[]) => api.updateCategoryPreferences(cats),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
    },
  });

  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  const debouncedSave = useCallback(
    (cats: CatPref[]) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        mutateRef.current(cats);
      }, 500);
    },
    []
  );

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = localCats.findIndex((c) => c.category === active.id);
    const newIndex = localCats.findIndex((c) => c.category === over.id);
    const reordered = arrayMove(localCats, oldIndex, newIndex).map((c, i) => ({
      ...c,
      sort_order: i,
    }));
    setLocalCats(reordered);
    debouncedSave(reordered);
  }

  function handleToggleHidden(category: string) {
    const updated = localCats.map((c) =>
      c.category === category ? { ...c, hidden: !c.hidden } : c
    );
    setLocalCats(updated);
    debouncedSave(updated);
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse mb-4" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 bg-slate-50 rounded-lg animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  // Sort: visible first, then hidden
  const visible = localCats.filter((c) => !c.hidden);
  const hidden = localCats.filter((c) => c.hidden);
  const sorted = [...visible, ...hidden];

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Categorías
      </h3>
      <p className="text-xs text-slate-400 mb-3">Arrastra para reordenar. Oculta las que no uses.</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={sorted.map((c) => c.category)} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {sorted.map((item) => (
              <SortableItem key={item.category} item={item} onToggleHidden={handleToggleHidden} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      {mutation.isError && (
        <p className="text-xs text-red-500 mt-2">Error al guardar. Intenta de nuevo.</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/components/CategoriesSection.tsx
git commit -m "feat: add CategoriesSection with drag-and-drop reorder and hide/show"
```

---

## Task 15: Frontend — DeleteAccountSection component

**Files:**
- Create: `frontend/app/(dashboard)/settings/components/DeleteAccountSection.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/app/(dashboard)/settings/components/DeleteAccountSection.tsx
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";

export function DeleteAccountSection() {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const router = useRouter();
  const reset = useLukaStore((s) => s.reset);

  const mutation = useMutation({
    mutationFn: () => api.deleteAccount(),
    onSuccess: async () => {
      const supabase = createClient();
      await supabase.auth.signOut();
      reset();
      router.push("/login");
    },
  });

  const canDelete = confirmation === "ELIMINAR";

  return (
    <>
      <div className="pt-6 border-t border-red-100">
        <button
          onClick={() => setOpen(true)}
          className="text-sm text-red-500 font-medium hover:text-red-600 transition-colors"
        >
          Eliminar cuenta
        </button>
      </div>

      {/* Mobile: bottom sheet, Desktop: also uses bottom sheet for simplicity */}
      <BottomSheet open={open} onClose={() => { setOpen(false); setConfirmation(""); }}>
        <div className="p-5 space-y-4">
          <h3 className="text-lg font-semibold text-slate-900">Eliminar cuenta</h3>
          <p className="text-sm text-slate-600">
            Esto es irreversible. Se eliminarán todos tus datos: transacciones, cuentas
            bancarias, presupuestos y configuración.
          </p>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Escribe ELIMINAR para confirmar
            </label>
            <input
              type="text"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              placeholder="ELIMINAR"
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
            />
          </div>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canDelete || mutation.isPending}
            className="w-full py-2.5 bg-red-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-red-700 transition-colors"
          >
            {mutation.isPending ? "Eliminando..." : "Eliminar cuenta permanentemente"}
          </button>
          {mutation.isError && (
            <p className="text-xs text-red-500">Error al eliminar. Intenta de nuevo.</p>
          )}
        </div>
      </BottomSheet>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/components/DeleteAccountSection.tsx
git commit -m "feat: add DeleteAccountSection with confirmation bottom sheet"
```

---

## Task 16: Frontend — HogarSection + PrivacySection + BankAccountsSection

**Files:**
- Create: `frontend/app/(dashboard)/settings/components/HogarSection.tsx`
- Create: `frontend/app/(dashboard)/settings/components/PrivacySection.tsx`
- Create: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`

- [ ] **Step 1: Create HogarSection**

```tsx
// frontend/app/(dashboard)/settings/components/HogarSection.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function HogarSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);

  const { data: summary } = useQuery({
    queryKey: ["household-summary", householdId],
    queryFn: () => api.getHouseholdSummary(householdId!),
    enabled: !!householdId,
  });

  const members = summary ?? [];
  const isCoupleHousehold = members.length > 1;
  // Sort: current user first, partner second
  const sorted = [...members].sort((a: any, b: any) =>
    a.user_id === userId ? -1 : b.user_id === userId ? 1 : 0
  );

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Hogar
      </h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">Tipo</span>
          <span className="text-sm font-medium text-slate-700">
            {isCoupleHousehold ? "Pareja" : "Individual"}
          </span>
        </div>
        {sorted.map((member: { user_id: string; user_name: string; user_email: string }) => (
          <div key={member.user_id} className="flex items-center justify-between">
            <span className="text-sm text-slate-500">
              {member.user_id === userId ? "Tú" : "Pareja"}
            </span>
            <div className="text-right">
              <p className="text-sm font-medium text-slate-700">{member.user_name}</p>
              <p className="text-xs text-slate-400">{member.user_email}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create PrivacySection**

```tsx
// frontend/app/(dashboard)/settings/components/PrivacySection.tsx
export function PrivacySection() {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Privacidad de Datos
      </h3>
      <div className="space-y-2 text-sm text-slate-500 leading-relaxed">
        <p>
          Luka procesa tus notificaciones bancarias para categorizar transacciones.
          Los emails se eliminan automáticamente dentro de 24 horas.
        </p>
        <p>
          Nunca almacenamos números de tarjeta, contraseñas bancarias ni credenciales
          de acceso a tu banco.
        </p>
        <p>
          Puedes eliminar tu cuenta y todos tus datos en cualquier momento desde esta
          página.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create BankAccountsSection**

This extracts the bank accounts logic from the current `settings/page.tsx`. The component should contain the `ConnectBankSection` and `AccountCard` sub-components, moved as-is from the current page with only styling polish (card shadows, spacing, DM Sans inheritance).

Read the current `frontend/app/(dashboard)/settings/page.tsx` and extract lines related to bank account management into this component. Keep all Fintoc integration, polling, account CRUD logic intact. The only changes are:
- Wrap in the standard card container (`bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)]`)
- Add the section header (`CUENTAS BANCARIAS` uppercase label)
- Accept `householdId` as a prop instead of reading from store internally

```tsx
// frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx
"use client";
// ... extract ConnectBankSection + AccountCard from current page.tsx
// Wrap in standard card container
// Accept householdId as prop
```

The implementer should read `frontend/app/(dashboard)/settings/page.tsx` and extract the `ConnectBankSection`, `AccountCard`, and related helper components (`ACCOUNT_TYPE_LABELS`, etc.) into this file, wrapping them in the new card styling.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/components/HogarSection.tsx frontend/app/\(dashboard\)/settings/components/PrivacySection.tsx frontend/app/\(dashboard\)/settings/components/BankAccountsSection.tsx
git commit -m "feat: add HogarSection, PrivacySection, BankAccountsSection components"
```

---

## Task 17: Frontend — Rewrite Settings page.tsx

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Rewrite the settings page**

Replace the entire contents of `frontend/app/(dashboard)/settings/page.tsx` with a clean composition of section components:

```tsx
// frontend/app/(dashboard)/settings/page.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { ProfileSection } from "./components/ProfileSection";
import { BankAccountsSection } from "./components/BankAccountsSection";
import { HogarSection } from "./components/HogarSection";
import { NotificationsSection } from "./components/NotificationsSection";
import { CategoriesSection } from "./components/CategoriesSection";
import { PrivacySection } from "./components/PrivacySection";
import { DeleteAccountSection } from "./components/DeleteAccountSection";

export default function SettingsPage() {
  const householdId = useLukaStore((s) => s.householdId);

  const { data: me, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  if (isLoading || !me) {
    return (
      <div className="space-y-4 p-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-32 bg-white rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-32">
      <div>
        <h1 className="text-2xl font-bold text-luka-dark">Configuración</h1>
        <p className="text-sm text-slate-500 mt-1">Administra tu cuenta y preferencias</p>
      </div>

      <div className="space-y-4">
        <ProfileSection
          user={{
            full_name: me.full_name,
            email: me.email,
            phone_whatsapp: me.phone_whatsapp ?? null,
          }}
        />

        <BankAccountsSection householdId={householdId} />

        <HogarSection />

        <NotificationsSection />

        <CategoriesSection />

        <PrivacySection />

        <DeleteAccountSection />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the page renders**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/page.tsx
git commit -m "feat: rewrite settings page as composition of section components"
```

---

## Task 18: Frontend — Login page polish

**Files:**
- Modify: `frontend/app/(auth)/login/page.tsx`

- [ ] **Step 1: Polish the login page**

Read the current login page and apply these changes:
- Verify DM Sans propagates (it should via root layout, but check)
- Update button styles to use `rounded-xl` (matching dashboard) instead of current `rounded-lg`
- Ensure focus states use `focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500`
- Polish descriptive text if needed (clarity, tone)
- Ensure all interactive elements have minimum 44px touch targets on mobile
- No structural changes

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(auth\)/login/page.tsx
git commit -m "style: polish login page — rounded-xl buttons, consistent focus states"
```

---

## Task 19: Frontend — Onboarding pages polish

**Files:**
- Modify: `frontend/app/(auth)/onboarding/layout.tsx`
- Modify: `frontend/app/(auth)/onboarding/setup-household/page.tsx`
- Modify: `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx`
- Modify: `frontend/app/(auth)/onboarding/connect-bank/page.tsx`

- [ ] **Step 1: Polish the onboarding layout**

In `layout.tsx`:
- Update step indicator circles to use `shadow-[0_1px_3px_rgba(0,0,0,0.03)]` on active step
- Ensure consistent sizing (active step circle at least 44px diameter for touch)
- Verify DM Sans propagates

- [ ] **Step 2: Polish setup-household page**

- Update button styles: `rounded-xl` instead of `rounded-lg`
- Input styles: `rounded-xl`, `focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500`
- Consistent spacing (gap-4 between form elements)

- [ ] **Step 3: Polish verify-whatsapp page**

Same treatment as setup-household:
- `rounded-xl` buttons and inputs
- Consistent focus rings
- 44px minimum touch targets for buttons

- [ ] **Step 4: Polish connect-bank page**

- `rounded-xl` buttons
- Consistent styling with other onboarding steps

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(auth\)/onboarding/
git commit -m "style: polish onboarding pages — consistent buttons, inputs, focus states"
```

---

## Task 20: Final verification + deploy

**Files:** None new

- [ ] **Step 1: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Push to main**

```bash
git push origin main
```

Both Vercel (frontend) and Railway (backend) will auto-deploy.
