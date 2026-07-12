"""Service layer for the Trips (Viajes) module.

Implements create / list / get / update / archive trip and add / remove
attendee. Phase 4 will layer balance computation, base_currency
re-anchor, and the >$0.50 leave-with-balance check on top of these.

See ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.1, §4.2.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_FLOOR, Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.auth.models import User
from modules.trips.models import (
    Trip,
    TripAttendee,
    TripExpense,
    TripExpenseSplit,
    TripSettlement,
    TripSettlementDismissal,
    TripSuggestionDismissal,
)
from modules.trips.schemas import (
    CreateAttendeeInput,
    CreateExpenseRequest,
    CreateSettlementRequest,
    CreateTripRequest,
    ExpenseResponse,
    SplitInput,
    UpdateExpenseRequest,
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


def _trip_to_summary(trip: Trip, your_net_balance: Decimal = Decimal("0")) -> dict:
    """Build the TripResponse payload."""
    return {
        "id": trip.id,
        "name": trip.name,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "base_currency": trip.base_currency,
        "status": _classify_status(trip.start_date, trip.end_date),
        "creator_user_id": trip.creator_user_id,
        "created_at": trip.created_at,
        "your_net_balance": your_net_balance,
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
    """Return trips bucketed by date window (active / upcoming / past) with
    the caller's REAL net balance per trip.

    Only trips where the user has an active (``left_at IS NULL``) attendee
    row are included. This is the single implementation behind GET /trips —
    an earlier duplicate lived in the router while this one hardcoded $0.
    """
    from modules.trips.balances import your_net_balance  # local: avoids cycle

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
        net = await your_net_balance(trip, user.id, db)
        buckets[_classify_status(trip.start_date, trip.end_date)].append(
            _trip_to_summary(trip, your_net_balance=net)
        )
    return buckets


async def get_trip(
    db: AsyncSession, trip_id: UUID, user: User, *, require_active: bool = False
) -> Trip:
    """Return a trip with attendees + expenses + settlements eager-loaded.

    Raises 404 if the user has never been on the trip (active or left).
    With ``require_active=True`` (every MUTATION route), a member who left or
    was removed gets 403 — departed attendees keep read access to the history
    but must never be able to rewrite the ledger.
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

    if require_active and not await _is_active_member(db, trip_id, user.id):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "left_members_cannot_modify",
                "message": "You are no longer an active member of this trip.",
            },
        )

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


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


_CENT = Decimal("0.01")

# Currency scaling lives in modules.currencies.units — single source of truth
# shared with the Plaid mapper and Luka Connect (drift here means 100× money).
from modules.currencies.units import major_unit_quantum, to_major_units  # noqa: E402


def _txn_amount_to_major(amount: Decimal, currency: str) -> Decimal:
    """Convert ``transactions.amount`` storage units → trip-ledger major units.

    Transactions store integer minor units (cents for 2-decimal currencies,
    whole units for zero-decimal ones). Trip expenses store major units
    (``Numeric(14, 2)``).
    """
    return to_major_units(Decimal(amount), currency).quantize(major_unit_quantum(currency))


def _floor_step(value: Decimal, currency: str) -> Decimal:
    """Quantize to the currency's payable step (1 for CLP/COP, 0.01 for USD),
    rounding toward negative infinity (== floor for positives)."""
    return value.quantize(major_unit_quantum(currency), rounding=ROUND_FLOOR)


def _normalize_splits(
    splits: list[SplitInput], amount: Decimal, payer_attendee_id: UUID, currency: str
) -> list[dict]:
    """Compute per-attendee share_amounts so they sum exactly to ``amount``.

    Shares are quantized to the currency's payable step — a 10.000 CLP dinner
    split 3 ways yields 3.334/3.333/3.333, never fractional pesos.

    Modes (must be consistent across all splits):
      - ``equal``           : amount / n, payer absorbs floor remainder.
      - ``custom_amount``   : caller supplies share_amount; sum must == amount.
      - ``custom_percent``  : caller supplies share_percent; server computes
                              floor(amount * pct / 100); payer absorbs residual.
    """
    if not splits:
        raise HTTPException(status_code=422, detail="at least one split required")

    split_ids = [s.attendee_id for s in splits]
    if len(split_ids) != len(set(split_ids)):
        # Duplicates would silently double-charge that attendee.
        raise HTTPException(status_code=422, detail="duplicate attendee in splits")

    types = {s.share_type for s in splits}
    if len(types) > 1:
        raise HTTPException(status_code=422, detail="all splits must use the same share_type")
    mode = next(iter(types))
    n = len(splits)

    if mode == "equal":
        per = _floor_step(amount / Decimal(n), currency)
        result = [
            {
                "attendee_id": s.attendee_id,
                "share_amount": per,
                "share_type": "equal",
            }
            for s in splits
        ]
    elif mode == "custom_amount":
        for s in splits:
            if s.share_amount is None:
                raise HTTPException(
                    status_code=422, detail="share_amount required for custom_amount"
                )
            if s.share_amount < 0:
                # A negative share means an attendee GAINS money from an
                # expense — corrupts balance netting semantics.
                raise HTTPException(status_code=422, detail="share_amount must be >= 0")
        result = [
            {
                "attendee_id": s.attendee_id,
                "share_amount": Decimal(s.share_amount),
                "share_type": "custom_amount",
            }
            for s in splits
        ]
    elif mode == "custom_percent":
        for s in splits:
            if s.share_percent is None:
                raise HTTPException(
                    status_code=422, detail="share_percent required for custom_percent"
                )
            if s.share_percent < 0:
                raise HTTPException(status_code=422, detail="share_percent must be >= 0")
        total_pct = sum((s.share_percent for s in splits), Decimal("0"))
        if total_pct != Decimal("100"):
            raise HTTPException(
                status_code=422,
                detail=f"share_percent values must sum to 100, got {total_pct}",
            )
        result = [
            {
                "attendee_id": s.attendee_id,
                "share_amount": _floor_step(amount * s.share_percent / Decimal("100"), currency),
                "share_type": "custom_percent",
            }
            for s in splits
        ]
    else:  # pragma: no cover — Pydantic Literal blocks other values upstream
        raise HTTPException(status_code=422, detail=f"unknown share_type {mode}")

    current_sum = sum((r["share_amount"] for r in result), Decimal("0"))
    residual = amount - current_sum
    if residual != Decimal("0"):
        if mode == "custom_amount":
            raise HTTPException(
                status_code=422,
                detail=f"share_amounts sum to {current_sum}, expected {amount}",
            )
        # equal / custom_percent: payer absorbs the floor remainder.
        for r in result:
            if r["attendee_id"] == payer_attendee_id:
                r["share_amount"] = r["share_amount"] + residual
                break
        else:
            # Payer not present in splits — shouldn't generally happen, but
            # spec says payer absorbs remainder; fall back to first split.
            result[0]["share_amount"] = result[0]["share_amount"] + residual

    return result


async def create_expense(
    db: AsyncSession,
    trip: Trip,
    user: User,
    payload: CreateExpenseRequest,
) -> TripExpense:
    """Create a trip expense with normalized splits.

    Sign convention: ``trip_expenses.amount`` is always positive. If a
    ``transaction_id`` is supplied, ``payload.amount`` must equal
    ``abs(transaction.amount)`` and the caller must own that transaction.

    Returns the persisted expense with ``splits`` eager-loaded. Raises:
      - 403 if the linked transaction is not owned by the caller.
      - 404 if the payer/split attendees aren't on this trip.
      - 409 if the linked transaction already has household splits (joint
        account) or is already linked to another trip expense.
      - 422 on share-type, sum, or "attendee left" mismatches.
    """
    # 1. Payer must belong to this trip.
    payer = (
        await db.execute(
            select(TripAttendee).where(
                TripAttendee.id == payload.payer_attendee_id,
                TripAttendee.trip_id == trip.id,
            )
        )
    ).scalar_one_or_none()
    if payer is None:
        raise HTTPException(status_code=404, detail="payer_attendee_id not on this trip")

    # 2. Every split attendee must belong to this trip and still be active.
    split_attendee_ids = [s.attendee_id for s in payload.splits]
    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.id.in_(split_attendee_ids),
                    TripAttendee.trip_id == trip.id,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(set(split_attendee_ids)):
        raise HTTPException(status_code=404, detail="one or more split attendees not on this trip")
    for row in rows:
        if row.left_at is not None:
            raise HTTPException(status_code=422, detail=f"attendee {row.id} has left the trip")

    # v1 single-currency cut: every expense must be in the trip's base currency.
    # Multi-currency + FX is deferred to v2 (see FX_INTEGRATION.md).
    if payload.currency.upper() != trip.base_currency.upper():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "currency_must_match_trip_base",
                "message": (
                    f"expense currency {payload.currency.upper()} must match "
                    f"trip base currency {trip.base_currency.upper()} (v1 single-currency)."
                ),
            },
        )

    amount = Decimal(payload.amount)

    # 3. If linked to a transaction: caller-ownership + sign-convention check.
    if payload.transaction_id is not None:
        from modules.transactions.models import Transaction  # local to avoid cycles

        txn = (
            await db.execute(select(Transaction).where(Transaction.id == payload.transaction_id))
        ).scalar_one_or_none()
        if txn is None:
            raise HTTPException(status_code=404, detail="transaction not found")
        if txn.user_id != user.id:
            raise HTTPException(status_code=403, detail="transaction not owned by caller")
        expected = _txn_amount_to_major(abs(Decimal(txn.amount)), txn.currency)
        if amount != expected:
            raise HTTPException(
                status_code=422,
                detail=f"amount {amount} does not match abs(transaction.amount) {expected}",
            )

    # 4. Compute splits (raises 422 on mismatch).
    splits_to_create = _normalize_splits(payload.splits, amount, payer.id, payload.currency)

    # 5. Insert expense; the BEFORE trigger raises 23514 if the transaction
    #    already has household splits, and the partial unique index raises
    #    23505 if another live trip_expense already links the same txn.
    exp = TripExpense(
        trip_id=trip.id,
        payer_attendee_id=payer.id,
        description=payload.description,
        amount=amount,
        currency=payload.currency.upper(),
        expense_date=payload.expense_date,
        transaction_id=payload.transaction_id,
        fx_rate_to_base=None,
        created_by_user_id=user.id,
    )
    sp = await db.begin_nested()
    try:
        db.add(exp)
        await db.flush()
    except IntegrityError as exc:
        await sp.rollback()
        msg = str(getattr(exc, "orig", exc))
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or ""
        if "household splits" in msg or sqlstate == "23514":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "joint_account_dual_split_not_supported",
                    "message": (
                        "Esta transacción está en una cuenta conjunta. "
                        "La división conjunta + viaje aún no está disponible."
                    ),
                },
            )
        if sqlstate == "23505" or "ux_trip_expenses_transaction" in msg:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "transaction_already_linked",
                    "message": "Esta transacción ya está vinculada a otro viaje.",
                },
            )
        raise

    for split_data in splits_to_create:
        db.add(TripExpenseSplit(trip_expense_id=exp.id, **split_data))
    await db.flush()

    fetched = (
        await db.execute(
            select(TripExpense)
            .options(selectinload(TripExpense.splits))
            .where(TripExpense.id == exp.id)
        )
    ).scalar_one()
    return fetched


# ---------------------------------------------------------------------------
# Update / delete expense
# ---------------------------------------------------------------------------


async def _validate_payer_on_trip(
    db: AsyncSession, trip_id: UUID, payer_attendee_id: UUID
) -> TripAttendee:
    payer = (
        await db.execute(
            select(TripAttendee).where(
                TripAttendee.id == payer_attendee_id,
                TripAttendee.trip_id == trip_id,
            )
        )
    ).scalar_one_or_none()
    if payer is None:
        raise HTTPException(status_code=404, detail="payer_attendee_id not on this trip")
    return payer


async def _validate_split_attendees(
    db: AsyncSession, trip_id: UUID, splits: list[SplitInput]
) -> None:
    split_attendee_ids = [s.attendee_id for s in splits]
    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.id.in_(split_attendee_ids),
                    TripAttendee.trip_id == trip_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(set(split_attendee_ids)):
        raise HTTPException(status_code=404, detail="one or more split attendees not on this trip")
    for row in rows:
        if row.left_at is not None:
            raise HTTPException(status_code=422, detail=f"attendee {row.id} has left the trip")


async def _validate_transaction_link(
    db: AsyncSession, user: User, transaction_id: UUID, amount: Decimal
) -> None:
    from modules.transactions.models import Transaction  # local to avoid cycles

    txn = (
        await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    ).scalar_one_or_none()
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    if txn.user_id != user.id:
        raise HTTPException(status_code=403, detail="transaction not owned by caller")
    expected = _txn_amount_to_major(abs(Decimal(txn.amount)), txn.currency)
    if amount != expected:
        raise HTTPException(
            status_code=422,
            detail=f"amount {amount} does not match abs(transaction.amount) {expected}",
        )


async def update_expense(
    db: AsyncSession,
    trip_id: UUID,
    expense_id: UUID,
    user: User,
    payload: UpdateExpenseRequest,
    if_match: int,
) -> TripExpense:
    """Update a trip expense with optimistic concurrency.

    On version mismatch returns 409 with the current state so the caller can
    show a conflict dialog. If ``amount`` or ``payer_attendee_id`` change, the
    caller MUST also supply ``splits`` — we don't try to re-balance silently.
    Splits, when supplied, replace the existing set wholesale.
    """
    res = await db.execute(
        select(TripExpense)
        .options(selectinload(TripExpense.splits))
        .where(
            TripExpense.id == expense_id,
            TripExpense.trip_id == trip_id,
            TripExpense.deleted_at.is_(None),
        )
    )
    expense = res.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense.version != if_match:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "current_version": expense.version,
                "expense": ExpenseResponse.model_validate(expense).model_dump(mode="json"),
            },
        )

    changes = payload.model_dump(exclude_unset=True)
    splits_provided = "splits" in changes and payload.splits is not None
    amount_changed = "amount" in changes and payload.amount is not None
    payer_changed = (
        "payer_attendee_id" in changes
        and payload.payer_attendee_id is not None
        and payload.payer_attendee_id != expense.payer_attendee_id
    )

    if (amount_changed or payer_changed) and not splits_provided:
        raise HTTPException(
            status_code=422,
            detail="splits must be provided when amount or payer_attendee_id changes",
        )

    # Determine new field values.
    new_amount = Decimal(payload.amount) if amount_changed else Decimal(expense.amount)
    new_payer_id: UUID = payload.payer_attendee_id if payer_changed else expense.payer_attendee_id

    # Validate the (potentially new) payer is on the trip.
    if payer_changed:
        await _validate_payer_on_trip(db, trip_id, new_payer_id)

    # Validate transaction linkage if it's being added/changed — and re-validate
    # whenever the final state has a link AND the amount changed, even if the
    # payload echoes back the SAME transaction_id (otherwise a PATCH with
    # {amount: X, transaction_id: <current>} could diverge the ledger amount
    # from abs(transaction.amount)).
    new_transaction_id = expense.transaction_id
    if "transaction_id" in changes:
        new_transaction_id = payload.transaction_id
        if new_transaction_id is not None and (
            new_transaction_id != expense.transaction_id or amount_changed
        ):
            await _validate_transaction_link(db, user, new_transaction_id, new_amount)
    elif amount_changed and expense.transaction_id is not None:
        # Amount changed but txn link unchanged — re-validate the link still matches.
        await _validate_transaction_link(db, user, expense.transaction_id, new_amount)

    # v1 single-currency invariant: a currency change must still match the
    # trip's base currency (create_expense enforces this; PATCH must too, or
    # compute_balances sums CLP and USD numerals as one unit).
    new_currency = expense.currency
    if "currency" in changes and payload.currency is not None:
        new_currency = payload.currency.upper()
        base_currency = (
            await db.execute(select(Trip.base_currency).where(Trip.id == trip_id))
        ).scalar_one()
        if new_currency != base_currency.upper():
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "currency_must_match_trip_base",
                    "message": (
                        f"expense currency {new_currency} must match trip base "
                        f"currency {base_currency.upper()} (v1 single-currency)."
                    ),
                },
            )

    # Apply scalar field updates.
    if "description" in changes and payload.description is not None:
        expense.description = payload.description
    if amount_changed:
        expense.amount = new_amount
    if "currency" in changes and payload.currency is not None:
        expense.currency = new_currency
    if "expense_date" in changes and payload.expense_date is not None:
        expense.expense_date = payload.expense_date
    if payer_changed:
        expense.payer_attendee_id = new_payer_id
    if "transaction_id" in changes:
        expense.transaction_id = new_transaction_id

    # Replace splits if provided.
    if splits_provided:
        await _validate_split_attendees(db, trip_id, payload.splits)
        splits_to_create = _normalize_splits(payload.splits, new_amount, new_payer_id, new_currency)
        # Delete existing splits via the relationship collection so cascade
        # delete-orphan handles them cleanly, then add the new ones.
        expense.splits.clear()
        await db.flush()
        for split_data in splits_to_create:
            expense.splits.append(TripExpenseSplit(**split_data))

    expense.version = expense.version + 1
    expense.updated_at = datetime.now(timezone.utc)

    sp = await db.begin_nested()
    try:
        await db.flush()
    except IntegrityError as exc:
        await sp.rollback()
        msg = str(getattr(exc, "orig", exc))
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or ""
        if "household splits" in msg or sqlstate == "23514":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "joint_account_dual_split_not_supported",
                    "message": (
                        "Esta transacción está en una cuenta conjunta. "
                        "La división conjunta + viaje aún no está disponible."
                    ),
                },
            )
        if sqlstate == "23505" or "ux_trip_expenses_transaction" in msg:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "transaction_already_linked",
                    "message": "Esta transacción ya está vinculada a otro viaje.",
                },
            )
        raise

    fetched = (
        await db.execute(
            select(TripExpense)
            .options(selectinload(TripExpense.splits))
            .where(TripExpense.id == expense.id)
        )
    ).scalar_one()
    return fetched


async def delete_expense(
    db: AsyncSession,
    trip_id: UUID,
    expense_id: UUID,
    user: User,
) -> None:
    """Soft-delete a trip expense.

    Sets ``deleted_at = now()``. The partial unique index on transaction_id
    excludes soft-deleted rows, so the linked transaction becomes available
    for re-linking immediately after.
    """
    res = await db.execute(
        select(TripExpense).where(
            TripExpense.id == expense_id,
            TripExpense.trip_id == trip_id,
            TripExpense.deleted_at.is_(None),
        )
    )
    expense = res.scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.deleted_at = datetime.now(timezone.utc)
    await db.flush()


# ---------------------------------------------------------------------------
# Settlements (Phase 4)
# ---------------------------------------------------------------------------


async def create_settlement(
    db: AsyncSession,
    trip: Trip,
    user: User,
    payload: CreateSettlementRequest,
) -> TripSettlement:
    """Insert a settlement transferring ``amount`` from one attendee to another.

    v1 single-currency cut: ``payload.currency`` must equal ``trip.base_currency``;
    ``fx_rate_to_base`` stays NULL. The schema already enforces
    ``from_attendee_id != to_attendee_id`` and ``amount > 0`` (Pydantic + DB CHECK).

    Settlements intentionally bypass the ``transaction_splits`` mutual-exclusivity
    trigger — those triggers only fire on ``trip_expenses``.
    """
    if payload.currency.upper() != trip.base_currency.upper():
        raise HTTPException(
            status_code=422,
            detail={
                "code": "currency_must_match_trip_base",
                "message": (
                    f"settlement currency {payload.currency.upper()} must match "
                    f"trip base currency {trip.base_currency.upper()} (v1 single-currency)."
                ),
            },
        )

    # from + to must both belong to this trip.
    rows = (
        (
            await db.execute(
                select(TripAttendee).where(
                    TripAttendee.trip_id == trip.id,
                    TripAttendee.id.in_([payload.from_attendee_id, payload.to_attendee_id]),
                )
            )
        )
        .scalars()
        .all()
    )
    found_ids = {r.id for r in rows}
    if payload.from_attendee_id not in found_ids or payload.to_attendee_id not in found_ids:
        raise HTTPException(status_code=404, detail="one or both attendees not on this trip")

    # Optional transaction link must be owned by the caller.
    if payload.transaction_id is not None:
        from modules.transactions.models import Transaction  # local import

        txn = (
            await db.execute(select(Transaction).where(Transaction.id == payload.transaction_id))
        ).scalar_one_or_none()
        if txn is None:
            raise HTTPException(status_code=404, detail="transaction not found")
        if txn.user_id != user.id:
            raise HTTPException(status_code=403, detail="transaction not owned by caller")

    settlement = TripSettlement(
        trip_id=trip.id,
        from_attendee_id=payload.from_attendee_id,
        to_attendee_id=payload.to_attendee_id,
        amount=Decimal(payload.amount),
        currency=payload.currency.upper(),
        fx_rate_to_base=None,
        transaction_id=payload.transaction_id,
        created_by_user_id=user.id,
    )
    db.add(settlement)
    await db.flush()
    await db.refresh(settlement)
    return settlement


# ---------------------------------------------------------------------------
# Force-remove attendee with write-off (Phase 4 Task 4.6)
# ---------------------------------------------------------------------------


async def force_remove_attendee(
    db: AsyncSession,
    trip_id: UUID,
    attendee_id: UUID,
    user: User,
) -> None:
    """Creator-only. Zero out the attendee's outstanding balance via a
    write-off settlement, then set ``left_at``.

    If the attendee's net is positive (creditor), the write-off goes
    *from* a creator surrogate counterparty *to* them — wait, simpler:
    we model the write-off as a settlement whose **other side is the trip
    creator's attendee**. The plan is:
      - net > 0 (attendee is owed): settlement from=attendee, to=creator,
        amount=net  → attendee.net -= net (zeroed); creator absorbs the loss.
      - net < 0 (attendee owes): settlement from=creator, to=attendee,
        amount=|net| → attendee.net += |net| (zeroed); creator absorbs again.
    Either way the creator's attendee row eats the write-off; the field
    ``write_off=true`` flags it for audit.
    """
    # Fetch the trip + verify creator.
    trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.creator_user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the trip creator can force-remove an attendee"
        )

    attendee = (
        await db.execute(
            select(TripAttendee).where(
                TripAttendee.id == attendee_id,
                TripAttendee.trip_id == trip_id,
            )
        )
    ).scalar_one_or_none()
    if attendee is None:
        raise HTTPException(status_code=404, detail="Attendee not on this trip")
    if attendee.left_at is not None:
        raise HTTPException(status_code=404, detail="Attendee already left this trip")
    if attendee.user_id == trip.creator_user_id:
        # The creator is the write-off counterparty; removing themselves would
        # emit a from==to settlement (DB CHECK violation → opaque 500).
        raise HTTPException(
            status_code=422,
            detail="creator cannot force-remove themselves; archive the trip instead",
        )

    # Find the creator's active attendee row to be the write-off counterparty.
    creator_attendee = (
        (
            await db.execute(
                select(TripAttendee)
                .where(
                    TripAttendee.trip_id == trip_id,
                    TripAttendee.user_id == trip.creator_user_id,
                    TripAttendee.left_at.is_(None),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if creator_attendee is None:
        raise HTTPException(
            status_code=500, detail="trip creator missing attendee row (data corruption)"
        )

    # Compute current balance for this attendee.
    from modules.trips.balances import compute_balances  # local import to avoid cycles

    balances = await compute_balances(trip_id, db)
    target = next((b for b in balances if b.attendee_id == attendee.id), None)
    net = Decimal(target.net_in_base) if target is not None else Decimal("0")

    if net > Decimal("0.01"):
        # Attendee is a creditor — emit attendee → creator for ``net``.
        db.add(
            TripSettlement(
                trip_id=trip_id,
                from_attendee_id=attendee.id,
                to_attendee_id=creator_attendee.id,
                amount=net,
                currency=trip.base_currency,
                fx_rate_to_base=None,
                created_by_user_id=user.id,
                write_off=True,
            )
        )
    elif net < Decimal("-0.01"):
        # Attendee is a debtor — emit creator → attendee for ``|net|``.
        db.add(
            TripSettlement(
                trip_id=trip_id,
                from_attendee_id=creator_attendee.id,
                to_attendee_id=attendee.id,
                amount=-net,
                currency=trip.base_currency,
                fx_rate_to_base=None,
                created_by_user_id=user.id,
                write_off=True,
            )
        )
    # else: net within ±0.01 — no write-off needed.

    attendee.left_at = datetime.now(timezone.utc)
    await db.flush()


# ---------------------------------------------------------------------------
# Invite links (Phase 5)
# ---------------------------------------------------------------------------


INVITE_TOKEN_TTL_DAYS = 30


def _hash_token(raw_token: str) -> str:
    """SHA-256 hex digest of the raw token (only the hash is persisted)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def generate_invite_link(db: AsyncSession, trip_id: UUID, user: User) -> tuple[str, datetime]:
    """Creator-only. Generate a fresh invite token, store its hash, and
    return ``(raw_token, expires_at)``.

    Rotation = same endpoint: any prior hash is overwritten so old links
    immediately stop redeeming. The raw token is returned exactly once —
    callers MUST surface it to the user immediately.
    """
    trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.creator_user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the trip creator can manage the invite link"
        )
    raw = secrets.token_urlsafe(32)  # 256 bits of entropy
    trip.invite_token_hash = _hash_token(raw)
    trip.invite_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=INVITE_TOKEN_TTL_DAYS
    )
    await db.flush()
    return raw, trip.invite_token_expires_at


async def revoke_invite_link(db: AsyncSession, trip_id: UUID, user: User) -> None:
    """Creator-only. Clears the invite token hash + expiry (link dies)."""
    trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.creator_user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Only the trip creator can manage the invite link"
        )
    trip.invite_token_hash = None
    trip.invite_token_expires_at = None
    await db.flush()


async def lookup_trip_by_token(db: AsyncSession, raw_token: str) -> Trip:
    """Resolve a raw invite token to its Trip if non-expired. Read-only.

    Raises 404 if no live invite matches (covers wrong token, revoked
    invite, and expired invite indistinguishably — we don't want to leak
    which case applies).
    """
    h = _hash_token(raw_token)
    trip = (
        await db.execute(
            select(Trip).where(
                Trip.invite_token_hash == h,
                Trip.invite_token_expires_at > datetime.now(timezone.utc),
            )
        )
    ).scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="invite link not found or expired")
    return trip


async def accept_invite(db: AsyncSession, raw_token: str, user: User) -> Trip:
    """Idempotent: add caller as a Luka attendee if not already, and
    refresh the invite expiry (sliding 30-day window on use).

    - Already-active member: no-op (returns the same trip).
    - Previously left member: clear ``left_at`` instead of inserting a
      duplicate row (avoids breaking historical balance attribution).
    """
    trip = await lookup_trip_by_token(db, raw_token)
    existing = (
        await db.execute(
            select(TripAttendee).where(
                TripAttendee.trip_id == trip.id,
                TripAttendee.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            TripAttendee(
                trip_id=trip.id,
                user_id=user.id,
                display_name=user.full_name,
            )
        )
    elif existing.left_at is not None:
        existing.left_at = None
    # Sliding-window refresh: every successful join extends the link.
    trip.invite_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=INVITE_TOKEN_TTL_DAYS
    )
    await db.flush()
    return trip


# ---------------------------------------------------------------------------
# Phase 6 — Suggestions inbox + dismissals
#
# See spec ``docs/superpowers/specs/2026-04-30-viajes-trips-design.md`` §4.6.
# ---------------------------------------------------------------------------


async def _detected_subscription_merchant_keys(db: AsyncSession, user_id: UUID) -> set[str]:
    """Delegates to the subscriptions module — the cache schema is owned
    there (L12); a broad except keeps suggestion filtering best-effort."""
    try:
        from modules.subscriptions.service import get_active_subscription_merchant_keys

        return await get_active_subscription_merchant_keys(db, user_id)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "subscription-key lookup failed; trip suggestions unfiltered", exc_info=True
        )
        return set()


async def get_suggested_transactions(db: AsyncSession, trip_id: UUID, user: User) -> list[dict]:
    """Caller's expense transactions in the trip's date window that are not
    already linked, dismissed, a subscription, or a transfer.

    Returns dicts shaped like ``SuggestedTransaction`` (transaction_id,
    merchant, amount, currency, transaction_date, category) for the router
    to wrap. Only the caller's own ``user_id`` is queried — each Luka
    attendee on the trip has their own personal inbox.
    """

    from modules.merchants.models import Merchant
    from modules.transactions.models import Transaction

    trip = await get_trip(db, trip_id, user)

    sub_keys = await _detected_subscription_merchant_keys(db, user.id)

    # Linked/dismissed exclusions run as SQL anti-joins — the old version
    # loaded every live trip-expense link PLATFORM-WIDE into a Python set on
    # each inbox open.
    linked_subq = select(TripExpense.transaction_id).where(
        TripExpense.transaction_id.isnot(None),
        TripExpense.deleted_at.is_(None),
    )
    dismissed_subq = select(TripSuggestionDismissal.transaction_id).where(
        TripSuggestionDismissal.user_id == user.id,
        TripSuggestionDismissal.trip_id == trip.id,
    )

    q = (
        select(Transaction, Merchant.normalized_name)
        .outerjoin(Merchant, Transaction.merchant_id == Merchant.id)
        .where(
            Transaction.user_id == user.id,
            Transaction.transaction_type == "expense",
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.reimbursement_group_id.is_(None),
            Transaction.transaction_date >= trip.start_date,
            Transaction.transaction_date < trip.end_date + timedelta(days=1),
            Transaction.id.notin_(linked_subq),
            Transaction.id.notin_(dismissed_subq),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = (await db.execute(q)).all()

    out: list[dict] = []
    for txn, normalized in rows:
        merchant_key = (normalized or txn.raw_merchant_name or "").strip().lower()
        if merchant_key and merchant_key in sub_keys:
            continue
        out.append(
            {
                "transaction_id": txn.id,
                "merchant": normalized or txn.raw_merchant_name,
                # Trip surfaces speak positive MAJOR units (create_expense
                # validates against abs(txn.amount) in major units) — emitting
                # the raw stored minor units made prefilled forms 100× off.
                "amount": _txn_amount_to_major(abs(Decimal(txn.amount)), txn.currency),
                "currency": txn.currency,
                "transaction_date": (
                    txn.transaction_date.date()
                    if hasattr(txn.transaction_date, "date")
                    else txn.transaction_date
                ),
                "category": txn.category,
            }
        )
    return out


async def dismiss_suggestion(
    db: AsyncSession, trip_id: UUID, transaction_id: UUID, user: User
) -> None:
    """Insert a ``TripSuggestionDismissal`` for ``(user, trip, transaction)``.

    Idempotent: a duplicate dismissal is a no-op (composite PK guarantees
    uniqueness; we swallow IntegrityError so repeated calls don't 500).
    Membership is enforced via ``get_trip`` (404 for non-members).
    """
    await get_trip(db, trip_id, user)
    db.add(
        TripSuggestionDismissal(
            user_id=user.id,
            trip_id=trip_id,
            transaction_id=transaction_id,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()


async def undismiss_suggestion(
    db: AsyncSession, trip_id: UUID, transaction_id: UUID, user: User
) -> None:
    """Remove the ``TripSuggestionDismissal`` row, restoring inbox visibility."""
    from sqlalchemy import delete as sql_delete

    await get_trip(db, trip_id, user)
    await db.execute(
        sql_delete(TripSuggestionDismissal).where(
            TripSuggestionDismissal.user_id == user.id,
            TripSuggestionDismissal.trip_id == trip_id,
            TripSuggestionDismissal.transaction_id == transaction_id,
        )
    )
    await db.flush()


async def dismiss_settlement_suggestion(db: AsyncSession, transaction_id: UUID, user: User) -> None:
    """Insert a ``TripSettlementDismissal`` for ``(user, transaction)``.

    Idempotent. Note: not gated by trip — settlement suggestions are a
    per-user signal across all the user's trips (the same Zelle won't fire
    twice for the same trip anyway).
    """
    db.add(
        TripSettlementDismissal(
            user_id=user.id,
            transaction_id=transaction_id,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
