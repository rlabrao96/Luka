"""Trip balance computation + smart-settle plan.

Phase 4 v1 cut: single-currency only. Every ``trip_expenses.amount`` and
``trip_settlements.amount`` is already denominated in ``trip.base_currency``
(enforced at write time by ``service.create_expense`` /
``service.create_settlement``), so no FX conversion is needed.

Multi-currency support is v2 — see ``FX_INTEGRATION.md`` for the design.

Public surface:
- ``compute_balances(trip_id, db)`` — async, returns ``list[BalanceEntry]``
  per attendee (positive = creditor, negative = debtor) sorted descending
  by net.
- ``smart_settle_plan(balances, currency)`` — pure, greedy minimum-transactions
  reduction. Total transfers ≤ n − 1 for n non-zero attendees.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.trips.models import (
    Trip,
    TripAttendee,
    TripExpense,
    TripSettlement,
)
from modules.trips.schemas import BalanceEntry, SettleSuggestion


_EPS = Decimal("0.01")


async def compute_balances(trip_id: UUID, db: AsyncSession) -> list[BalanceEntry]:
    """Compute net balance per attendee in the trip's base currency.

    Net per attendee = Σ(amount they paid as payer) − Σ(their share across all
    splits) + settlements applied (a settlement of $X from D to C transfers
    $X of debt: ``net[D] += X``, ``net[C] -= X`` — debtor's net moves toward
    zero from below, creditor's from above).

    Soft-deleted expenses are excluded. Write-off settlements are included
    just like normal settlements (they're how force-remove zeros a balance).
    Attendees who left are still included (they may have non-zero balances).
    """
    attendees = (
        (await db.execute(select(TripAttendee).where(TripAttendee.trip_id == trip_id)))
        .scalars()
        .all()
    )
    net: dict[UUID, Decimal] = {a.id: Decimal("0") for a in attendees}
    name: dict[UUID, str] = {a.id: a.display_name for a in attendees}

    expenses = (
        (
            await db.execute(
                select(TripExpense)
                .options(selectinload(TripExpense.splits))
                .where(
                    TripExpense.trip_id == trip_id,
                    TripExpense.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for exp in expenses:
        if exp.payer_attendee_id in net:
            net[exp.payer_attendee_id] += Decimal(exp.amount)
        for sp in exp.splits:
            if sp.attendee_id in net:
                net[sp.attendee_id] -= Decimal(sp.share_amount)

    settlements = (
        (await db.execute(select(TripSettlement).where(TripSettlement.trip_id == trip_id)))
        .scalars()
        .all()
    )
    for s in settlements:
        amt = Decimal(s.amount)
        if s.from_attendee_id in net:
            net[s.from_attendee_id] += amt
        if s.to_attendee_id in net:
            net[s.to_attendee_id] -= amt

    entries = [
        BalanceEntry(
            attendee_id=aid,
            attendee_display_name=name.get(aid),
            net_in_base=val,
        )
        for aid, val in net.items()
    ]
    entries.sort(key=lambda e: e.net_in_base, reverse=True)
    return entries


def smart_settle_plan(balances: Iterable[BalanceEntry], currency: str) -> list[SettleSuggestion]:
    """Greedy minimum-transactions plan.

    Pair the largest creditor with the largest debtor, emit a transfer of
    ``min(|creditor|, |debtor|)``, decrement both, drop anyone within
    ``±0.01`` of zero, repeat. For ``n`` attendees with non-zero net, this
    emits ≤ ``n − 1`` transfers (Splitwise's classic bound).

    Pure function. Mutates a local copy; the caller's list is untouched.
    """
    pos: list[tuple[UUID, Decimal]] = []
    neg: list[tuple[UUID, Decimal]] = []
    for b in balances:
        v = Decimal(b.net_in_base)
        if v > _EPS:
            pos.append((b.attendee_id, v))
        elif v < -_EPS:
            neg.append((b.attendee_id, v))
    pos.sort(key=lambda t: t[1], reverse=True)
    neg.sort(key=lambda t: t[1])  # most-negative first

    suggestions: list[SettleSuggestion] = []
    while pos and neg:
        cid, cval = pos[0]
        did, dval = neg[0]
        amount = min(cval, -dval).quantize(Decimal("0.01"))
        if amount <= Decimal("0"):
            break
        suggestions.append(
            SettleSuggestion(
                from_attendee_id=did,
                to_attendee_id=cid,
                amount=amount,
                currency=currency,
            )
        )
        cval -= amount
        dval += amount
        if cval <= _EPS:
            pos.pop(0)
        else:
            pos[0] = (cid, cval)
        if dval >= -_EPS:
            neg.pop(0)
        else:
            neg[0] = (did, dval)
    return suggestions


async def your_net_balance(trip: Trip, user_id: UUID, db: AsyncSession) -> Decimal:
    """Helper: return the caller's net for one trip (sum across all their
    active+left attendee rows, though typically one). Used for trip-list."""
    balances = await compute_balances(trip.id, db)
    # Find the attendee row for this user.
    res = await db.execute(
        select(TripAttendee.id).where(
            TripAttendee.trip_id == trip.id,
            TripAttendee.user_id == user_id,
        )
    )
    ids = {row[0] for row in res.all()}
    return sum((b.net_in_base for b in balances if b.attendee_id in ids), Decimal("0"))
