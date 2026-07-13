"""Shared-card charge classification: pend charges on a shared_card until sorted.
See docs/superpowers/specs/2026-07-12-shared-card-charge-classification-design.md.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import BankAccount
from modules.transactions.models import Transaction


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
