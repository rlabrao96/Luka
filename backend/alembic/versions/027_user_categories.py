"""user_categories — add category_type/is_custom, drop hidden, per-user merchant counters

Revision ID: 027
Revises: 026
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add category_type (nullable first so existing rows don't violate NOT NULL)
    op.add_column(
        "user_category_preferences",
        sa.Column("category_type", sa.String(), nullable=True),
    )

    # 2. Add is_custom
    op.add_column(
        "user_category_preferences",
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 3. Drop hidden
    op.drop_column("user_category_preferences", "hidden")

    # 4. Backfill category_type for known expense categories
    op.execute("""
        UPDATE user_category_preferences
        SET category_type = 'expense'
        WHERE category IN (
            'Alimentación','Supermercado','Transporte','Combustible',
            'Entretenimiento','Salud','Farmacia','Hogar',
            'Ropa','Tecnología','Educación','Viajes','Servicios','Otros'
        )
    """)

    # 5. Backfill category_type for known income categories
    op.execute("""
        UPDATE user_category_preferences
        SET category_type = 'income'
        WHERE category IN (
            'Sueldo','Freelance','Inversiones','Arriendo','Bono',
            'Transferencia de terceros','Deuda pendiente','Otros ingresos'
        )
    """)

    # 6. Remaining nulls (unknown/custom categories) default to 'expense'
    op.execute("""
        UPDATE user_category_preferences
        SET category_type = 'expense'
        WHERE category_type IS NULL
    """)

    # 7. Now set NOT NULL
    op.alter_column("user_category_preferences", "category_type", nullable=False)

    # 8. Seed defaults for every user that currently has ZERO rows
    op.execute("""
        INSERT INTO user_category_preferences
            (id, user_id, category, category_type, is_custom, sort_order)
        SELECT
            gen_random_uuid(), u.id,
            defaults.category, defaults.category_type, false, defaults.sort_order
        FROM users u
        CROSS JOIN (VALUES
            ('Alimentación','expense',0), ('Supermercado','expense',1),
            ('Transporte','expense',2),  ('Combustible','expense',3),
            ('Entretenimiento','expense',4), ('Salud','expense',5),
            ('Farmacia','expense',6),    ('Hogar','expense',7),
            ('Ropa','expense',8),        ('Tecnología','expense',9),
            ('Educación','expense',10),  ('Viajes','expense',11),
            ('Servicios','expense',12),  ('Otros','expense',13),
            ('Sueldo','income',0),       ('Freelance','income',1),
            ('Inversiones','income',2),  ('Arriendo','income',3),
            ('Bono','income',4),
            ('Transferencia de terceros','income',5),
            ('Deuda pendiente','income',6), ('Otros ingresos','income',7)
        ) AS defaults(category, category_type, sort_order)
        WHERE NOT EXISTS (
            SELECT 1 FROM user_category_preferences ucp WHERE ucp.user_id = u.id
        )
    """)

    # 9. Add user_id to merchant_category_selections (nullable)
    op.add_column(
        "merchant_category_selections",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 9b. Create FK separately (op.add_column silently ignores ForeignKey constraints)
    op.create_foreign_key(
        "fk_merchant_category_selections_user_id",
        "merchant_category_selections",
        "users",
        ["user_id"],
        ["id"],
    )

    # 10. Partial unique index for per-user rows
    op.execute("""
        CREATE UNIQUE INDEX uq_merchant_category_user
        ON merchant_category_selections (merchant_id, user_id, category)
        WHERE user_id IS NOT NULL
    """)

    # 11. Partial unique index for legacy global rows
    op.execute("""
        CREATE UNIQUE INDEX uq_merchant_category_global
        ON merchant_category_selections (merchant_id, category)
        WHERE user_id IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_merchant_category_user")
    op.execute("DROP INDEX IF EXISTS uq_merchant_category_global")
    op.drop_constraint(
        "fk_merchant_category_selections_user_id",
        "merchant_category_selections",
        type_="foreignkey",
    )
    op.drop_column("merchant_category_selections", "user_id")
    op.add_column(
        "user_category_preferences",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_column("user_category_preferences", "is_custom")
    op.drop_column("user_category_preferences", "category_type")
