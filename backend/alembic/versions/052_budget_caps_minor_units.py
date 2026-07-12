"""052 — budget caps/budgets stored in minor units

Revision ID: 052
Revises: 051

`category_budgets.amount` and `household_budgets.budgeted` were stored as the
user typed them (MAJOR units) while every transaction-derived spend figure is
integer MINOR units. For 2-decimal currencies that mismatch made the budget
risk stats compare a 200 (USD) cap against 12050 (cents) of spend, and split
the frontend into two contradictory rendering conventions (some surfaces ÷100,
some not) — one of them always 100× off. CLP/COP masked the bug because their
minor unit IS the major unit.

Convention after this migration: caps and monthly budgets are integer minor
units, same as transactions. The frontend converts at the input boundary.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "052"
down_revision: Union[str, Sequence[str], None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ZERO_DECIMAL = "('CLP','COP','JPY','KRW','PYG','VND')"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE category_budgets
        SET amount = amount * 100
        WHERE UPPER(currency) NOT IN {_ZERO_DECIMAL}
        """
    )
    op.execute(
        f"""
        UPDATE household_budgets hb
        SET budgeted = hb.budgeted * 100
        FROM bank_accounts ba
        WHERE ba.id = hb.bank_account_id
          AND UPPER(ba.currency) NOT IN {_ZERO_DECIMAL}
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE category_budgets
        SET amount = amount / 100
        WHERE UPPER(currency) NOT IN {_ZERO_DECIMAL}
        """
    )
    op.execute(
        f"""
        UPDATE household_budgets hb
        SET budgeted = hb.budgeted / 100
        FROM bank_accounts ba
        WHERE ba.id = hb.bank_account_id
          AND UPPER(ba.currency) NOT IN {_ZERO_DECIMAL}
        """
    )
