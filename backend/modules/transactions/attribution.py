"""Partner-card charge attribution: hand off a transaction on a shared card to
a household partner. See docs/superpowers/specs/2026-07-12-partner-card-charge-attribution-design.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.auth.models import User
from modules.households.models import HouseholdMember
from modules.notifications.service import create_notification
from modules.transactions.models import Transaction, TransactionAttribution, TransactionSplit


def effective_owner_id(owner_user_id: uuid.UUID, attribution: TransactionAttribution | None):
    """Who a transaction's amount counts for: the recipient when actively
    attributed, otherwise the account/transaction owner."""
    if attribution is not None and attribution.status == "active":
        return attribution.attributed_to_user_id
    return owner_user_id


def attributed_to_clause(caller_id: uuid.UUID):
    """Rows actively attributed to ``caller_id``. Requires outerjoin(TransactionAttribution)."""
    return (TransactionAttribution.attributed_to_user_id == caller_id) & (
        TransactionAttribution.status == "active"
    )


def _attributed_away():
    """A row that is actively handed off to someone (so it leaves the owner's totals)."""
    return (TransactionAttribution.id.isnot(None)) & (TransactionAttribution.status == "active")


def owned_by_caller_clause(caller_id: uuid.UUID):
    """A transaction counts for ``caller_id`` when it is their own row and NOT
    actively attributed away, OR it is actively attributed TO them.

    Requires the query to ``outerjoin(TransactionAttribution)``. This is the
    single predicate the exactly-one-owner AGGREGATES use (dashboard totals,
    category breakdown), guaranteeing exactly-one-owner by construction.
    """
    own_kept = (Transaction.user_id == caller_id) & (~_attributed_away())
    return or_(own_kept, attributed_to_clause(caller_id))


def list_visible_clause(caller_id: uuid.UUID):
    """LIST views: the caller sees their OWN rows (even ones handed off — they
    stay visible, labeled) PLUS rows handed off TO them. No exclusion.
    Requires outerjoin(TransactionAttribution)."""
    return or_(Transaction.user_id == caller_id, attributed_to_clause(caller_id))


def personal_scope_clause(caller_id: uuid.UUID):
    """PERSONAL-budget view: the caller's own personal/untagged rows that are
    NOT attributed away, PLUS rows attributed to them. Excludes the caller's own
    SHARED rows and exclude-only partner rows. Requires outerjoin(TransactionSplit)
    AND outerjoin(TransactionAttribution)."""
    own_personal = and_(
        Transaction.user_id == caller_id,
        or_(TransactionSplit.split_type == "personal", TransactionSplit.split_type.is_(None)),
        not_(_attributed_away()),
    )
    return or_(own_personal, attributed_to_clause(caller_id))


async def account_person_balances(db: AsyncSession, bank_account_id) -> list[dict]:
    """Per-effective-owner gastos/pagos/saldo breakdown for a single shared card.

    Unlike the counts-toward-totals aggregates (dashboard, budgets), a card
    payment (transaction_type='transfer') is NOT excluded here — for a card
    BALANCE we want both charges and payments. Only ``bank_account_id`` and a
    pending/orphan status guard scope the rows.
    """
    # One reused expression object for SELECT and GROUP BY — see get_dashboard_summary's
    # cat_expr note: two separately-built `case(...)` calls would bind as two
    # different parameters and Postgres would reject the grouping.
    effective_owner = case(
        (
            (TransactionAttribution.id.isnot(None)) & (TransactionAttribution.status == "active"),
            TransactionAttribution.attributed_to_user_id,
        ),
        else_=Transaction.user_id,
    )

    gastos = func.coalesce(func.sum(func.abs(Transaction.amount)).filter(Transaction.amount < 0), 0)
    pagos = func.coalesce(func.sum(Transaction.amount).filter(Transaction.amount > 0), 0)

    rows = await db.execute(
        select(
            effective_owner.label("user_id"),
            User.full_name,
            gastos.label("gastos"),
            pagos.label("pagos"),
        )
        .select_from(Transaction)
        .outerjoin(TransactionAttribution, TransactionAttribution.transaction_id == Transaction.id)
        .join(User, User.id == effective_owner)
        .where(
            Transaction.bank_account_id == bank_account_id,
            Transaction.status.notin_(["pending", "orphan"]),
            Transaction.needs_classification.isnot(True),
        )
        .group_by(effective_owner, User.id, User.full_name)
    )

    return [
        {
            "user_id": str(row.user_id),
            "name": row.full_name,
            "gastos": int(row.gastos),
            "pagos": int(row.pagos),
            "saldo": int(row.gastos) - int(row.pagos),
        }
        for row in rows
    ]


class AmbiguousRecipient(Exception):
    """More than one other active member — caller must choose."""

    def __init__(self, candidate_ids: list[uuid.UUID]):
        self.candidate_ids = candidate_ids
        super().__init__("multiple candidate recipients")


class AttributionNotFound(Exception):
    """No attribution row for the given id / transaction."""


class AttributionForbidden(Exception):
    """Caller is not the party allowed to perform this action."""


async def resolve_recipient(db, household_id, sender_id):
    ids = (
        (
            await db.execute(
                select(HouseholdMember.user_id).where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.user_id != sender_id,
                    HouseholdMember.left_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not ids:
        return None
    if len(ids) > 1:
        raise AmbiguousRecipient(list(ids))
    return ids[0]


async def _set_split(db, transaction_id, split_type, decided_by):
    split = (
        await db.execute(
            select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
        )
    ).scalar_one_or_none()
    if split:
        split.split_type = split_type
        split.decided_by_user_id = decided_by
        split.decided_at = datetime.now(timezone.utc)
    else:
        db.add(
            TransactionSplit(
                transaction_id=transaction_id,
                split_type=split_type,
                decided_by_user_id=decided_by,
                decided_at=datetime.now(timezone.utc),
            )
        )


async def hand_off(db: AsyncSession, txn, sender_id, recipient_id):
    """Tag the txn as the recipient's (split=partner) + upsert attribution + notify."""
    from modules.transactions.service import mark_user_edited

    await _set_split(db, txn.id, "partner", sender_id)
    mark_user_edited(txn, "split_type")

    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one_or_none()
    # Redundant re-tag: already active and pointed at the same recipient. Capture
    # this BEFORE the upsert so we can skip re-notifying the recipient.
    is_redundant = (
        attr is not None and attr.status == "active" and attr.attributed_to_user_id == recipient_id
    )
    if attr is None:
        attr = TransactionAttribution(
            transaction_id=txn.id,
            attributed_to_user_id=recipient_id,
            attributed_by_user_id=sender_id,
            status="active",
        )
        db.add(attr)
    else:
        attr.attributed_to_user_id = recipient_id
        attr.attributed_by_user_id = sender_id
        attr.status = "active"
        if not is_redundant:
            attr.acknowledged_at = None
    await db.flush()

    if is_redundant:
        return

    await create_notification(
        db,
        user_id=recipient_id,
        type="charge_attributed",
        title=f"{txn.raw_merchant_name} — ¿es tuyo?",
        payload={
            "transaction_id": str(txn.id),
            "attribution_id": str(attr.id),
            "merchant": txn.raw_merchant_name,
            "amount": txn.amount if isinstance(txn.amount, int) else str(txn.amount),
            "currency": txn.currency,
        },
        commit=False,
    )


async def reject(db: AsyncSession, attribution_id, by_user_id):
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.id == attribution_id)
        )
    ).scalar_one_or_none()
    if attr is None:
        raise AttributionNotFound
    if attr.attributed_to_user_id != by_user_id:
        raise AttributionForbidden
    attr.status = "rejected"
    attr.acknowledged_at = None
    txn = (
        await db.execute(select(Transaction).where(Transaction.id == attr.transaction_id))
    ).scalar_one()
    await _set_split(db, txn.id, "personal", by_user_id)
    await db.flush()
    await create_notification(
        db,
        user_id=attr.attributed_by_user_id,
        type="attribution_rejected",
        title=f"{txn.raw_merchant_name} vuelve a tus gastos",
        payload={
            "transaction_id": str(txn.id),
            "merchant": txn.raw_merchant_name,
            "amount": txn.amount if isinstance(txn.amount, int) else str(txn.amount),
            "currency": txn.currency,
        },
        commit=False,
    )
    return attr


async def acknowledge(db: AsyncSession, attribution_id, by_user_id):
    """Recipient confirms a charge handed to them (marks it acknowledged)."""
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.id == attribution_id)
        )
    ).scalar_one_or_none()
    if attr is None:
        raise AttributionNotFound
    if attr.attributed_to_user_id != by_user_id:
        raise AttributionForbidden
    attr.acknowledged_at = datetime.now(timezone.utc)
    return attr


async def revert_attributions_for_member(db: AsyncSession, user_id):
    """Undo every active attribution involving a leaving member (as recipient
    OR sender): mark it rejected and revert the transaction's split to personal,
    so nothing stays attributed to/from a non-member."""
    attrs = (
        (
            await db.execute(
                select(TransactionAttribution).where(
                    TransactionAttribution.status == "active",
                    or_(
                        TransactionAttribution.attributed_to_user_id == user_id,
                        TransactionAttribution.attributed_by_user_id == user_id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    for attr in attrs:
        attr.status = "rejected"
        attr.acknowledged_at = None
        await _set_split(db, attr.transaction_id, "personal", user_id)
    await db.flush()


async def un_tag(db: AsyncSession, transaction_id, by_user_id):
    attr = (
        await db.execute(
            select(TransactionAttribution).where(
                TransactionAttribution.transaction_id == transaction_id
            )
        )
    ).scalar_one_or_none()
    if attr is None:
        raise AttributionNotFound
    if attr.attributed_by_user_id != by_user_id:
        raise AttributionForbidden
    recipient, was_ack = attr.attributed_to_user_id, attr.acknowledged_at is not None
    await db.delete(attr)
    await _set_split(db, transaction_id, "personal", by_user_id)
    await db.flush()
    if was_ack:
        txn = (
            await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        ).scalar_one()
        await create_notification(
            db,
            user_id=recipient,
            type="attribution_removed",
            title=f"{txn.raw_merchant_name} se quitó de tus gastos",
            payload={"transaction_id": str(transaction_id)},
            commit=False,
        )
    return attr
