"""Remove deprecated expense categories and reassign transactions to random defaults

Removes Combustible, Supermercado, Farmacia, Tecnología, Servicios from all users.
Transactions and splits in those categories are reassigned to a random category
from the 9 new expense defaults. Merchant selections for those categories are deleted.

Revision ID: 028
Revises: 027
"""

from alembic import op

_REMOVED = ('Combustible', 'Supermercado', 'Farmacia', 'Tecnología', 'Servicios')
_DEFAULTS = ('Alimentación', 'Transporte', 'Entretenimiento', 'Salud', 'Hogar',
             'Ropa', 'Educación', 'Viajes', 'Otros')

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    removed_list = ", ".join(f"'{c}'" for c in _REMOVED)
    defaults_array = ", ".join(f"'{c}'" for c in _DEFAULTS)
    n = len(_DEFAULTS)

    # Reassign transactions
    op.execute(f"""
        UPDATE transactions
        SET category = (ARRAY[{defaults_array}])[floor(random()*{n})::int + 1]
        WHERE category IN ({removed_list})
    """)

    # Reassign transaction splits
    op.execute(f"""
        UPDATE transaction_splits
        SET category = (ARRAY[{defaults_array}])[floor(random()*{n})::int + 1]
        WHERE category IN ({removed_list})
    """)

    # Delete per-user merchant selections for removed categories
    op.execute(f"""
        DELETE FROM merchant_category_selections
        WHERE category IN ({removed_list})
        AND user_id IS NOT NULL
    """)

    # Delete the preference rows for all users
    op.execute(f"""
        DELETE FROM user_category_preferences
        WHERE category IN ({removed_list})
    """)


def downgrade() -> None:
    # Data reassignment is not reversible — downgrade is a no-op
    pass
