"""
Local-only admin router for merchant training UI.
Served at /train — no auth required (dev tool only).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.models import Merchant
from modules.transactions.models import Transaction

router = APIRouter(prefix="/train", tags=["training"])


# ── Schemas ────────────────────────────────────────────────


class TrainCard(BaseModel):
    id: str
    display_name: str
    default_category: str | None = None
    is_verified: bool = False
    raw_names: list[str] = []
    transaction_count: int = 0
    total_amount: float = 0.0


class ApproveBody(BaseModel):
    display_name: str | None = None
    category: str | None = None


class MergeBody(BaseModel):
    target_id: str


# ── Endpoints ──────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
async def train_ui():
    """Serve the single-page training UI."""
    html_path = Path(__file__).parent / "train_ui.html"
    return HTMLResponse(html_path.read_text())


@router.get("/merchants")
async def list_merchants(
    filter: str = "unverified",
    search: str = "",
    db: AsyncSession = Depends(get_db),
):
    """List canonical merchants for training. Single query with aggregation."""
    # Single query: canonical + aggregated raw_names + transaction stats
    query = (
        select(
            CanonicalMerchant.id,
            CanonicalMerchant.display_name,
            CanonicalMerchant.default_category,
            CanonicalMerchant.is_verified,
            func.array_agg(func.distinct(Merchant.raw_name)).label("raw_names"),
            func.count(func.distinct(Transaction.id)).label("txn_count"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
        )
        .outerjoin(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .outerjoin(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
        .group_by(CanonicalMerchant.id)
    )

    if filter == "unverified":
        query = query.where(CanonicalMerchant.is_verified == False)  # noqa: E712
    elif filter == "verified":
        query = query.where(CanonicalMerchant.is_verified == True)  # noqa: E712

    if search:
        query = query.where(CanonicalMerchant.display_name.ilike(f"%{search}%"))

    query = query.order_by(CanonicalMerchant.display_name)
    result = await db.execute(query)
    rows = result.all()

    return [
        TrainCard(
            id=str(row.id),
            display_name=row.display_name,
            default_category=row.default_category,
            is_verified=row.is_verified,
            raw_names=[n for n in (row.raw_names or []) if n is not None],
            transaction_count=row.txn_count or 0,
            total_amount=float(row.total_amount or 0),
        )
        for row in rows
    ]


@router.patch("/merchants/{merchant_id}")
async def approve_merchant(
    merchant_id: uuid.UUID,
    body: ApproveBody,
    db: AsyncSession = Depends(get_db),
):
    """Approve/edit a canonical merchant."""
    result = await db.execute(select(CanonicalMerchant).where(CanonicalMerchant.id == merchant_id))
    cm = result.scalar_one_or_none()
    if not cm:
        raise HTTPException(404, "Not found")

    if body.display_name:
        cm.display_name = body.display_name
    if body.category:
        cm.default_category = body.category
    cm.is_verified = True
    cm.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/merchants/{merchant_id}/merge")
async def merge_merchant(
    merchant_id: uuid.UUID,
    body: MergeBody,
    db: AsyncSession = Depends(get_db),
):
    """Merge source into target canonical merchant."""
    source = await db.execute(select(CanonicalMerchant).where(CanonicalMerchant.id == merchant_id))
    src = source.scalar_one_or_none()
    if not src:
        raise HTTPException(404, "Source not found")

    target = await db.execute(
        select(CanonicalMerchant).where(CanonicalMerchant.id == uuid.UUID(body.target_id))
    )
    tgt = target.scalar_one_or_none()
    if not tgt:
        raise HTTPException(404, "Target not found")

    # Move all merchant links
    await db.execute(
        Merchant.__table__.update()
        .where(Merchant.canonical_merchant_id == src.id)
        .values(canonical_merchant_id=tgt.id)
    )
    await db.delete(src)
    await db.commit()
    return {"ok": True, "merged_into": tgt.display_name}


@router.delete("/merchants/{merchant_id}")
async def delete_merchant(
    merchant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a canonical merchant and unlink its raw names."""
    result = await db.execute(select(CanonicalMerchant).where(CanonicalMerchant.id == merchant_id))
    cm = result.scalar_one_or_none()
    if not cm:
        raise HTTPException(404, "Not found")

    # Unlink merchants
    await db.execute(
        Merchant.__table__.update()
        .where(Merchant.canonical_merchant_id == cm.id)
        .values(canonical_merchant_id=None)
    )
    await db.delete(cm)
    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Global merchant DB stats."""
    total = (await db.execute(select(func.count()).select_from(CanonicalMerchant))).scalar_one()
    verified = (
        await db.execute(
            select(func.count())
            .select_from(CanonicalMerchant)
            .where(CanonicalMerchant.is_verified == True)  # noqa: E712
        )
    ).scalar_one()
    linked = (
        await db.execute(
            select(func.count())
            .select_from(Merchant)
            .where(Merchant.canonical_merchant_id.isnot(None))
        )
    ).scalar_one()
    unlinked = (
        await db.execute(
            select(func.count())
            .select_from(Merchant)
            .where(Merchant.canonical_merchant_id.is_(None))
        )
    ).scalar_one()

    return {
        "total": total,
        "verified": verified,
        "unverified": total - verified,
        "linked": linked,
        "unlinked": unlinked,
    }
