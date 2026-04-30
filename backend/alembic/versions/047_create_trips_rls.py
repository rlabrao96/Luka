"""047 — RLS policies + helper functions for Viajes (Trips)

Revision ID: 047
Revises: 046

Defines two SECURITY DEFINER helper functions
(`is_trip_member`, `is_active_trip_member`), enables RLS on all eight
`trip_*` tables, and creates the per-table policies described in
Viajes design spec §3.11.

The helper functions are SECURITY DEFINER so policies that consult
`trip_attendees` do not recurse into the RLS check on `trip_attendees`
itself.
"""

from alembic import op


revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


TRIP_TABLES = [
    "trips",
    "trip_attendees",
    "trip_expenses",
    "trip_expense_splits",
    "trip_settlements",
    "trip_suggestion_dismissals",
    "trip_settlement_dismissals",
    "trip_base_currency_changes",
]


def upgrade() -> None:
    # ---- 1. Helper functions ------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.is_trip_member(
            p_trip_id uuid,
            p_user_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = public
        AS $$
            SELECT EXISTS (
                SELECT 1
                FROM trip_attendees
                WHERE trip_id = p_trip_id
                  AND user_id = p_user_id
            );
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.is_active_trip_member(
            p_trip_id uuid,
            p_user_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = public
        AS $$
            SELECT EXISTS (
                SELECT 1
                FROM trip_attendees
                WHERE trip_id = p_trip_id
                  AND user_id = p_user_id
                  AND left_at IS NULL
            );
        $$;
        """
    )

    # ---- 2. Enable RLS on all trip_* tables ---------------------------------
    for t in TRIP_TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;")

    # ---- 3. Policies --------------------------------------------------------

    # trips ------------------------------------------------------------------
    op.execute(
        """
        CREATE POLICY trips_select ON trips
            FOR SELECT
            USING (is_trip_member(id, auth.uid()));
        """
    )
    op.execute(
        """
        CREATE POLICY trips_insert ON trips
            FOR INSERT
            WITH CHECK (creator_user_id = auth.uid());
        """
    )
    op.execute(
        """
        CREATE POLICY trips_update ON trips
            FOR UPDATE
            USING (creator_user_id = auth.uid())
            WITH CHECK (creator_user_id = auth.uid());
        """
    )
    op.execute(
        """
        CREATE POLICY trips_delete ON trips
            FOR DELETE
            USING (creator_user_id = auth.uid());
        """
    )

    # trip_attendees ---------------------------------------------------------
    op.execute(
        """
        CREATE POLICY trip_attendees_select ON trip_attendees
            FOR SELECT
            USING (is_trip_member(trip_id, auth.uid()));
        """
    )
    op.execute(
        """
        CREATE POLICY trip_attendees_insert ON trip_attendees
            FOR INSERT
            WITH CHECK (is_active_trip_member(trip_id, auth.uid()));
        """
    )
    op.execute(
        """
        CREATE POLICY trip_attendees_update ON trip_attendees
            FOR UPDATE
            USING (
                user_id = auth.uid()
                OR EXISTS (
                    SELECT 1 FROM trips
                    WHERE id = trip_id
                      AND creator_user_id = auth.uid()
                )
            )
            WITH CHECK (
                user_id = auth.uid()
                OR EXISTS (
                    SELECT 1 FROM trips
                    WHERE id = trip_id
                      AND creator_user_id = auth.uid()
                )
            );
        """
    )
    op.execute(
        """
        CREATE POLICY trip_attendees_delete ON trip_attendees
            FOR DELETE
            USING (
                EXISTS (
                    SELECT 1 FROM trips
                    WHERE id = trip_id
                      AND creator_user_id = auth.uid()
                )
            );
        """
    )

    # trip_expenses, trip_settlements (same pattern) -------------------------
    for t in ("trip_expenses", "trip_settlements"):
        op.execute(
            f"""
            CREATE POLICY {t}_select ON {t}
                FOR SELECT
                USING (is_trip_member(trip_id, auth.uid()));
            """
        )
        op.execute(
            f"""
            CREATE POLICY {t}_all ON {t}
                FOR ALL
                USING (is_active_trip_member(trip_id, auth.uid()))
                WITH CHECK (is_active_trip_member(trip_id, auth.uid()));
            """
        )

    # trip_expense_splits (no trip_id; join via trip_expenses) ---------------
    op.execute(
        """
        CREATE POLICY trip_expense_splits_select ON trip_expense_splits
            FOR SELECT
            USING (
                EXISTS (
                    SELECT 1 FROM trip_expenses te
                    WHERE te.id = trip_expense_id
                      AND is_trip_member(te.trip_id, auth.uid())
                )
            );
        """
    )
    op.execute(
        """
        CREATE POLICY trip_expense_splits_all ON trip_expense_splits
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM trip_expenses te
                    WHERE te.id = trip_expense_id
                      AND is_active_trip_member(te.trip_id, auth.uid())
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM trip_expenses te
                    WHERE te.id = trip_expense_id
                      AND is_active_trip_member(te.trip_id, auth.uid())
                )
            );
        """
    )

    # trip_suggestion_dismissals, trip_settlement_dismissals -----------------
    for t in ("trip_suggestion_dismissals", "trip_settlement_dismissals"):
        op.execute(
            f"""
            CREATE POLICY {t}_all ON {t}
                FOR ALL
                USING (user_id = auth.uid())
                WITH CHECK (user_id = auth.uid());
            """
        )

    # trip_base_currency_changes --------------------------------------------
    op.execute(
        """
        CREATE POLICY trip_base_currency_changes_select ON trip_base_currency_changes
            FOR SELECT
            USING (is_trip_member(trip_id, auth.uid()));
        """
    )
    op.execute(
        """
        CREATE POLICY trip_base_currency_changes_insert ON trip_base_currency_changes
            FOR INSERT
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM trips
                    WHERE id = trip_id
                      AND creator_user_id = auth.uid()
                )
            );
        """
    )


def downgrade() -> None:
    # ---- Drop policies ------------------------------------------------------
    policies = [
        ("trips", ["trips_select", "trips_insert", "trips_update", "trips_delete"]),
        (
            "trip_attendees",
            [
                "trip_attendees_select",
                "trip_attendees_insert",
                "trip_attendees_update",
                "trip_attendees_delete",
            ],
        ),
        ("trip_expenses", ["trip_expenses_select", "trip_expenses_all"]),
        ("trip_settlements", ["trip_settlements_select", "trip_settlements_all"]),
        (
            "trip_expense_splits",
            ["trip_expense_splits_select", "trip_expense_splits_all"],
        ),
        ("trip_suggestion_dismissals", ["trip_suggestion_dismissals_all"]),
        ("trip_settlement_dismissals", ["trip_settlement_dismissals_all"]),
        (
            "trip_base_currency_changes",
            [
                "trip_base_currency_changes_select",
                "trip_base_currency_changes_insert",
            ],
        ),
    ]
    for table, names in policies:
        for name in names:
            op.execute(f"DROP POLICY IF EXISTS {name} ON {table};")

    # ---- Disable RLS --------------------------------------------------------
    for t in TRIP_TABLES:
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")

    # ---- Drop helper functions ---------------------------------------------
    op.execute("DROP FUNCTION IF EXISTS public.is_active_trip_member(uuid, uuid);")
    op.execute("DROP FUNCTION IF EXISTS public.is_trip_member(uuid, uuid);")
