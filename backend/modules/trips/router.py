"""FastAPI router for the Trips (Viajes) module — Phase 2 (Tasks 2.5 + 2.6).

Endpoints implemented:

- ``GET    /trips``                           — list user's trips bucketed by date
- ``POST   /trips``                           — create a trip (creator becomes attendee)
- ``GET    /trips/{trip_id}``                 — trip detail with attendees
- ``PATCH  /trips/{trip_id}``                 — creator-only name/date edits
- ``DELETE /trips/{trip_id}``                 — creator-only archive (soft)
- ``POST   /trips/{trip_id}/attendees``       — add Luka or external attendee
- ``DELETE /trips/{trip_id}/attendees/{aid}`` — self-leave or creator-remove

All endpoints require an authenticated user with ``feature_trips_enabled=True``
(403 otherwise). Phase 4 will layer balance computation, settle suggestions,
base-currency change, and the >$0.50 leave-with-balance check on top of these
endpoints. See ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md``
§4.1, §4.2.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.rate_limit import limiter
from core.security import get_current_user
from modules.auth.models import User
from modules.trips import service
from modules.trips.balances import compute_balances, smart_settle_plan, your_net_balance
from modules.trips.models import Trip, TripAttendee, TripExpense, TripSettlement
from modules.trips.schemas import (
    AttendeeResponse,
    CreateAttendeeInput,
    CreateExpenseRequest,
    CreateSettlementRequest,
    CreateTripRequest,
    ExpenseResponse,
    InviteLinkResponse,
    SettlementResponse,
    SplitResponse,
    SuggestedTransaction,
    TripDetailResponse,
    TripListResponse,
    TripPreviewResponse,
    TripResponse,
    UpdateExpenseRequest,
    UpdateTripRequest,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload


router = APIRouter(prefix="/trips", tags=["trips"])


# ---------------------------------------------------------------------------
# Feature-flag dependency
# ---------------------------------------------------------------------------


async def require_trips_feature(user: User = Depends(get_current_user)) -> User:
    """Gate every trips endpoint on the per-user feature flag."""
    if not user.feature_trips_enabled:
        raise HTTPException(status_code=403, detail="feature_trips_enabled is off")
    return user


# ---------------------------------------------------------------------------
# Internal serialization helpers
# ---------------------------------------------------------------------------


def _to_trip_response(trip: Trip, your_net_balance: Decimal | None = None) -> TripResponse:
    """Build a ``TripResponse`` from a ``Trip`` ORM row.

    ``your_net_balance`` is computed by the caller via ``compute_balances``.
    """
    summary = service._trip_to_summary(trip)
    if your_net_balance is not None:
        summary["your_net_balance"] = your_net_balance
    return TripResponse(**summary)


def _to_settlement_response(s: TripSettlement) -> SettlementResponse:
    return SettlementResponse(
        id=s.id,
        trip_id=s.trip_id,
        from_attendee_id=s.from_attendee_id,
        to_attendee_id=s.to_attendee_id,
        amount=s.amount,
        currency=s.currency,
        fx_rate_to_base=s.fx_rate_to_base,
        settled_at=s.settled_at,
        transaction_id=s.transaction_id,
        write_off=s.write_off,
        created_at=s.created_at,
    )


async def _to_trip_detail(trip: Trip, user: User, db) -> TripDetailResponse:
    """Build full trip detail incl. balances + settle_suggestions + settlements."""
    summary: dict[str, Any] = service._trip_to_summary(trip)

    # Live (non-deleted) expenses with eager-loaded splits.
    exp_rows = (
        (
            await db.execute(
                select(TripExpense)
                .options(selectinload(TripExpense.splits))
                .where(
                    TripExpense.trip_id == trip.id,
                    TripExpense.deleted_at.is_(None),
                )
                .order_by(TripExpense.expense_date.desc(), TripExpense.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    settlements = (
        (
            await db.execute(
                select(TripSettlement)
                .where(TripSettlement.trip_id == trip.id)
                .order_by(TripSettlement.settled_at.desc())
            )
        )
        .scalars()
        .all()
    )

    balances = await compute_balances(trip.id, db)
    suggestions = smart_settle_plan(balances, trip.base_currency)

    # Caller's own net (sum across their attendee rows on this trip).
    own_ids = {a.id for a in trip.attendees if a.user_id == user.id}
    your_net = sum((b.net_in_base for b in balances if b.attendee_id in own_ids), Decimal("0"))
    summary["your_net_balance"] = your_net

    return TripDetailResponse(
        **summary,
        attendees=[AttendeeResponse.model_validate(a) for a in trip.attendees],
        expenses=[_to_expense_response(e) for e in exp_rows],
        settlements=[_to_settlement_response(s) for s in settlements],
        balances=balances,
        settle_suggestions=suggestions,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=TripListResponse)
async def list_trips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripListResponse:
    buckets = await service.list_trips(db, user)
    return TripListResponse(
        active=[TripResponse(**t) for t in buckets["active"]],
        upcoming=[TripResponse(**t) for t in buckets["upcoming"]],
        past=[TripResponse(**t) for t in buckets["past"]],
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: CreateTripRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripResponse:
    trip = await service.create_trip(db, creator=user, payload=payload)
    await db.commit()
    await db.refresh(trip)
    return _to_trip_response(trip, your_net_balance=Decimal("0"))


# ---------------------------------------------------------------------------
# Invite links (Phase 5)
#
# These two routes (``/preview/{token}`` and ``/join/{token}``) MUST be
# declared before any ``/{trip_id}/...`` routes so FastAPI's path matcher
# doesn't try to coerce the token into a UUID. Tokens are URL-safe base64
# (43 chars), so a strict UUID match would 422 — but declaring these first
# is the bullet-proof guarantee.
# ---------------------------------------------------------------------------


@router.get("/preview/{token}", response_model=TripPreviewResponse)
@limiter.limit("10/minute")
async def preview_invite(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripPreviewResponse:
    """Return name + dates + attendee count for a valid invite token.

    Auth-required (anti-spam). Read-only — does NOT refresh expiry, does
    NOT add the caller as an attendee. Rate-limited per IP.
    """
    trip = await service.lookup_trip_by_token(db, token)
    attendee_count = (
        await db.execute(
            select(func.count())
            .select_from(TripAttendee)
            .where(
                TripAttendee.trip_id == trip.id,
                TripAttendee.left_at.is_(None),
            )
        )
    ).scalar()
    return TripPreviewResponse(
        name=trip.name,
        start_date=trip.start_date,
        end_date=trip.end_date,
        attendee_count=attendee_count or 0,
        base_currency=trip.base_currency,
    )


@router.post("/join/{token}", response_model=TripDetailResponse)
@limiter.limit("10/minute")
async def join_via_invite(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripDetailResponse:
    """Add the caller to the trip behind ``token`` and return full detail.

    Idempotent: re-joining is a no-op for already-active members. The
    invite expiry slides forward by 30 days on every successful join.
    Rate-limited per IP.
    """
    trip = await service.accept_invite(db, token, user)
    await db.commit()
    # Re-fetch with eager-loaded attendees so ``_to_trip_detail`` can use them.
    full_trip = await service.get_trip(db, trip.id, user)
    return await _to_trip_detail(full_trip, user, db)


@router.get("/{trip_id}", response_model=TripDetailResponse)
async def get_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripDetailResponse:
    trip = await service.get_trip(db, trip_id, user)
    return await _to_trip_detail(trip, user, db)


@router.post("/{trip_id}/invite-link", response_model=InviteLinkResponse)
async def create_invite_link(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> InviteLinkResponse:
    """Creator-only. Generate (or rotate) the trip's invite link.

    The raw token is shown exactly once in the response — only its sha256
    hash is persisted. Rotation overwrites the prior hash, immediately
    killing any previously-distributed link.
    """
    raw_token, expires_at = await service.generate_invite_link(db, trip_id, user)
    await db.commit()
    url = f"{settings.frontend_url}/viajes/join/{raw_token}"
    return InviteLinkResponse(token=raw_token, url=url, expires_at=expires_at)


@router.delete("/{trip_id}/invite-link", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite_link(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    """Creator-only. Clear the invite hash + expiry (kills the live link)."""
    await service.revoke_invite_link(db, trip_id, user)
    await db.commit()
    return None


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: UUID,
    payload: UpdateTripRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripResponse:
    trip = await service.update_trip(db, trip_id, user, payload)
    await db.commit()
    await db.refresh(trip)
    net = await your_net_balance(trip, user.id, db)
    return _to_trip_response(trip, your_net_balance=net)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.archive_trip(db, trip_id, user)
    await db.commit()
    return None


@router.post(
    "/{trip_id}/attendees",
    response_model=AttendeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_attendee(
    trip_id: UUID,
    payload: CreateAttendeeInput,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> AttendeeResponse:
    # ``get_trip`` enforces membership (404 otherwise) and eager-loads attendees.
    trip = await service.get_trip(db, trip_id, user)
    attendee = await service.add_attendee(db, trip, user, payload)
    await db.commit()
    await db.refresh(attendee)
    return AttendeeResponse.model_validate(attendee)


@router.delete(
    "/{trip_id}/attendees/{attendee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_attendee(
    trip_id: UUID,
    attendee_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.remove_attendee(db, trip_id, attendee_id, user)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


def _to_expense_response(exp) -> ExpenseResponse:
    return ExpenseResponse(
        id=exp.id,
        trip_id=exp.trip_id,
        payer_attendee_id=exp.payer_attendee_id,
        description=exp.description,
        amount=exp.amount,
        currency=exp.currency,
        expense_date=exp.expense_date,
        transaction_id=exp.transaction_id,
        fx_rate_to_base=exp.fx_rate_to_base,
        version=exp.version,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
        splits=[SplitResponse.model_validate(s) for s in exp.splits],
    )


@router.get("/{trip_id}/export")
async def export_trip_csv(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
):
    """Download the trip ledger (expenses + splits + settlements) as CSV."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    trip = await service.get_trip(db, trip_id, user)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from modules.trips.models import TripAttendee, TripExpense, TripSettlement

    attendees = {
        a.id: a.display_name
        for a in (
            await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip.id))
        ).scalars()
    }
    expenses = (
        (
            await db.execute(
                select(TripExpense)
                .options(selectinload(TripExpense.splits))
                .where(TripExpense.trip_id == trip.id, TripExpense.deleted_at.is_(None))
                .order_by(TripExpense.expense_date)
            )
        )
        .scalars()
        .all()
    )
    settlements = (
        (
            await db.execute(
                select(TripSettlement)
                .where(TripSettlement.trip_id == trip.id)
                .order_by(TripSettlement.settled_at)
            )
        )
        .scalars()
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["registro", "fecha", "descripcion", "pagador/de", "para", "monto", "moneda", "detalle"]
    )
    for e in expenses:
        writer.writerow(
            [
                "gasto",
                e.expense_date.isoformat(),
                e.description,
                attendees.get(e.payer_attendee_id, ""),
                "",
                str(e.amount),
                e.currency,
                "",
            ]
        )
        for s in e.splits:
            writer.writerow(
                [
                    "parte",
                    e.expense_date.isoformat(),
                    e.description,
                    "",
                    attendees.get(s.attendee_id, ""),
                    str(s.share_amount),
                    e.currency,
                    s.share_type,
                ]
            )
    for st in settlements:
        writer.writerow(
            [
                "pago",
                st.settled_at.date().isoformat() if st.settled_at else "",
                "ajuste" if st.write_off else "pago entre asistentes",
                attendees.get(st.from_attendee_id, ""),
                attendees.get(st.to_attendee_id, ""),
                str(st.amount),
                st.currency,
                "write-off" if st.write_off else "",
            ]
        )

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in trip.name)[:40].strip()
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="luka-viaje-{safe_name or trip_id}.csv"'
        },
    )


@router.post(
    "/{trip_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    trip_id: UUID,
    payload: CreateExpenseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> ExpenseResponse:
    # ``get_trip`` enforces membership (404 otherwise).
    trip = await service.get_trip(db, trip_id, user, require_active=True)
    expense = await service.create_expense(db, trip, user, payload)
    await db.commit()
    return _to_expense_response(expense)


@router.patch("/{trip_id}/expenses/{expense_id}", response_model=ExpenseResponse)
async def patch_expense(
    trip_id: UUID,
    expense_id: UUID,
    payload: UpdateExpenseRequest,
    if_match: int = Header(..., alias="If-Match"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> ExpenseResponse:
    # ``get_trip`` enforces membership (404 otherwise).
    await service.get_trip(db, trip_id, user, require_active=True)
    expense = await service.update_expense(db, trip_id, expense_id, user, payload, if_match)
    await db.commit()
    return _to_expense_response(expense)


@router.delete(
    "/{trip_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_expense(
    trip_id: UUID,
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.get_trip(db, trip_id, user, require_active=True)
    await service.delete_expense(db, trip_id, expense_id, user)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Settlements (Phase 4 Task 4.4)
# ---------------------------------------------------------------------------


@router.post(
    "/{trip_id}/settlements",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_settlement(
    trip_id: UUID,
    payload: CreateSettlementRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> SettlementResponse:
    trip = await service.get_trip(db, trip_id, user, require_active=True)
    settlement = await service.create_settlement(db, trip, user, payload)
    await db.commit()
    return _to_settlement_response(settlement)


# ---------------------------------------------------------------------------
# Force-remove with write-off (Phase 4 Task 4.6)
# ---------------------------------------------------------------------------


@router.post(
    "/{trip_id}/attendees/{attendee_id}/force-remove",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def force_remove_attendee(
    trip_id: UUID,
    attendee_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.force_remove_attendee(db, trip_id, attendee_id, user)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Phase 6 — Suggestions inbox (Task 6.1)
# ---------------------------------------------------------------------------


@router.get(
    "/{trip_id}/suggested-transactions",
    response_model=list[SuggestedTransaction],
)
async def list_suggested_transactions(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> list[SuggestedTransaction]:
    rows = await service.get_suggested_transactions(db, trip_id, user)
    return [SuggestedTransaction(**r) for r in rows]


@router.post(
    "/{trip_id}/suggested-transactions/{transaction_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dismiss_suggested_transaction(
    trip_id: UUID,
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.dismiss_suggestion(db, trip_id, transaction_id, user)
    await db.commit()
    return None


@router.delete(
    "/{trip_id}/suggested-transactions/{transaction_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def undismiss_suggested_transaction(
    trip_id: UUID,
    transaction_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.undismiss_suggestion(db, trip_id, transaction_id, user)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Phase 6 — Settlement-suggestion confirm/dismiss (Tasks 6.2 + 6.3)
# ---------------------------------------------------------------------------


class _ConfirmSettlementRequest(BaseModel):
    trip_id: UUID
    from_attendee_id: UUID
    to_attendee_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    transaction_id: UUID


class _DismissSettlementRequest(BaseModel):
    transaction_id: UUID


@router.post(
    "/settlement-suggestions/confirm",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_settlement_suggestion(
    payload: _ConfirmSettlementRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> SettlementResponse:
    """Promote an auto-detect suggestion into a real ``trip_settlements`` row.

    Membership is enforced by ``service.get_trip``; ``service.create_settlement``
    handles attendee + currency validation and links ``transaction_id``.
    """
    trip = await service.get_trip(db, payload.trip_id, user, require_active=True)
    settlement = await service.create_settlement(
        db,
        trip,
        user,
        CreateSettlementRequest(
            from_attendee_id=payload.from_attendee_id,
            to_attendee_id=payload.to_attendee_id,
            amount=payload.amount,
            currency=payload.currency,
            transaction_id=payload.transaction_id,
        ),
    )
    await db.commit()
    return _to_settlement_response(settlement)


@router.post(
    "/settlement-suggestions/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def dismiss_settlement_suggestion(
    payload: _DismissSettlementRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.dismiss_settlement_suggestion(db, payload.transaction_id, user)
    await db.commit()
    return None
