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

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.trips import service
from modules.trips.balances import compute_balances, smart_settle_plan
from modules.trips.models import Trip, TripExpense, TripSettlement
from modules.trips.schemas import (
    AttendeeResponse,
    CreateAttendeeInput,
    CreateExpenseRequest,
    CreateSettlementRequest,
    CreateTripRequest,
    ExpenseResponse,
    SettlementResponse,
    SplitResponse,
    TripDetailResponse,
    TripListResponse,
    TripResponse,
    UpdateExpenseRequest,
    UpdateTripRequest,
)
from sqlalchemy import select
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


async def _your_net_for_trip(trip: Trip, user: User, db) -> Decimal:
    from modules.trips.models import TripAttendee

    balances = await compute_balances(trip.id, db)
    res = await db.execute(
        select(TripAttendee.id).where(
            TripAttendee.trip_id == trip.id,
            TripAttendee.user_id == user.id,
        )
    )
    own_ids = {row[0] for row in res.all()}
    return sum((b.net_in_base for b in balances if b.attendee_id in own_ids), Decimal("0"))


@router.get("", response_model=TripListResponse)
async def list_trips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripListResponse:
    # Re-fetch trip rows so we can compute balances per trip (the service
    # returns dicts already; we need ORM rows here to call ``compute_balances``).
    from modules.trips.models import TripAttendee

    res = await db.execute(
        select(Trip)
        .join(TripAttendee, TripAttendee.trip_id == Trip.id)
        .where(
            TripAttendee.user_id == user.id,
            TripAttendee.left_at.is_(None),
        )
        .order_by(Trip.start_date.desc())
    )
    trips = res.scalars().unique().all()

    buckets: dict[str, list[TripResponse]] = {"active": [], "upcoming": [], "past": []}
    for trip in trips:
        if trip.status == "archived":
            continue
        net = await _your_net_for_trip(trip, user, db)
        bucket_key = service._classify_status(trip.start_date, trip.end_date)
        buckets[bucket_key].append(_to_trip_response(trip, your_net_balance=net))

    return TripListResponse(
        active=buckets["active"], upcoming=buckets["upcoming"], past=buckets["past"]
    )


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    payload: CreateTripRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripResponse:
    trip = await service.create_trip(db, creator=user, payload=payload)
    return _to_trip_response(trip, your_net_balance=Decimal("0"))


@router.get("/{trip_id}", response_model=TripDetailResponse)
async def get_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripDetailResponse:
    trip = await service.get_trip(db, trip_id, user)
    return await _to_trip_detail(trip, user, db)


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: UUID,
    payload: UpdateTripRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripResponse:
    trip = await service.update_trip(db, trip_id, user, payload)
    net = await _your_net_for_trip(trip, user, db)
    return _to_trip_response(trip, your_net_balance=net)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> None:
    await service.archive_trip(db, trip_id, user)
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
    trip = await service.get_trip(db, trip_id, user)
    expense = await service.create_expense(db, trip, user, payload)
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
    await service.get_trip(db, trip_id, user)
    expense = await service.update_expense(db, trip_id, expense_id, user, payload, if_match)
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
    await service.get_trip(db, trip_id, user)
    await service.delete_expense(db, trip_id, expense_id, user)
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
    trip = await service.get_trip(db, trip_id, user)
    settlement = await service.create_settlement(db, trip, user, payload)
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
    return None
