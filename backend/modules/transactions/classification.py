"""Shared-card charge classification: pend charges on a shared_card until sorted.
See docs/superpowers/specs/2026-07-12-shared-card-charge-classification-design.md.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import BankAccount
from modules.transactions.models import Transaction, TransactionAttribution

OUTCOMES = {"owner_personal", "partner_personal", "owner_shared", "partner_shared"}


class AlreadyClassified(Exception):
    """The charge was already sorted (first-to-sort won)."""


class NotPending(Exception):
    """The transaction isn't a pending shared-card charge."""


def should_pend(account_type: str | None, transaction_type: str | None) -> bool:
    """A non-transfer charge on a shared_card account is pending classification."""
    return account_type == "shared_card" and transaction_type != "transfer"


async def list_pending_for_household(db: AsyncSession, household_id):
    """Shared-card charges awaiting classification, visible to both members."""
    rows = await db.execute(
        select(Transaction)
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == household_id,
            Transaction.needs_classification.is_(True),
            BankAccount.account_type == "shared_card",
        )
        .order_by(Transaction.transaction_date.desc())
    )
    return rows.scalars().all()


async def classify(db: AsyncSession, transaction_id, actor_id, outcome, partner_id=None):
    """Four-way sort of a pending shared-card charge. First-to-sort wins:
    a charge whose ``needs_classification`` is no longer True raises
    ``AlreadyClassified``. Writes the split + (for partner-* outcomes) the
    attribution; the payer meaning of that attribution is resolved later
    (Task 6) via split_type.
    """
    from modules.transactions.attribution import _set_split, resolve_recipient
    from modules.transactions.service import mark_user_edited

    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")

    txn = (
        await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    ).scalar_one_or_none()
    if txn is None:
        raise NotPending()
    if txn.needs_classification is not True:
        raise AlreadyClassified()

    is_partner = outcome.startswith("partner_")
    split_type = (
        "personal"
        if outcome == "owner_personal"
        else ("partner" if outcome == "partner_personal" else "shared")
    )

    # Resolve the partner for partner-* outcomes. AmbiguousRecipient (>1 other
    # member) propagates to the endpoint (→ 409).
    recipient = None
    if is_partner:
        recipient = partner_id or await resolve_recipient(db, txn.household_id, actor_id)
        if recipient is None:
            raise ValueError("no_partner_in_household")

    await _set_split(db, txn.id, split_type, actor_id)
    mark_user_edited(txn, "split_type")

    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one_or_none()
    if is_partner:
        if attr is None:
            db.add(
                TransactionAttribution(
                    transaction_id=txn.id,
                    attributed_to_user_id=recipient,
                    attributed_by_user_id=actor_id,
                    status="active",
                )
            )
        else:
            attr.attributed_to_user_id = recipient
            attr.attributed_by_user_id = actor_id
            attr.status = "active"
            attr.acknowledged_at = None
    elif attr is not None:
        await db.delete(attr)

    txn.needs_classification = False
    await db.flush()
    return txn


async def resolve_pending_to_owner_on_leave(db: AsyncSession, household_id):
    """When a member leaves, resolve every still-``needs_classification=True``
    shared-card charge in that household to owner-personal. The classification
    queue is a two-person surface (both partners see and sort it) — once a
    member leaves, nothing should keep pending against them, so the remaining
    owner keeps the charge as a personal expense.
    """
    from modules.transactions.attribution import _set_split

    rows = (
        (
            await db.execute(
                select(Transaction)
                .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
                .where(
                    Transaction.household_id == household_id,
                    Transaction.needs_classification.is_(True),
                    BankAccount.account_type == "shared_card",
                )
            )
        )
        .scalars()
        .all()
    )

    for txn in rows:
        await _set_split(db, txn.id, "personal", txn.user_id)
        attr = (
            await db.execute(
                select(TransactionAttribution).where(
                    TransactionAttribution.transaction_id == txn.id
                )
            )
        ).scalar_one_or_none()
        if attr is not None:
            await db.delete(attr)
        txn.needs_classification = False

    await db.flush()
