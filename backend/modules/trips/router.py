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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.trips import service
from modules.trips.models import Trip
from modules.trips.schemas import (
    AttendeeResponse,
    CreateAttendeeInput,
    CreateExpenseRequest,
    CreateTripRequest,
    ExpenseResponse,
    SplitResponse,
    TripDetailResponse,
    TripListResponse,
    TripResponse,
    UpdateTripRequest,
)


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

    Phase 2 hardcodes ``your_net_balance`` to 0 — Phase 4 will compute it.
    Status is derived the same way as the service helper.
    """
    summary = service._trip_to_summary(trip)
    if your_net_balance is not None:
        summary["your_net_balance"] = your_net_balance
    return TripResponse(**summary)


def _to_trip_detail(trip: Trip) -> TripDetailResponse:
    summary: dict[str, Any] = service._trip_to_summary(trip)
    return TripDetailResponse(
        **summary,
        attendees=[AttendeeResponse.model_validate(a) for a in trip.attendees],
        # Phase 4: balances + settle_suggestions + settlements get filled in.
        expenses=[],
        settlements=[],
        balances=[],
        settle_suggestions=[],
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
    return _to_trip_response(trip, your_net_balance=Decimal("0"))


@router.get("/{trip_id}", response_model=TripDetailResponse)
async def get_trip(
    trip_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripDetailResponse:
    trip = await service.get_trip(db, trip_id, user)
    return _to_trip_detail(trip)


@router.patch("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: UUID,
    payload: UpdateTripRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_trips_feature),
) -> TripResponse:
    trip = await service.update_trip(db, trip_id, user, payload)
    return _to_trip_response(trip, your_net_balance=Decimal("0"))


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
