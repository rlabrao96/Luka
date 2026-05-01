"""Service layer for the Trips (Viajes) module.

Implements create / list / get / update / archive trip and add / remove
attendee. Phase 4 will layer balance computation, base_currency
re-anchor, and the >$0.50 leave-with-balance check on top of these.

See ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.1, §4.2.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.auth.models import User
from modules.trips.models import Trip, TripAttendee
from modules.trips.schemas import (
    CreateAttendeeInput,
    CreateTripRequest,
    UpdateTripRequest,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_display_name(payload: CreateAttendeeInput) -> str:
    """Pick a display name for an external (non-Luka) attendee."""
    if payload.display_name:
        return payload.display_name
    if payload.email:
        return payload.email.split("@", 1)[0]
    if payload.phone:
        return payload.phone
    # CreateAttendeeInput's validator guarantees at least one of the three is
    # set, so this branch is unreachable in practice.
    return "Guest"


async def _lookup_user(
    db: AsyncSession, *, email: Optional[str] = None, phone: Optional[str] = None
) -> Optional[User]:
    if email:
        res = await db.execute(select(User).where(User.email == email))
        u = res.scalar_one_or_none()
        if u:
            return u
    if phone:
        res = await db.execute(select(User).where(User.phone_whatsapp == phone))
        return res.scalar_one_or_none()
    return None


async def _is_active_member(db: AsyncSession, trip_id: UUID, user_id: UUID) -> bool:
    res = await db.execute(
        select(TripAttendee.id).where(
            TripAttendee.trip_id == trip_id,
            TripAttendee.user_id == user_id,
            TripAttendee.left_at.is_(None),
        )
    )
    return res.first() is not None


async def _is_any_member(db: AsyncSession, trip_id: UUID, user_id: UUID) -> bool:
    """Member ever (active or left). Used for read access."""
    res = await db.execute(
        select(TripAttendee.id).where(
            TripAttendee.trip_id == trip_id,
            TripAttendee.user_id == user_id,
        )
    )
    return res.first() is not None


def _classify_status(start: date, end: date, today: Optional[date] = None) -> str:
    today = today or date.today()
    if today < start:
        return "upcoming"
    if today > end:
        return "past"
    return "active"


def _trip_to_summary(trip: Trip) -> dict:
    """Build the TripResponse payload (Phase 2: hardcoded $0 balance)."""
    return {
        "id": trip.id,
        "name": trip.name,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "base_currency": trip.base_currency,
        "status": _classify_status(trip.start_date, trip.end_date),
        "created_at": trip.created_at,
        # TODO Phase 4: real balance computation per spec §3.4.
        "your_net_balance": Decimal("0"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_trip(db: AsyncSession, creator: User, payload: CreateTripRequest) -> Trip:
    """Create a trip with the creator as a Luka attendee.

    Each ``payload.attendees`` entry resolves to either an existing Luka user
    (by email then phone) or an external stub. Duplicates within the payload
    are de-duplicated by user_id (Luka) — external stubs are kept as given.
    """
    trip = Trip(
        creator_user_id=creator.id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        base_currency=payload.base_currency.upper(),
    )
    db.add(trip)
    await db.flush()

    # Creator is always added first.
    db.add(
        TripAttendee(
            trip_id=trip.id,
            user_id=creator.id,
            display_name=creator.full_name,
        )
    )

    seen_user_ids: set[UUID] = {creator.id}
    for entry in payload.attendees:
        user = await _lookup_user(db, email=entry.email, phone=entry.phone)
        if user is not None:
            if user.id in seen_user_ids:
                continue
            seen_user_ids.add(user.id)
            db.add(
                TripAttendee(
                    trip_id=trip.id,
                    user_id=user.id,
                    display_name=entry.display_name or user.full_name,
                )
            )
        else:
            db.add(
                TripAttendee(
                    trip_id=trip.id,
                    user_id=None,
                    display_name=_resolve_display_name(entry),
                )
            )

    await db.flush()
    await db.refresh(trip)
    return trip


async def list_trips(db: AsyncSession, user: User) -> dict:
    """Return trips bucketed by date window (active / upcoming / past).

    Only trips where the user has an active (``left_at IS NULL``) attendee
    row are included. ``your_net_balance`` is hardcoded to $0 in Phase 2.
    """
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

    buckets: dict[str, list[dict]] = {"active": [], "upcoming": [], "past": []}
    for trip in trips:
        # Archived trips drop out of the date-bucketed list view.
        if trip.status == "archived":
            continue
        buckets[_classify_status(trip.start_date, trip.end_date)].append(_trip_to_summary(trip))
    return buckets


async def get_trip(db: AsyncSession, trip_id: UUID, user: User) -> Trip:
    """Return a trip with attendees + expenses + settlements eager-loaded.

    Raises 404 if the user has never been on the trip (active or left).
    """
    res = await db.execute(
        select(Trip)
        .where(Trip.id == trip_id)
        .options(
            selectinload(Trip.attendees),
            selectinload(Trip.expenses),
        )
    )
    trip = res.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    if not await _is_any_member(db, trip_id, user.id):
        # 404 (not 403) so we don't leak existence to non-members.
        raise HTTPException(status_code=404, detail="Trip not found")

    return trip


async def update_trip(
    db: AsyncSession, trip_id: UUID, user: User, payload: UpdateTripRequest
) -> Trip:
    """Creator-only update of name / dates. ``base_currency`` is Phase 4."""
    if payload.base_currency is not None:
        # Re-anchoring all expense fx_rate_to_base values is a Phase 4 task.
        raise HTTPException(
            status_code=400,
            detail="Changing base_currency is not supported yet (Phase 4).",
        )

    res = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = res.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.creator_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the trip creator can update this trip")

    if payload.name is not None:
        trip.name = payload.name
    if payload.start_date is not None:
        trip.start_date = payload.start_date
    if payload.end_date is not None:
        trip.end_date = payload.end_date

    # Cross-field validation when only one date is provided in the patch.
    if trip.end_date < trip.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    trip.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(trip)
    return trip


async def archive_trip(db: AsyncSession, trip_id: UUID, user: User) -> None:
    """Creator-only. Sets ``status = 'archived'``."""
    res = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = res.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.creator_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the trip creator can archive this trip")
    trip.status = "archived"
    trip.updated_at = datetime.now(timezone.utc)
    await db.flush()


async def add_attendee(
    db: AsyncSession, trip: Trip, user: User, payload: CreateAttendeeInput
) -> TripAttendee:
    """Add an attendee to a trip. Caller must be an active member.

    Resolution order: email → phone → external stub.
    Raises 409 on duplicate active Luka attendee.
    """
    if not await _is_active_member(db, trip.id, user.id):
        raise HTTPException(status_code=403, detail="Only active members can add attendees")

    resolved = await _lookup_user(db, email=payload.email, phone=payload.phone)
    if resolved is not None:
        # Reject if this Luka user already has an active row on the trip.
        existing = await db.execute(
            select(TripAttendee).where(
                TripAttendee.trip_id == trip.id,
                TripAttendee.user_id == resolved.id,
                TripAttendee.left_at.is_(None),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="User is already on this trip")
        attendee = TripAttendee(
            trip_id=trip.id,
            user_id=resolved.id,
            display_name=payload.display_name or resolved.full_name,
        )
    else:
        attendee = TripAttendee(
            trip_id=trip.id,
            user_id=None,
            display_name=_resolve_display_name(payload),
        )

    db.add(attendee)
    await db.flush()
    await db.refresh(attendee)
    return attendee


async def remove_attendee(db: AsyncSession, trip_id: UUID, attendee_id: UUID, user: User) -> None:
    """Soft-remove an attendee (sets ``left_at = now()``).

    Permission rules:
    - Self-leave (attendee resolves to caller) — allowed.
    - Otherwise — only the trip's creator can remove.

    Phase 4 will add the >$0.50-balance pre-check on top of this.
    """
    res = await db.execute(
        select(TripAttendee).where(
            TripAttendee.id == attendee_id,
            TripAttendee.trip_id == trip_id,
        )
    )
    attendee = res.scalar_one_or_none()
    if attendee is None:
        raise HTTPException(status_code=404, detail="Attendee not on this trip")

    trip_res = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = trip_res.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")

    is_self = attendee.user_id is not None and attendee.user_id == user.id
    is_creator = trip.creator_user_id == user.id
    if not (is_self or is_creator):
        raise HTTPException(
            status_code=403,
            detail="Only the trip creator or the attendee themselves can remove this attendee",
        )

    if attendee.left_at is None:
        attendee.left_at = datetime.now(timezone.utc)
        await db.flush()
