# Merchant Cleaning & Review Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pipeline that groups raw bank merchant names into canonical merchants via LLM, lets users review them in a Tinder-style swipe UI, and provides a CLI for developer curation — all backed by a global shared merchant dataset.

**Architecture:** New `canonical_merchants` table as the clean merchant identity layer, linked from existing `merchants` via FK. Two-phase LLM batch job (ARQ): Phase 1 groups+names, Phase 2 reuses existing `lookup_merchant()` for categorization. Notification center in sidebar drives user to review UI. CLI script enables developer curation.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Gemini 2.5 Flash (LLM), ARQ + Redis (jobs), Next.js 14 + React Query + Tailwind + shadcn/ui (frontend), click (CLI)

**Spec:** `docs/superpowers/specs/2026-04-01-merchant-cleaning-review-design.md`

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/alembic/versions/022_canonical_merchants_and_notifications.py` | Migration: create `canonical_merchants`, `notifications`, `merchant_review_jobs` tables; add `canonical_merchant_id` to `merchants` |
| `backend/modules/notifications/__init__.py` | Module init |
| `backend/modules/notifications/models.py` | SQLAlchemy models: `Notification` |
| `backend/modules/merchant_review/models.py` | SQLAlchemy models: `CanonicalMerchant`, `MerchantReviewJob` |
| `backend/modules/notifications/schemas.py` | Pydantic schemas for notification endpoints |
| `backend/modules/notifications/service.py` | Business logic: create, list, update notifications |
| `backend/modules/notifications/router.py` | FastAPI endpoints: GET/PATCH `/notifications` |
| `backend/modules/merchant_review/__init__.py` | Module init |
| `backend/modules/merchant_review/schemas.py` | Pydantic schemas for review endpoints |
| `backend/modules/merchant_review/service.py` | Business logic: get review cards, approve/edit/skip merchants |
| `backend/modules/merchant_review/router.py` | FastAPI endpoints: GET/PATCH `/merchant-review` |
| `backend/modules/merchant_review/llm_grouping.py` | Phase 1 LLM call: group raw names → canonical merchants |
| `backend/scripts/train_merchants.py` | CLI script: seed, review, merge, stats, regroup |
| `backend/tests/test_canonical_merchants.py` | Tests for canonical merchant creation + linking |
| `backend/tests/test_merchant_review_api.py` | Tests for review API endpoints |
| `backend/tests/test_notifications_api.py` | Tests for notification API endpoints |
| `backend/tests/test_llm_grouping.py` | Tests for Phase 1 LLM grouping logic |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/modules/merchants/models.py` | Add `canonical_merchant_id` FK column to `Merchant` |
| `backend/modules/merchants/service.py` | No changes needed (Phase 2 reuses as-is) |
| `backend/modules/bank_connect/router.py:263-352` | After `_process_movements()`, trigger review job if `created > 0` |
| `backend/jobs/tasks.py` | Add `process_merchant_review` ARQ job |
| `backend/main.py` | Register notification + merchant_review routers, import models |
| `backend/modules/transactions/router.py` | Modify GET `/transactions/mine` to join `display_name` |
| `backend/modules/transactions/schemas.py` | Add `display_name` field to `TransactionResponse` |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/app/lib/hooks/useNotifications.ts` | React Query hooks: `useNotifications()`, `useUnreadCount()` |
| `frontend/app/lib/hooks/useMerchantReview.ts` | React Query hooks: `useMerchantReview()`, `useReviewStatus()` |
| `frontend/app/(dashboard)/notifications/page.tsx` | Notifications list page |
| `frontend/app/(dashboard)/transactions/review/[jobId]/page.tsx` | Tinder-style swipe review UI |
| `frontend/app/(dashboard)/components/NotificationBadge.tsx` | Sidebar notification item with badge count |
| `frontend/app/(dashboard)/components/ProcessingBanner.tsx` | Green banner shown during ARQ processing |
| `frontend/app/(dashboard)/components/MerchantCard.tsx` | Single swipe card component (view + edit mode) |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/app/lib/api.ts` | Add notification + review types and endpoint methods |
| `frontend/app/(dashboard)/components/Sidebar.tsx` | Add `NotificationBadge` below nav items |
| `frontend/app/(dashboard)/components/BottomNav.tsx` | Add notification icon for mobile |
| `frontend/app/(dashboard)/transactions/page.tsx` | Add `ProcessingBanner` at top |
| `frontend/app/(dashboard)/components/RecentTransactions.tsx` | Display `display_name` when available, fallback to `raw_merchant_name` |

---

## Task 1: Database Migration — New Tables + Modified Column

**Files:**
- Create: `backend/alembic/versions/022_canonical_merchants_and_notifications.py`
- Modify: `backend/modules/merchants/models.py`

- [ ] **Step 1: Create the Alembic migration**

```python
"""Add canonical_merchants, notifications, merchant_review_jobs tables."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision = "022"
down_revision = "021"


def upgrade() -> None:
    # canonical_merchants
    op.create_table(
        "canonical_merchants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("display_name", sa.String(), nullable=False, unique=True),
        sa.Column("default_category", sa.String(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("status", sa.String(), server_default="unread", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_user_status", "notifications", ["user_id", "status"])

    # merchant_review_jobs
    op.create_table(
        "merchant_review_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bank_credential_id", UUID(as_uuid=True), sa.ForeignKey("bank_credentials.id"), nullable=False),
        sa.Column("status", sa.String(), server_default="processing", nullable=False),
        sa.Column("total_merchants", sa.Integer(), nullable=True),
        sa.Column("reviewed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("notification_id", UUID(as_uuid=True), sa.ForeignKey("notifications.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add FK column to merchants
    op.add_column("merchants", sa.Column("canonical_merchant_id", UUID(as_uuid=True), sa.ForeignKey("canonical_merchants.id"), nullable=True))

    # Add review_job_id to canonical_merchants so we can scope review cards per job
    op.add_column("canonical_merchants", sa.Column("review_job_id", UUID(as_uuid=True), sa.ForeignKey("merchant_review_jobs.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("canonical_merchants", "review_job_id")
    op.drop_column("merchants", "canonical_merchant_id")
    op.drop_table("merchant_review_jobs")
    op.drop_index("ix_notifications_user_status", "notifications")
    op.drop_table("notifications")
    op.drop_table("canonical_merchants")
```

- [ ] **Step 2: Update the Merchant model**

In `backend/modules/merchants/models.py`, add the FK column to the `Merchant` class:

```python
canonical_merchant_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("canonical_merchants.id"), nullable=True
)
```

- [ ] **Step 3: Run the migration**

```bash
cd backend && alembic upgrade head
```
Expected: Migration applies cleanly, no errors.

- [ ] **Step 4: Verify tables exist**

```bash
cd backend && python -c "
from core.database import engine
import asyncio
from sqlalchemy import inspect

async def check():
    async with engine.connect() as conn:
        def _inspect(conn):
            insp = inspect(conn)
            tables = insp.get_table_names()
            for t in ['canonical_merchants', 'notifications', 'merchant_review_jobs']:
                assert t in tables, f'{t} not found'
            cols = [c['name'] for c in insp.get_columns('merchants')]
            assert 'canonical_merchant_id' in cols
            print('All tables and columns verified')
        await conn.run_sync(_inspect)

asyncio.run(check())
"
```

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/022_canonical_merchants_and_notifications.py backend/modules/merchants/models.py
git commit -m "feat: add canonical_merchants, notifications, merchant_review_jobs tables"
```

---

## Task 2: Backend Models — Notification, MerchantReviewJob, CanonicalMerchant

**Files:**
- Create: `backend/modules/notifications/__init__.py`
- Create: `backend/modules/notifications/models.py`
- Create: `backend/modules/merchant_review/models.py` (note: `__init__.py` created in Task 4)

- [ ] **Step 1: Create the notifications module**

`backend/modules/notifications/__init__.py` — empty file.

`backend/modules/notifications/models.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String, default="unread")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`backend/modules/merchant_review/models.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class CanonicalMerchant(Base):
    __tablename__ = "canonical_merchants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    default_category: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    review_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchant_review_jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantReviewJob(Base):
    __tablename__ = "merchant_review_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_credential_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_credentials.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="processing")
    total_merchants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_count: Mapped[int] = mapped_column(Integer, default=0)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register models in main.py**

Add to `backend/main.py` imports section:

```python
import modules.notifications.models  # noqa: F401
import modules.merchant_review.models  # noqa: F401
```

- [ ] **Step 3: Verify models load**

```bash
cd backend && python -c "from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.notifications.models import Notification; print('Models imported OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/modules/notifications/ backend/main.py
git commit -m "feat: add CanonicalMerchant, Notification, MerchantReviewJob models"
```

---

## Task 3: Notifications API — Service + Router + Schemas

**Files:**
- Create: `backend/modules/notifications/schemas.py`
- Create: `backend/modules/notifications/service.py`
- Create: `backend/modules/notifications/router.py`
- Create: `backend/tests/test_notifications_api.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Write test for notifications API**

`backend/tests/test_notifications_api.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_get_notifications_requires_auth(http_client: AsyncClient):
    resp = await http_client.get("/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_notifications_returns_list(http_client: AsyncClient, override_auth, override_db):
    with patch("modules.notifications.service.get_user_notifications", new_callable=AsyncMock, return_value=[]):
        resp = await http_client.get("/notifications")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_patch_notification_mark_read(http_client: AsyncClient, override_auth, override_db):
    fake_notif = {
        "id": "00000000-0000-0000-0000-000000000001",
        "type": "merchant_review",
        "title": "47 merchants ready",
        "status": "read",
        "payload": {},
        "created_at": "2026-04-01T00:00:00Z",
        "read_at": "2026-04-01T00:01:00Z",
    }
    with patch("modules.notifications.service.update_notification", new_callable=AsyncMock, return_value=fake_notif):
        resp = await http_client.patch(
            "/notifications/00000000-0000-0000-0000-000000000001",
            json={"status": "read"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"


@pytest.mark.asyncio
async def test_get_unread_count(http_client: AsyncClient, override_auth, override_db):
    with patch("modules.notifications.service.get_unread_count", new_callable=AsyncMock, return_value=3):
        resp = await http_client.get("/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json() == {"count": 3}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_notifications_api.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write schemas**

`backend/modules/notifications/schemas.py`:

```python
from pydantic import BaseModel
from datetime import datetime


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    status: str
    payload: dict | None = None
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationUpdate(BaseModel):
    status: str  # "read", "dismissed", "actioned"


class UnreadCountResponse(BaseModel):
    count: int
```

- [ ] **Step 4: Write service**

`backend/modules/notifications/service.py`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from modules.notifications.models import Notification


async def get_user_notifications(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.status == "unread")
    )
    return result.scalar_one()


async def update_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID, status: str
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return None

    notif.status = status
    notif.updated_at = datetime.now(timezone.utc)
    if status == "read":
        notif.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(notif)
    return notif


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    payload: dict | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        payload=payload,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif
```

- [ ] **Step 5: Write router**

`backend/modules/notifications/router.py`:

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.notifications import service
from modules.notifications.schemas import (
    NotificationResponse,
    NotificationUpdate,
    UnreadCountResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_user_notifications(db, current_user.id)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await service.get_unread_count(db, current_user.id)
    return {"count": count}


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: uuid.UUID,
    body: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = await service.update_notification(db, current_user.id, notification_id, body.status)
    if not notif:
        raise HTTPException(404, "Notification not found")
    return notif
```

- [ ] **Step 6: Register router in main.py**

Add to `backend/main.py`:

```python
from modules.notifications.router import router as notifications_router
```

And in `create_app()`:

```python
app.include_router(notifications_router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_notifications_api.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/modules/notifications/ backend/tests/test_notifications_api.py backend/main.py
git commit -m "feat: add notifications API — list, unread count, mark read/dismissed"
```

---

## Task 4: LLM Grouping — Phase 1 Logic

**Files:**
- Create: `backend/modules/merchant_review/__init__.py`
- Create: `backend/modules/merchant_review/llm_grouping.py`
- Create: `backend/tests/test_llm_grouping.py`

- [ ] **Step 1: Write test for LLM grouping**

`backend/tests/test_llm_grouping.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_group_merchants_parses_llm_response():
    """Test that the grouping function correctly parses LLM JSON output."""
    from modules.merchant_review.llm_grouping import group_raw_merchants

    fake_llm_response = [
        {"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", "LIDER LAS CONDES"]},
        {"display_name": "Netflix", "raw_names": ["NETFLIX.COM"]},
    ]

    with patch(
        "modules.merchant_review.llm_grouping._call_grouping_llm",
        new_callable=AsyncMock,
        return_value=fake_llm_response,
    ):
        result = await group_raw_merchants(["LIDER PROVIDENCIA", "LIDER LAS CONDES", "NETFLIX.COM"])

    assert len(result) == 2
    assert result[0]["display_name"] == "Lider"
    assert set(result[0]["raw_names"]) == {"LIDER PROVIDENCIA", "LIDER LAS CONDES"}
    assert result[1]["display_name"] == "Netflix"


@pytest.mark.asyncio
async def test_group_merchants_handles_empty_input():
    from modules.merchant_review.llm_grouping import group_raw_merchants

    result = await group_raw_merchants([])
    assert result == []


@pytest.mark.asyncio
async def test_group_merchants_handles_llm_failure():
    from modules.merchant_review.llm_grouping import group_raw_merchants

    with patch(
        "modules.merchant_review.llm_grouping._call_grouping_llm",
        new_callable=AsyncMock,
        side_effect=Exception("LLM timeout"),
    ):
        result = await group_raw_merchants(["LIDER PROVIDENCIA"])

    # On failure, each name becomes its own group with title-cased display name
    assert len(result) == 1
    assert result[0]["display_name"] == "Lider Providencia"
    assert result[0]["raw_names"] == ["LIDER PROVIDENCIA"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_llm_grouping.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Implement LLM grouping**

`backend/modules/merchant_review/__init__.py` — empty file.

`backend/modules/merchant_review/llm_grouping.py`:

```python
import json
import logging
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings
from modules.merchants.llm import _get_client, _strip_code_fences

logger = logging.getLogger(__name__)

_GROUPING_PROMPT = """You are a banking data specialist. Given a list of raw merchant names from bank statements, group them by BUSINESS ENTITY.

Rules:
- Group ONLY when the same company/brand (different branches OK)
- NEVER group by business type (two different restaurants = separate)
- NEVER group different services from same company (e.g., Uber Trips ≠ Uber Eats)
- NEVER group different businesses that share a category (e.g., "Estacionamiento PR" ≠ "Estacionamiento Vita")
- When in doubt, keep separate
- Generate a clean display name for each group
- Fix casing (ALL CAPS → proper case)
- Remove bank transaction prefixes (COMPRA, PAGO, CARGO, PURCHASE, etc.)
- Keep the business name recognizable

Respond ONLY with JSON. Format:
[
  {"display_name": "Clean Name", "raw_names": ["RAW1", "RAW2"]},
  ...
]"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _call_grouping_llm(raw_names: list[str]) -> list[dict]:
    response = await _get_client().aio.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"Raw merchant names:\n{json.dumps(raw_names)}",
        config=genai.types.GenerateContentConfig(
            system_instruction=_GROUPING_PROMPT,
            temperature=0.2,
            max_output_tokens=4096,
            thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw = _strip_code_fences(response.text)
    return json.loads(raw)


def _fallback_grouping(raw_names: list[str]) -> list[dict]:
    """If LLM fails, each name becomes its own group with title-cased name."""
    result = []
    for name in raw_names:
        # Strip common prefixes for display
        display = name
        for prefix in ("COMPRA ", "PAGO ", "CARGO ", "PURCHASE "):
            if display.upper().startswith(prefix):
                display = display[len(prefix):]
                break
        result.append({
            "display_name": display.strip().title(),
            "raw_names": [name],
        })
    return result


async def group_raw_merchants(raw_names: list[str]) -> list[dict]:
    """
    Group raw merchant names into canonical merchant proposals.
    Returns: [{"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", ...]}, ...]
    """
    if not raw_names:
        return []

    try:
        return await _call_grouping_llm(raw_names)
    except Exception:
        logger.exception("LLM grouping failed, falling back to individual grouping")
        return _fallback_grouping(raw_names)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/test_llm_grouping.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/merchant_review/ backend/tests/test_llm_grouping.py
git commit -m "feat: add LLM grouping for raw merchant names (Phase 1)"
```

---

## Task 5: Merchant Review Service + ARQ Job

**Files:**
- Create: `backend/modules/merchant_review/service.py`
- Create: `backend/modules/merchant_review/schemas.py`
- Modify: `backend/jobs/tasks.py` (add `process_merchant_review` job)
- Create: `backend/tests/test_canonical_merchants.py`

- [ ] **Step 1: Write test for canonical merchant creation**

`backend/tests/test_canonical_merchants.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_create_canonical_from_groups():
    """Test that LLM groups are correctly persisted as canonical merchants."""
    from modules.merchant_review.service import create_canonicals_from_groups

    groups = [
        {"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", "LIDER LAS CONDES"]},
        {"display_name": "Netflix", "raw_names": ["NETFLIX.COM"]},
    ]

    with patch(
        "modules.merchant_review.service._get_or_create_canonical",
        new_callable=AsyncMock,
    ) as mock_get_or_create:
        mock_get_or_create.side_effect = [
            {"id": "uuid-1", "display_name": "Lider", "is_new": True},
            {"id": "uuid-2", "display_name": "Netflix", "is_new": True},
        ]
        with patch(
            "modules.merchant_review.service._link_merchants_to_canonical",
            new_callable=AsyncMock,
        ):
            result = await create_canonicals_from_groups(None, groups)

    assert len(result) == 2
    assert mock_get_or_create.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_canonical_merchants.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write merchant review schemas**

`backend/modules/merchant_review/schemas.py`:

```python
from pydantic import BaseModel


class ReviewCardResponse(BaseModel):
    canonical_merchant_id: str
    display_name: str
    default_category: str | None = None
    llm_suggested_categories: list[str] = []
    raw_names: list[str] = []
    transaction_count: int = 0
    total_amount: float = 0.0
    is_verified: bool = False

    model_config = {"from_attributes": True}


class ReviewStatusResponse(BaseModel):
    job_id: str
    status: str  # processing, ready, completed, skipped, failed
    total_merchants: int | None = None
    reviewed_count: int = 0


class MerchantApproval(BaseModel):
    display_name: str | None = None  # None = keep LLM suggestion
    category: str | None = None  # None = keep LLM suggestion
    action: str  # "approve", "skip"
```

- [ ] **Step 4: Write merchant review service**

`backend/modules/merchant_review/service.py`:

```python
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.notifications.models import Notification
from modules.merchants.models import Merchant
from modules.transactions.models import Transaction

logger = logging.getLogger(__name__)


async def _get_or_create_canonical(
    db: AsyncSession, display_name: str, review_job_id: uuid.UUID | None = None
) -> dict:
    """Get existing or create new canonical merchant. Returns dict with id, display_name, is_new."""
    result = await db.execute(
        select(CanonicalMerchant).where(CanonicalMerchant.display_name == display_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return {"id": str(existing.id), "display_name": existing.display_name, "is_new": False}

    try:
        canonical = CanonicalMerchant(display_name=display_name, review_job_id=review_job_id)
        db.add(canonical)
        await db.flush()
        return {"id": str(canonical.id), "display_name": canonical.display_name, "is_new": True}
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.display_name == display_name)
        )
        existing = result.scalar_one()
        return {"id": str(existing.id), "display_name": existing.display_name, "is_new": False}


async def _link_merchants_to_canonical(
    db: AsyncSession, raw_names: list[str], canonical_id: uuid.UUID
) -> None:
    """Link merchant rows to their canonical merchant."""
    for raw_name in raw_names:
        result = await db.execute(select(Merchant).where(Merchant.raw_name == raw_name))
        merchant = result.scalar_one_or_none()
        if merchant and not merchant.canonical_merchant_id:
            merchant.canonical_merchant_id = canonical_id


async def create_canonicals_from_groups(
    db: AsyncSession, groups: list[dict], review_job_id: uuid.UUID | None = None
) -> list[dict]:
    """Create canonical merchants from LLM grouping output. Returns list of created/linked canonicals."""
    results = []
    for group in groups:
        info = await _get_or_create_canonical(db, group["display_name"], review_job_id)
        canonical_id = uuid.UUID(info["id"])
        await _link_merchants_to_canonical(db, group["raw_names"], canonical_id)
        results.append(info)
    return results


async def get_review_cards(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict]:
    """Get all canonical merchants for a review job, with aggregated transaction data."""
    job = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    review_job = job.scalar_one_or_none()
    if not review_job:
        return []

    # Get all canonical merchants created during this job's time window
    # by finding merchants linked during job processing
    result = await db.execute(
        select(
            CanonicalMerchant.id,
            CanonicalMerchant.display_name,
            CanonicalMerchant.default_category,
            CanonicalMerchant.is_verified,
            func.array_agg(Merchant.raw_name).label("raw_names"),
        )
        .join(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .join(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
        .where(
            Transaction.user_id == user_id,
            CanonicalMerchant.review_job_id == job_id,
        )
        .group_by(CanonicalMerchant.id)
    )
    rows = result.all()

    cards = []
    for row in rows:
        # Get transaction stats for this canonical merchant
        stats = await db.execute(
            select(
                func.count().label("count"),
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.raw_merchant_name.in_(row.raw_names),
            )
        )
        stat = stats.one()

        # Get LLM suggestions from the first linked merchant
        merchant_result = await db.execute(
            select(Merchant).where(Merchant.raw_name == row.raw_names[0])
        )
        merchant = merchant_result.scalar_one_or_none()

        cards.append({
            "canonical_merchant_id": str(row.id),
            "display_name": row.display_name,
            "default_category": row.default_category,
            "llm_suggested_categories": merchant.llm_suggested_categories or [] if merchant else [],
            "raw_names": list(set(row.raw_names)),
            "transaction_count": stat.count,
            "total_amount": float(stat.total or 0),
            "is_verified": row.is_verified,
        })

    return cards


async def approve_merchant(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    canonical_id: uuid.UUID,
    display_name: str | None,
    category: str | None,
) -> bool:
    """Approve (and optionally edit) a canonical merchant."""
    canonical = await db.execute(
        select(CanonicalMerchant).where(CanonicalMerchant.id == canonical_id)
    )
    merchant = canonical.scalar_one_or_none()
    if not merchant:
        return False

    if display_name:
        merchant.display_name = display_name
    if category:
        merchant.default_category = category
    merchant.is_verified = True
    merchant.updated_at = datetime.now(timezone.utc)

    # Update all linked transactions with the category
    if category:
        linked_merchants = await db.execute(
            select(Merchant.raw_name).where(Merchant.canonical_merchant_id == canonical_id)
        )
        raw_names = [r[0] for r in linked_merchants.all()]
        if raw_names:
            await db.execute(
                Transaction.__table__.update()
                .where(
                    Transaction.user_id == user_id,
                    Transaction.raw_merchant_name.in_(raw_names),
                    Transaction.category.is_(None),
                )
                .values(category=category)
            )

    # Increment reviewed count on the job
    job = await db.execute(
        select(MerchantReviewJob).where(MerchantReviewJob.id == job_id)
    )
    review_job = job.scalar_one_or_none()
    if review_job:
        review_job.reviewed_count += 1
        review_job.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return True


async def skip_review(
    db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> bool:
    """Skip entire review — auto-accept all LLM values."""
    result = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        return False

    job.status = "skipped"
    job.completed_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)

    # Also dismiss the notification
    if job.notification_id:
        notif = await db.execute(
            select(Notification).where(Notification.id == job.notification_id)
        )
        notification = notif.scalar_one_or_none()
        if notification:
            notification.status = "dismissed"
            notification.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return True
```

- [ ] **Step 5: Write the ARQ job**

Add to `backend/jobs/tasks.py` — import at top:

```python
from modules.merchant_review.llm_grouping import group_raw_merchants
from modules.merchant_review.service import create_canonicals_from_groups
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.notifications.models import Notification
from modules.notifications.service import create_notification
```

Add the job function:

```python
async def process_merchant_review(ctx: dict, job_id: str) -> None:
    """
    ARQ job: Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.
    """
    async with AsyncSessionLocal() as db:
        redis = aioredis.from_url(settings.redis_url)
        try:
            # Load the review job
            result = await db.execute(
                select(MerchantReviewJob).where(MerchantReviewJob.id == uuid.UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if not job:
                logger.error("Review job %s not found", job_id)
                return

            # Collect unique raw merchant names from user's uncategorized connect transactions
            txn_result = await db.execute(
                select(Transaction.raw_merchant_name)
                .where(
                    Transaction.user_id == job.user_id,
                    Transaction.source_type == "connect",
                    Transaction.category.is_(None),
                )
                .distinct()
            )
            raw_names = [r[0] for r in txn_result.all() if r[0]]

            # Filter out names that already have a canonical merchant
            names_to_process = []
            for name in raw_names:
                mr = await db.execute(
                    select(Merchant).where(Merchant.raw_name == name)
                )
                merchant = mr.scalar_one_or_none()
                if not merchant or not merchant.canonical_merchant_id:
                    names_to_process.append(name)
                    # Ensure merchant row exists
                    if not merchant:
                        db.add(Merchant(raw_name=name, normalized_name=name))
                        await db.flush()

            if not names_to_process:
                job.status = "ready"
                job.total_merchants = 0
                await db.commit()
                return

            # Phase 1: LLM grouping
            groups = await group_raw_merchants(names_to_process)

            # Create canonical merchants and link (pass job.id to scope review cards)
            canonicals = await create_canonicals_from_groups(db, groups, review_job_id=job.id)
            await db.commit()

            # Phase 2: Categorize each new canonical using existing lookup_merchant
            new_count = 0
            for i, group in enumerate(groups):
                canonical_info = canonicals[i]
                if not canonical_info.get("is_new"):
                    continue

                first_raw = group["raw_names"][0]
                categories = await lookup_merchant(first_raw, db, redis)

                if categories:
                    canonical_result = await db.execute(
                        select(CanonicalMerchant).where(
                            CanonicalMerchant.id == uuid.UUID(canonical_info["id"])
                        )
                    )
                    canonical = canonical_result.scalar_one_or_none()
                    if canonical:
                        canonical.default_category = categories[0]

                    # Apply category to all linked transactions
                    for raw_name in group["raw_names"]:
                        await db.execute(
                            Transaction.__table__.update()
                            .where(
                                Transaction.user_id == job.user_id,
                                Transaction.raw_merchant_name == raw_name,
                                Transaction.category.is_(None),
                            )
                            .values(category=categories[0])
                        )

                new_count += 1

            # Finalize
            job.status = "ready"
            job.total_merchants = new_count
            job.updated_at = datetime.now(timezone.utc)

            # Update notification title
            if job.notification_id:
                notif_result = await db.execute(
                    select(Notification).where(Notification.id == job.notification_id)
                )
                notif = notif_result.scalar_one_or_none()
                if notif:
                    notif.title = f"{new_count} merchants ready for review"
                    notif.updated_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info("Review job %s complete: %d canonical merchants created", job_id, new_count)

        except Exception:
            logger.exception("Review job %s failed", job_id)
            # Use a fresh session — the original may be in a broken state
            async with AsyncSessionLocal() as error_db:
                result = await error_db.execute(
                    select(MerchantReviewJob).where(MerchantReviewJob.id == uuid.UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.updated_at = datetime.now(timezone.utc)
                    if job.notification_id:
                        notif_result = await error_db.execute(
                            select(Notification).where(Notification.id == job.notification_id)
                        )
                        notif = notif_result.scalar_one_or_none()
                        if notif:
                            notif.title = "Could not process merchants — transactions available with original names"
                            notif.updated_at = datetime.now(timezone.utc)
                    await error_db.commit()
        finally:
            await redis.aclose()
```

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest tests/test_canonical_merchants.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/modules/merchant_review/service.py backend/modules/merchant_review/schemas.py backend/jobs/tasks.py backend/tests/test_canonical_merchants.py
git commit -m "feat: add merchant review service + process_merchant_review ARQ job"
```

---

## Task 6: Merchant Review Router + Webhook Trigger

**Files:**
- Create: `backend/modules/merchant_review/router.py`
- Create: `backend/tests/test_merchant_review_api.py`
- Modify: `backend/modules/bank_connect/router.py:263-352` (add trigger)
- Modify: `backend/main.py` (register router)

- [ ] **Step 1: Write test for review API**

`backend/tests/test_merchant_review_api.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_get_review_cards_requires_auth(http_client):
    resp = await http_client.get("/merchant-review/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_review_status(http_client, override_auth, override_db):
    fake_job = {"job_id": "uuid-1", "status": "processing", "total_merchants": None, "reviewed_count": 0}
    with patch("modules.merchant_review.service.get_review_status", new_callable=AsyncMock, return_value=fake_job):
        resp = await http_client.get("/merchant-review/00000000-0000-0000-0000-000000000001/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_skip_review(http_client, override_auth, override_db):
    with patch("modules.merchant_review.service.skip_review", new_callable=AsyncMock, return_value=True):
        resp = await http_client.post("/merchant-review/00000000-0000-0000-0000-000000000001/skip")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_merchant_review_api.py -v
```

- [ ] **Step 3: Add `get_review_status` to service**

Add to `backend/modules/merchant_review/service.py`:

```python
async def get_review_status(
    db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID
) -> dict | None:
    result = await db.execute(
        select(MerchantReviewJob).where(
            MerchantReviewJob.id == job_id,
            MerchantReviewJob.user_id == user_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        return None
    return {
        "job_id": str(job.id),
        "status": job.status,
        "total_merchants": job.total_merchants,
        "reviewed_count": job.reviewed_count,
    }
```

- [ ] **Step 4: Write merchant review router**

`backend/modules/merchant_review/router.py`:

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.merchant_review import service
from modules.merchant_review.schemas import (
    ReviewCardResponse,
    ReviewStatusResponse,
    MerchantApproval,
)

router = APIRouter(prefix="/merchant-review", tags=["merchant-review"])


@router.get("/{job_id}", response_model=list[ReviewCardResponse])
async def get_review_cards(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_review_cards(db, job_id, current_user.id)


@router.get("/{job_id}/status", response_model=ReviewStatusResponse)
async def get_review_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status = await service.get_review_status(db, job_id, current_user.id)
    if not status:
        raise HTTPException(404, "Review job not found")
    return status


@router.patch("/{job_id}/merchants/{canonical_id}")
async def approve_merchant(
    job_id: uuid.UUID,
    canonical_id: uuid.UUID,
    body: MerchantApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.action == "skip":
        return {"ok": True}

    ok = await service.approve_merchant(
        db, current_user.id, job_id, canonical_id, body.display_name, body.category
    )
    if not ok:
        raise HTTPException(404, "Merchant not found")
    return {"ok": True}


@router.post("/{job_id}/skip")
async def skip_review(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await service.skip_review(db, current_user.id, job_id)
    if not ok:
        raise HTTPException(404, "Review job not found")
    return {"ok": True}
```

- [ ] **Step 5: Register router in main.py**

Add to `backend/main.py`:

```python
from modules.merchant_review.router import router as merchant_review_router
```

And in `create_app()`:

```python
app.include_router(merchant_review_router)
```

- [ ] **Step 6: Add trigger to bank_connect webhook**

In `backend/modules/bank_connect/router.py`, after the line `return created, enriched, skipped` in `_process_movements()` (around line 352), modify the caller `handle_connect_callback()` to trigger the review job after processing. Find where `created, enriched, skipped = await _process_movements(...)` is called and add after the commit:

```python
# Trigger merchant review pipeline if new transactions were created
if created > 0:
    from modules.notifications.service import create_notification
    from modules.notifications.models import MerchantReviewJob

    notif = await create_notification(
        db,
        user_id=cred.user_id,
        type="merchant_review",
        title="Processing your transactions...",
        payload={"bank_name": cred.bank_code, "transaction_count": created},
    )
    review_job = MerchantReviewJob(
        user_id=cred.user_id,
        bank_credential_id=cred.id,
        notification_id=notif.id,
    )
    db.add(review_job)
    await db.flush()
    await db.refresh(review_job)

    # Write sync_job_id back to notification payload so frontend can navigate to review
    notif.payload = {**(notif.payload or {}), "sync_job_id": str(review_job.id)}
    await db.commit()

    # Enqueue ARQ job
    from jobs.tasks import process_merchant_review
    redis = aioredis.from_url(settings.redis_url)
    try:
        from arq import ArqRedis
        pool = ArqRedis(redis)
        await pool.enqueue_job("process_merchant_review", str(review_job.id))
    finally:
        await redis.aclose()
```

- [ ] **Step 7: Run tests**

```bash
cd backend && python -m pytest tests/test_merchant_review_api.py -v
```
Expected: All PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/modules/merchant_review/router.py backend/tests/test_merchant_review_api.py backend/modules/bank_connect/router.py backend/main.py
git commit -m "feat: add merchant review API + trigger from bank connect webhook"
```

---

## Task 7: Transaction Display Name — Backend Join

**Files:**
- Modify: `backend/modules/transactions/schemas.py`
- Modify: `backend/modules/transactions/router.py`

- [ ] **Step 1: Add `display_name` to TransactionResponse schema**

In `backend/modules/transactions/schemas.py`, add to the `TransactionResponse` class:

```python
display_name: str | None = None
```

- [ ] **Step 2: Modify transaction query to join canonical merchant**

In `backend/modules/transactions/service.py` (or wherever `get_my_transactions` is defined), update the query to left-join through `merchants` → `canonical_merchants` and include `display_name` in the response. The exact implementation depends on the current query structure, but the pattern is:

```python
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.models import Merchant

# In the query that returns transactions:
# Add outerjoin to resolve display_name
query = (
    select(
        Transaction,
        CanonicalMerchant.display_name.label("display_name"),
    )
    .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
    .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
    .where(...)
)
```

Each row result will have `transaction` + `display_name`. In the response serialization, populate `display_name` from the join, falling back to `raw_merchant_name` if null.

- [ ] **Step 3: Verify the endpoint returns display_name**

```bash
cd backend && python -m pytest tests/test_transactions_api.py -v
```
Expected: Existing tests PASS (display_name is optional, defaults to None).

- [ ] **Step 4: Commit**

```bash
git add backend/modules/transactions/
git commit -m "feat: include display_name in transaction responses via canonical merchant join"
```

---

## Task 8: Frontend — API Client + Hooks

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Create: `frontend/app/lib/hooks/useNotifications.ts`
- Create: `frontend/app/lib/hooks/useMerchantReview.ts`

- [ ] **Step 1: Add types and endpoints to api.ts**

Add to `frontend/app/lib/api.ts` types section:

```typescript
export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  status: string;
  payload: {
    bank_name?: string;
    transaction_count?: number;
    sync_job_id?: string;
    merchant_count?: number;
  } | null;
  created_at: string;
  read_at: string | null;
}

export interface ReviewCard {
  canonical_merchant_id: string;
  display_name: string;
  default_category: string | null;
  llm_suggested_categories: string[];
  raw_names: string[];
  transaction_count: number;
  total_amount: number;
  is_verified: boolean;
}

export interface ReviewStatus {
  job_id: string;
  status: "processing" | "ready" | "completed" | "skipped" | "failed";
  total_merchants: number | null;
  reviewed_count: number;
}
```

Add to the `api` object:

```typescript
// Notifications
getNotifications: () => apiFetch<NotificationItem[]>("/notifications"),
getUnreadCount: () => apiFetch<{ count: number }>("/notifications/unread-count"),
updateNotification: (id: string, status: string) =>
  apiFetch<NotificationItem>(`/notifications/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  }),

// Merchant Review
getReviewCards: (jobId: string) => apiFetch<ReviewCard[]>(`/merchant-review/${jobId}`),
getReviewStatus: (jobId: string) => apiFetch<ReviewStatus>(`/merchant-review/${jobId}/status`),
approveMerchant: (jobId: string, canonicalId: string, data: { display_name?: string; category?: string; action: string }) =>
  apiFetch<{ ok: boolean }>(`/merchant-review/${jobId}/merchants/${canonicalId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  }),
skipReview: (jobId: string) =>
  apiFetch<{ ok: boolean }>(`/merchant-review/${jobId}/skip`, { method: "POST" }),
```

- [ ] **Step 2: Add `display_name` to Transaction interface**

In the existing `Transaction` interface in `api.ts`, add:

```typescript
display_name: string | null;
```

- [ ] **Step 3: Create notification hooks**

`frontend/app/lib/hooks/useNotifications.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.getNotifications(),
    staleTime: 30 * 1000,
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.getUnreadCount(),
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000, // Poll every 30s for badge updates
  });
}

export function useUpdateNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.updateNotification(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
```

- [ ] **Step 4: Create merchant review hooks**

`frontend/app/lib/hooks/useMerchantReview.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useMerchantReview(jobId: string) {
  return useQuery({
    queryKey: ["merchant-review", jobId],
    queryFn: () => api.getReviewCards(jobId),
    enabled: !!jobId,
  });
}

export function useReviewStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["merchant-review", "status", jobId],
    queryFn: () => api.getReviewStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      // Poll every 3s while processing, stop once ready/failed
      const status = query.state.data?.status;
      return status === "processing" ? 3000 : false;
    },
  });
}

export function useApproveMerchant(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ canonicalId, data }: { canonicalId: string; data: { display_name?: string; category?: string; action: string } }) =>
      api.approveMerchant(jobId, canonicalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["merchant-review", jobId] });
    },
  });
}

export function useSkipReview(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.skipReview(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["merchant-review"] });
    },
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useNotifications.ts frontend/app/lib/hooks/useMerchantReview.ts
git commit -m "feat: add notification + merchant review API client and React Query hooks"
```

---

## Task 9: Frontend — Notification Badge in Sidebar

**Files:**
- Create: `frontend/app/(dashboard)/components/NotificationBadge.tsx`
- Modify: `frontend/app/(dashboard)/components/Sidebar.tsx`
- Modify: `frontend/app/(dashboard)/components/BottomNav.tsx`

- [ ] **Step 1: Create NotificationBadge component**

`frontend/app/(dashboard)/components/NotificationBadge.tsx`:

```tsx
"use client";
import Link from "next/link";
import { Bell } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUnreadCount } from "@/app/lib/hooks/useNotifications";

export function NotificationBadge() {
  const pathname = usePathname();
  const { data } = useUnreadCount();
  const count = data?.count ?? 0;
  const active = pathname.startsWith("/notifications");

  return (
    <Link
      href="/notifications"
      className={cn(
        "flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
        count > 0
          ? "bg-amber-50 text-amber-700 border border-amber-200"
          : active
            ? "bg-luka-primary text-white shadow-sm shadow-blue-200"
            : "text-luka-muted hover:bg-blue-50 hover:text-luka-dark"
      )}
    >
      <span className="flex items-center gap-3">
        <Bell size={17} strokeWidth={count > 0 ? 2.2 : 1.8} />
        Notificaciones
      </span>
      {count > 0 && (
        <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
          {count}
        </span>
      )}
    </Link>
  );
}
```

- [ ] **Step 2: Add NotificationBadge to Sidebar**

In `frontend/app/(dashboard)/components/Sidebar.tsx`, add the import:

```typescript
import { NotificationBadge } from "./NotificationBadge";
```

Add `<NotificationBadge />` after the nav map loop (before the closing `</nav>` tag), separated by a divider:

```tsx
{/* After NAV.map() */}
<div className="mt-2 pt-2 border-t border-slate-100">
  <NotificationBadge />
</div>
```

- [ ] **Step 3: Add notification icon to BottomNav**

In `frontend/app/(dashboard)/components/BottomNav.tsx`, add a notification entry to the mobile bottom navigation. Import `Bell` from lucide-react and `useUnreadCount` hook. Add a nav item with the badge dot.

- [ ] **Step 4: Verify in browser**

```bash
cd frontend && npm run dev
```
Open `http://localhost:3000` — the sidebar should show "Notificaciones" below the menu with no badge (0 unread). The item should link to `/notifications`.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/components/NotificationBadge.tsx frontend/app/(dashboard)/components/Sidebar.tsx frontend/app/(dashboard)/components/BottomNav.tsx
git commit -m "feat: add notification badge to sidebar and bottom nav"
```

---

## Task 10: Frontend — Notifications Page

**Files:**
- Create: `frontend/app/(dashboard)/notifications/page.tsx`

- [ ] **Step 1: Create the notifications page**

`frontend/app/(dashboard)/notifications/page.tsx`:

```tsx
"use client";
import { useRouter } from "next/navigation";
import { Store, CheckCircle, AlertTriangle } from "lucide-react";
import { useNotifications, useUpdateNotification } from "@/app/lib/hooks/useNotifications";
import { cn } from "@/lib/utils";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days}d`;
}

const ICONS: Record<string, typeof Store> = {
  merchant_review: Store,
};

export default function NotificationsPage() {
  const router = useRouter();
  const { data: notifications = [], isLoading } = useNotifications();
  const updateNotification = useUpdateNotification();

  const handleReview = (notif: typeof notifications[0]) => {
    const jobId = notif.payload?.sync_job_id;
    if (jobId) {
      updateNotification.mutate({ id: notif.id, status: "read" });
      router.push(`/transactions/review/${jobId}`);
    }
  };

  const handleDismiss = (notif: typeof notifications[0]) => {
    updateNotification.mutate({ id: notif.id, status: "dismissed" });
  };

  const handleMarkAllRead = () => {
    notifications
      .filter((n) => n.status === "unread")
      .forEach((n) => updateNotification.mutate({ id: n.id, status: "read" }));
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-200 rounded w-48" />
        <div className="h-24 bg-slate-100 rounded-xl" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-luka-dark">Notificaciones</h1>
        {notifications.some((n) => n.status === "unread") && (
          <button
            onClick={handleMarkAllRead}
            className="text-sm text-luka-primary hover:underline"
          >
            Marcar todas leídas
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-center py-12 text-luka-muted">
          No tienes notificaciones
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((notif) => {
            const Icon = ICONS[notif.type] ?? AlertTriangle;
            const isUnread = notif.status === "unread";
            const isDone = notif.status === "actioned" || notif.status === "dismissed";

            return (
              <div
                key={notif.id}
                className={cn(
                  "rounded-xl p-4 transition-colors",
                  isUnread
                    ? "bg-blue-50 border border-blue-200"
                    : isDone
                      ? "bg-slate-50 opacity-60"
                      : "bg-white border border-slate-200"
                )}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
                      isUnread ? "bg-luka-primary text-white" : "bg-slate-200 text-slate-500"
                    )}
                  >
                    {isDone ? <CheckCircle size={18} /> : <Icon size={18} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm font-semibold", isUnread ? "text-luka-dark" : "text-slate-500")}>
                      {notif.title}
                    </p>
                    {notif.payload?.bank_name && (
                      <p className="text-xs text-luka-muted mt-0.5">
                        {notif.payload.bank_name}
                        {notif.payload.transaction_count
                          ? ` — ${notif.payload.transaction_count} transacciones importadas`
                          : ""}
                      </p>
                    )}
                    <p className="text-[10px] text-slate-400 mt-1">
                      {timeAgo(notif.created_at)}
                    </p>
                  </div>
                  {isUnread && <div className="w-2 h-2 bg-luka-primary rounded-full mt-1 shrink-0" />}
                </div>

                {isUnread && notif.type === "merchant_review" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => handleReview(notif)}
                      className="px-4 py-2 bg-luka-primary text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Revisar merchants
                    </button>
                    <button
                      onClick={() => handleDismiss(notif)}
                      className="px-4 py-2 border border-slate-200 text-xs text-slate-500 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      Omitir
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify in browser**

Navigate to `http://localhost:3000/notifications` — should show empty state "No tienes notificaciones".

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\\(dashboard\\)/notifications/
git commit -m "feat: add notifications page with review/dismiss actions"
```

---

## Task 11: Frontend — Processing Banner

**Files:**
- Create: `frontend/app/(dashboard)/components/ProcessingBanner.tsx`
- Modify: `frontend/app/(dashboard)/transactions/page.tsx`

- [ ] **Step 1: Create ProcessingBanner component**

`frontend/app/(dashboard)/components/ProcessingBanner.tsx`:

```tsx
"use client";
import { useNotifications } from "@/app/lib/hooks/useNotifications";
import { useReviewStatus } from "@/app/lib/hooks/useMerchantReview";

export function ProcessingBanner() {
  const { data: notifications = [] } = useNotifications();

  // Find the most recent merchant_review notification that's still processing
  const processingNotif = notifications.find(
    (n) => n.type === "merchant_review" && n.status === "unread"
  );

  const jobId = processingNotif?.payload?.sync_job_id ?? null;
  const { data: status } = useReviewStatus(jobId);

  if (!status || status.status !== "processing") return null;

  const bankName = processingNotif?.payload?.bank_name ?? "";
  const txCount = processingNotif?.payload?.transaction_count ?? 0;

  return (
    <div className="bg-green-50 border border-green-300 rounded-xl p-4 mb-4">
      <p className="text-sm font-semibold text-green-800">
        Clasificando tus merchants
      </p>
      <p className="text-xs text-green-700 mt-1">
        Estamos organizando {txCount} transacciones de {bankName}. Estarán
        listas para revisión en unos momentos.
      </p>
      <div className="mt-3 bg-green-200 rounded-full h-1 overflow-hidden">
        <div className="bg-green-500 h-full rounded-full animate-pulse w-3/5" />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add banner to transactions page**

In `frontend/app/(dashboard)/transactions/page.tsx`, import and add `<ProcessingBanner />` at the top of the page content (before the filter panel or summary bar):

```tsx
import { ProcessingBanner } from "../components/ProcessingBanner";

// Inside the return, at the top:
<ProcessingBanner />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\\(dashboard\\)/components/ProcessingBanner.tsx frontend/app/\\(dashboard\\)/transactions/page.tsx
git commit -m "feat: add green processing banner to transactions page during LLM processing"
```

---

## Task 12: Frontend — Tinder-Style Merchant Review UI

**Files:**
- Create: `frontend/app/(dashboard)/components/MerchantCard.tsx`
- Create: `frontend/app/(dashboard)/transactions/review/[jobId]/page.tsx`

- [ ] **Step 1: Create MerchantCard component**

`frontend/app/(dashboard)/components/MerchantCard.tsx`:

```tsx
"use client";
import { useState } from "react";
import { ReviewCard } from "@/app/lib/api";
import { cn } from "@/lib/utils";

const EXPENSE_CATEGORIES = [
  "Alimentación", "Supermercado", "Transporte", "Combustible",
  "Entretenimiento", "Salud", "Farmacia", "Hogar", "Ropa",
  "Tecnología", "Educación", "Viajes", "Servicios", "Otros",
];

const CATEGORY_ICONS: Record<string, string> = {
  Alimentación: "🍽️", Supermercado: "🛒", Transporte: "🚗", Combustible: "⛽",
  Entretenimiento: "🎬", Salud: "🏥", Farmacia: "💊", Hogar: "🏠", Ropa: "👕",
  Tecnología: "💻", Educación: "📚", Viajes: "✈️", Servicios: "🔧", Otros: "📦",
};

function formatAmount(amount: number): string {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Math.abs(amount));
}

interface Props {
  card: ReviewCard;
  onApprove: (displayName?: string, category?: string) => void;
  onSkip: () => void;
}

export function MerchantCard({ card, onApprove, onSkip }: Props) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(card.display_name);
  const [selectedCategory, setSelectedCategory] = useState(
    card.default_category ?? card.llm_suggested_categories[0] ?? ""
  );
  const [showAllCategories, setShowAllCategories] = useState(false);

  const icon = CATEGORY_ICONS[selectedCategory] ?? "📦";
  const suggestions = card.llm_suggested_categories.length > 0
    ? card.llm_suggested_categories
    : [card.default_category].filter(Boolean) as string[];

  const handleSaveApprove = () => {
    const nameChanged = displayName !== card.display_name ? displayName : undefined;
    const catChanged = selectedCategory !== (card.default_category ?? card.llm_suggested_categories[0]) ? selectedCategory : undefined;
    onApprove(nameChanged, catChanged);
  };

  if (editing) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 w-full max-w-[340px] border-2 border-luka-primary">
        <span className="inline-block bg-blue-50 text-luka-primary text-[10px] font-semibold px-2.5 py-1 rounded-md mb-4">
          EDITING
        </span>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Display Name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 w-full border-2 border-luka-primary rounded-xl px-4 py-2.5 text-lg font-bold text-luka-dark bg-slate-50 focus:outline-none"
            autoFocus
          />
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Category
          </label>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {suggestions.map((cat) => (
              <button
                key={cat}
                onClick={() => { setSelectedCategory(cat); setShowAllCategories(false); }}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                  selectedCategory === cat
                    ? "bg-luka-primary text-white"
                    : "bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
                )}
              >
                {cat}
              </button>
            ))}
            {!showAllCategories && (
              <button
                onClick={() => setShowAllCategories(true)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
              >
                Otra...
              </button>
            )}
          </div>
          {showAllCategories && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-slate-100">
              {EXPENSE_CATEGORIES.filter((c) => !suggestions.includes(c)).map((cat) => (
                <button
                  key={cat}
                  onClick={() => { setSelectedCategory(cat); setShowAllCategories(false); }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    selectedCategory === cat
                      ? "bg-luka-primary text-white"
                      : "bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-50 rounded-xl p-3 mb-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">
            Grouped from ({card.transaction_count} txns)
          </p>
          <p className="text-xs text-slate-500 leading-relaxed">
            {card.raw_names.join(", ")}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setEditing(false)}
            className="flex-1 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-500 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveApprove}
            className="flex-[1.5] py-2.5 bg-luka-primary text-white rounded-xl text-sm font-bold hover:bg-blue-700"
          >
            Save & Approve ✓
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 w-full max-w-[340px]">
      <div className="text-center mb-5">
        <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl">
          {icon}
        </div>
        <h2 className="text-xl font-bold text-luka-dark">{card.display_name}</h2>
        {selectedCategory && (
          <span className="inline-block mt-1.5 bg-blue-50 text-luka-primary text-xs font-medium px-3 py-1 rounded-full">
            {selectedCategory}
          </span>
        )}
      </div>

      <div className="bg-slate-50 rounded-xl p-3 mb-4">
        <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
          Raw names found ({card.transaction_count} txns)
        </p>
        <div className="flex flex-wrap gap-1">
          {card.raw_names.map((name) => (
            <span key={name} className="bg-white border border-slate-200 px-2 py-0.5 rounded-md text-[10px] text-slate-500">
              {name}
            </span>
          ))}
        </div>
      </div>

      <div className="flex justify-between text-xs text-slate-400 px-1">
        <span>{card.transaction_count} transactions</span>
        <span>Total: {formatAmount(card.total_amount)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create the review page**

`frontend/app/(dashboard)/transactions/review/[jobId]/page.tsx`:

```tsx
"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { SkipForward, Pencil } from "lucide-react";
import { MerchantCard } from "../../../components/MerchantCard";
import { useMerchantReview, useApproveMerchant, useSkipReview } from "@/app/lib/hooks/useMerchantReview";

export default function ReviewPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const { data: cards = [], isLoading } = useMerchantReview(jobId);
  const approveMutation = useApproveMerchant(jobId);
  const skipMutation = useSkipReview(jobId);
  const [currentIndex, setCurrentIndex] = useState(0);

  const currentCard = cards[currentIndex];
  const nextCard = cards[currentIndex + 1];
  const total = cards.length;
  const progress = total > 0 ? ((currentIndex) / total) * 100 : 0;

  const advance = () => {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
    } else {
      router.push("/transactions");
    }
  };

  const handleApprove = (displayName?: string, category?: string) => {
    if (!currentCard) return;
    approveMutation.mutate(
      {
        canonicalId: currentCard.canonical_merchant_id,
        data: { display_name: displayName, category, action: "approve" },
      },
      { onSuccess: advance }
    );
  };

  const handleSkip = () => {
    if (!currentCard) return;
    approveMutation.mutate(
      {
        canonicalId: currentCard.canonical_merchant_id,
        data: { action: "skip" },
      },
      { onSuccess: advance }
    );
  };

  const handleSkipAll = () => {
    skipMutation.mutate(undefined, {
      onSuccess: () => router.push("/transactions"),
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-4 border-luka-primary border-t-transparent rounded-full" />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-lg font-semibold text-luka-dark">No merchants to review</p>
        <button
          onClick={() => router.push("/transactions")}
          className="mt-4 text-sm text-luka-primary hover:underline"
        >
          Back to transactions
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center pt-4">
      {/* Header */}
      <div className="w-full max-w-[380px] mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Reviewing merchants</span>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400">{currentIndex + 1} / {total}</span>
            <button
              onClick={handleSkipAll}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Skip All
            </button>
          </div>
        </div>
        <div className="bg-slate-200 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-luka-primary h-full rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Card stack */}
      <div className="relative w-[340px] min-h-[360px] mb-6">
        {/* Next card (peek behind) */}
        {nextCard && (
          <div className="absolute top-2 left-3 right-3 bg-white rounded-2xl shadow-sm h-[340px] opacity-60" />
        )}
        {/* Current card */}
        {currentCard && (
          <div className="relative z-10">
            <MerchantCard
              key={currentCard.canonical_merchant_id}
              card={currentCard}
              onApprove={handleApprove}
              onSkip={handleSkip}
            />
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSkip}
          className="w-12 h-12 rounded-full border-2 border-slate-200 flex items-center justify-center text-slate-400 hover:border-slate-300 hover:text-slate-500 transition-colors"
          title="Skip"
        >
          <SkipForward size={18} />
        </button>
        <button
          onClick={() => {}}
          className="w-12 h-12 rounded-full border-2 border-red-200 flex items-center justify-center text-red-400 hover:border-red-300 hover:text-red-500 transition-colors"
          title="Edit"
        >
          <Pencil size={18} />
        </button>
        <button
          onClick={() => handleApprove()}
          className="w-16 h-16 rounded-full bg-green-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-green-200 hover:bg-green-600 transition-colors"
          title="Approve"
        >
          ✓
        </button>
      </div>
      <div className="flex items-center gap-4 mt-2 text-[10px] text-slate-400">
        <span className="w-12 text-center">Skip</span>
        <span className="w-12 text-center">Edit</span>
        <span className="w-16 text-center">Approve</span>
      </div>
    </div>
  );
}
```

**Important:** The Edit button in the action bar must trigger the MerchantCard's edit mode. Add state: `const [editRequested, setEditRequested] = useState(false);` — reset to false when `currentIndex` changes. Pass it as a prop to `MerchantCard`:

```tsx
// In MerchantCard, add prop:
editRequested?: boolean;

// In useEffect:
useEffect(() => { if (editRequested) setEditing(true); }, [editRequested]);
```

And wire the Edit button: `onClick={() => setEditRequested(true)}`.

- [ ] **Step 3: Verify in browser**

Navigate to `http://localhost:3000/transactions/review/some-uuid` — should show "No merchants to review" (no data). The layout, progress bar, and action buttons should render correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\\(dashboard\\)/components/MerchantCard.tsx frontend/app/\\(dashboard\\)/transactions/review/
git commit -m "feat: add Tinder-style merchant review page with swipe cards"
```

---

## Task 13: Frontend — Display Name in Transaction Lists

**Files:**
- Modify: `frontend/app/(dashboard)/components/RecentTransactions.tsx`

- [ ] **Step 1: Update transaction display to use display_name**

In `frontend/app/(dashboard)/components/RecentTransactions.tsx`, find where `raw_merchant_name` is displayed and replace with a fallback pattern:

```tsx
{transaction.display_name ?? transaction.raw_merchant_name}
```

Apply this wherever the merchant name is shown (transaction cards, pending blocks, etc.).

- [ ] **Step 2: Verify in browser**

Transactions should still show raw names (no canonical merchants linked yet). Once the pipeline runs, they'll switch to clean names.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\\(dashboard\\)/components/RecentTransactions.tsx
git commit -m "feat: show canonical display_name in transaction lists with fallback to raw"
```

---

## Task 14: CLI Training Script

**Files:**
- Create: `backend/scripts/train_merchants.py`

- [ ] **Step 1: Create the CLI script**

`backend/scripts/train_merchants.py`:

```python
"""CLI tool for curating the global canonical merchant database.

Usage:
    python scripts/train_merchants.py seed --from-db [--verify] [--dry-run]
    python scripts/train_merchants.py seed --from-file merchants.json [--verify]
    python scripts/train_merchants.py review
    python scripts/train_merchants.py merge "Source Name" "Target Name"
    python scripts/train_merchants.py stats
    python scripts/train_merchants.py regroup
"""
import asyncio
import json
import sys
from pathlib import Path

import click

# Add parent dir to path so we can import backend modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import AsyncSessionLocal  # noqa: E402
from core.config import settings  # noqa: E402


async def _get_db_and_redis():
    import redis.asyncio as aioredis
    db = AsyncSessionLocal()
    redis = aioredis.from_url(settings.redis_url)
    return db, redis


@click.group()
def cli():
    """Luka merchant training CLI."""
    pass


@cli.command()
@click.option("--from-db", "source_db", is_flag=True, help="Pull uncategorized from database")
@click.option("--from-file", "source_file", type=click.Path(exists=True), help="Load from JSON file")
@click.option("--verify", is_flag=True, help="Mark created merchants as verified")
@click.option("--dry-run", is_flag=True, help="Preview without writing")
def seed(source_db, source_file, verify, dry_run):
    """Seed canonical merchants from DB or file."""
    if source_db:
        asyncio.run(_seed_from_db(verify, dry_run))
    elif source_file:
        asyncio.run(_seed_from_file(source_file, verify, dry_run))
    else:
        click.echo("Specify --from-db or --from-file")


async def _seed_from_db(verify: bool, dry_run: bool):
    from sqlalchemy import select
    from modules.transactions.models import Transaction
    from modules.merchants.models import Merchant
    from modules.merchant_review.llm_grouping import group_raw_merchants
    from modules.merchant_review.service import create_canonicals_from_groups
    from modules.merchants.service import lookup_merchant

    db, redis = await _get_db_and_redis()
    try:
        # Get unique raw names without canonical
        result = await db.execute(
            select(Transaction.raw_merchant_name)
            .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
            .where(
                Merchant.canonical_merchant_id.is_(None)
                | Merchant.id.is_(None)
            )
            .distinct()
        )
        raw_names = [r[0] for r in result.all() if r[0]]

        click.echo(f"Found {len(raw_names)} uncategorized raw merchant names")

        if not raw_names:
            click.echo("Nothing to process.")
            return

        # Phase 1: Group
        click.echo("Running LLM grouping...")
        groups = await group_raw_merchants(raw_names)
        click.echo(f"LLM grouped into {len(groups)} canonical merchants")

        for g in groups:
            click.echo(f"  {g['display_name']}: {', '.join(g['raw_names'])}")

        if dry_run:
            click.echo("\n[DRY RUN] No changes written.")
            return

        # Create canonicals
        canonicals = await create_canonicals_from_groups(db, groups)
        await db.commit()

        # Phase 2: Categorize
        click.echo("Categorizing...")
        for i, group in enumerate(groups):
            info = canonicals[i]
            if not info.get("is_new"):
                continue
            first_raw = group["raw_names"][0]
            categories = await lookup_merchant(first_raw, db, redis)
            if categories:
                from modules.merchant_review.models import CanonicalMerchant
                cm = await db.execute(
                    select(CanonicalMerchant).where(CanonicalMerchant.display_name == group["display_name"])
                )
                canonical = cm.scalar_one_or_none()
                if canonical:
                    canonical.default_category = categories[0]
                    if verify:
                        canonical.is_verified = True
                    click.echo(f"  {group['display_name']} → {categories[0]}")

        await db.commit()
        click.echo(f"\nDone! Created {len([c for c in canonicals if c.get('is_new')])} canonical merchants.")
    finally:
        await db.close()
        await redis.aclose()


async def _seed_from_file(path: str, verify: bool, dry_run: bool):
    from sqlalchemy import select
    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    with open(path) as f:
        data = json.load(f)

    click.echo(f"Loaded {len(data)} merchant entries from {path}")

    if dry_run:
        for entry in data:
            click.echo(f"  {entry['display_name']}: {', '.join(entry['raw_names'])} → {entry.get('category', 'N/A')}")
        click.echo("\n[DRY RUN] No changes written.")
        return

    db, _ = await _get_db_and_redis()
    try:
        for entry in data:
            # Get or create canonical
            result = await db.execute(
                select(CanonicalMerchant).where(CanonicalMerchant.display_name == entry["display_name"])
            )
            canonical = result.scalar_one_or_none()
            if not canonical:
                canonical = CanonicalMerchant(
                    display_name=entry["display_name"],
                    default_category=entry.get("category"),
                    is_verified=verify,
                )
                db.add(canonical)
                await db.flush()

            # Link raw names
            for raw_name in entry.get("raw_names", []):
                mr = await db.execute(select(Merchant).where(Merchant.raw_name == raw_name))
                merchant = mr.scalar_one_or_none()
                if merchant:
                    merchant.canonical_merchant_id = canonical.id
                else:
                    db.add(Merchant(raw_name=raw_name, normalized_name=raw_name, canonical_merchant_id=canonical.id))

            click.echo(f"  {entry['display_name']} → {entry.get('category', 'N/A')}")

        await db.commit()
        click.echo(f"\nDone! Processed {len(data)} merchants.")
    finally:
        await db.close()


@cli.command()
def review():
    """Interactive review of unverified canonical merchants."""
    asyncio.run(_interactive_review())


async def _interactive_review():
    from sqlalchemy import select, func
    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant
    from modules.transactions.models import Transaction

    db, _ = await _get_db_and_redis()
    try:
        result = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.is_verified == False).order_by(CanonicalMerchant.created_at)  # noqa: E712
        )
        canonicals = list(result.scalars().all())
        click.echo(f"\n{len(canonicals)} unverified merchants to review\n")

        for cm in canonicals:
            # Get linked raw names
            mr = await db.execute(
                select(Merchant.raw_name).where(Merchant.canonical_merchant_id == cm.id)
            )
            raw_names = [r[0] for r in mr.all()]

            # Get transaction stats
            stats = await db.execute(
                select(func.count(), func.sum(Transaction.amount))
                .where(Transaction.raw_merchant_name.in_(raw_names))
            )
            count, total = stats.one()

            click.echo(f"Display name: {cm.display_name}")
            click.echo(f"Category: {cm.default_category or 'None'}")
            click.echo(f"Grouped from: {', '.join(raw_names)}")
            click.echo(f"Transactions: {count} (total: ${abs(total or 0):,.0f})")

            action = click.prompt(
                "→ (a)pprove  (e)dit  (s)kip  (m)erge into another  (q)uit",
                type=click.Choice(["a", "e", "s", "m", "q"]),
            )

            if action == "q":
                break
            elif action == "a":
                cm.is_verified = True
                await db.commit()
                click.echo("✓ Approved\n")
            elif action == "e":
                new_name = click.prompt("New display name", default=cm.display_name)
                new_cat = click.prompt("New category", default=cm.default_category or "")
                cm.display_name = new_name
                if new_cat:
                    cm.default_category = new_cat
                cm.is_verified = True
                await db.commit()
                click.echo("✓ Updated & approved\n")
            elif action == "m":
                target_name = click.prompt("Merge into (display name)")
                tr = await db.execute(
                    select(CanonicalMerchant).where(CanonicalMerchant.display_name == target_name)
                )
                target = tr.scalar_one_or_none()
                if not target:
                    click.echo(f"Not found: {target_name}\n")
                    continue
                # Move all merchant links
                await db.execute(
                    Merchant.__table__.update()
                    .where(Merchant.canonical_merchant_id == cm.id)
                    .values(canonical_merchant_id=target.id)
                )
                await db.delete(cm)
                await db.commit()
                click.echo(f"✓ Merged into {target_name}\n")
            else:
                click.echo("Skipped\n")
    finally:
        await db.close()


@cli.command()
@click.argument("source")
@click.argument("target")
def merge(source, target):
    """Merge source canonical merchant into target."""
    asyncio.run(_merge(source, target))


async def _merge(source_name: str, target_name: str):
    from sqlalchemy import select
    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    db, _ = await _get_db_and_redis()
    try:
        sr = await db.execute(select(CanonicalMerchant).where(CanonicalMerchant.display_name == source_name))
        source = sr.scalar_one_or_none()
        tr = await db.execute(select(CanonicalMerchant).where(CanonicalMerchant.display_name == target_name))
        target = tr.scalar_one_or_none()

        if not source:
            click.echo(f"Source not found: {source_name}")
            return
        if not target:
            click.echo(f"Target not found: {target_name}")
            return

        await db.execute(
            Merchant.__table__.update()
            .where(Merchant.canonical_merchant_id == source.id)
            .values(canonical_merchant_id=target.id)
        )
        await db.delete(source)
        await db.commit()
        click.echo(f"✓ Merged '{source_name}' into '{target_name}'")
    finally:
        await db.close()


@cli.command()
def stats():
    """Show global merchant database statistics."""
    asyncio.run(_stats())


async def _stats():
    from sqlalchemy import select, func
    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant

    db, _ = await _get_db_and_redis()
    try:
        total = await db.execute(select(func.count()).select_from(CanonicalMerchant))
        verified = await db.execute(
            select(func.count()).select_from(CanonicalMerchant).where(CanonicalMerchant.is_verified == True)  # noqa: E712
        )
        unverified = await db.execute(
            select(func.count()).select_from(CanonicalMerchant).where(CanonicalMerchant.is_verified == False)  # noqa: E712
        )
        linked = await db.execute(
            select(func.count()).select_from(Merchant).where(Merchant.canonical_merchant_id.isnot(None))
        )
        unlinked = await db.execute(
            select(func.count()).select_from(Merchant).where(Merchant.canonical_merchant_id.is_(None))
        )

        click.echo(f"Canonical merchants: {total.scalar_one()}")
        click.echo(f"  Verified: {verified.scalar_one()}")
        click.echo(f"  Unverified: {unverified.scalar_one()}")
        click.echo(f"Merchant raw names: {linked.scalar_one()} linked, {unlinked.scalar_one()} unlinked")
    finally:
        await db.close()


@cli.command()
def regroup():
    """Re-run LLM grouping on all unverified merchants."""
    asyncio.run(_regroup())


async def _regroup():
    from sqlalchemy import select
    from modules.merchant_review.models import CanonicalMerchant
    from modules.merchants.models import Merchant
    from modules.merchant_review.llm_grouping import group_raw_merchants
    from modules.merchant_review.service import create_canonicals_from_groups

    db, _ = await _get_db_and_redis()
    try:
        # Get all unverified canonical merchants
        result = await db.execute(
            select(CanonicalMerchant).where(CanonicalMerchant.is_verified == False)  # noqa: E712
        )
        old_canonicals = list(result.scalars().all())

        # Collect all their raw names
        raw_names = []
        for cm in old_canonicals:
            mr = await db.execute(
                select(Merchant.raw_name).where(Merchant.canonical_merchant_id == cm.id)
            )
            raw_names.extend([r[0] for r in mr.all()])

        if not raw_names:
            click.echo("No unverified merchants to regroup.")
            return

        click.echo(f"Regrouping {len(raw_names)} raw names from {len(old_canonicals)} unverified merchants...")

        # Unlink all
        for cm in old_canonicals:
            await db.execute(
                Merchant.__table__.update()
                .where(Merchant.canonical_merchant_id == cm.id)
                .values(canonical_merchant_id=None)
            )
            await db.delete(cm)
        await db.commit()

        # Re-run grouping
        groups = await group_raw_merchants(raw_names)
        canonicals = await create_canonicals_from_groups(db, groups)
        await db.commit()

        click.echo(f"Regrouped into {len(groups)} canonical merchants:")
        for g in groups:
            click.echo(f"  {g['display_name']}: {', '.join(g['raw_names'])}")
    finally:
        await db.close()


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI loads**

```bash
cd backend && python scripts/train_merchants.py --help
```
Expected: Shows commands: seed, review, merge, stats, regroup.

- [ ] **Step 3: Test stats command**

```bash
cd backend && python scripts/train_merchants.py stats
```
Expected: Shows all zeros (no canonical merchants yet).

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/train_merchants.py
git commit -m "feat: add train_merchants.py CLI — seed, review, merge, stats, regroup"
```

---

## Task 15: Integration Test — End-to-End Flow

**Files:**
- No new files — verify the full pipeline works together

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest -v
```
Expected: All tests pass, no regressions.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Manual E2E test checklist**

Run both backend and frontend locally:
```bash
# Terminal 1
cd backend && uvicorn main:app --reload

# Terminal 2
cd frontend && npm run dev
```

Verify:
1. Sidebar shows "Notificaciones" (no badge)
2. `/notifications` page shows empty state
3. `/transactions` page renders (no processing banner)
4. CLI `python scripts/train_merchants.py stats` works against local DB
5. No console errors in browser

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration test fixes"
```

- [ ] **Step 5: Final commit with all changes pushed**

```bash
git push
```
