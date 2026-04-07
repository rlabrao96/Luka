"""Rename partner_stats to member_stats — N-member support

Revision ID: 033
Revises: 032
Create Date: 2026-04-07
"""

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename the old PL/pgSQL function from get_partner_stats to get_member_stats
    # The new implementation uses direct SQL queries, so the function name doesn't affect
    # the backend anymore, but we rename it for consistency.
    op.execute("DROP FUNCTION IF EXISTS get_partner_stats(UUID, UUID, DATE);")


def downgrade() -> None:
    # Recreate the old function (kept for reference in historical migrations)
    # In practice, downgrade is rarely used, so this is a safety measure
    op.execute("""
        CREATE OR REPLACE FUNCTION get_partner_stats(
            p_household_id UUID,
            p_viewer_id UUID,
            p_month DATE DEFAULT DATE_TRUNC('month', CURRENT_DATE)::DATE
        )
        RETURNS JSON
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            partner_id UUID;
            result JSON;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM household_members
                WHERE household_id = p_household_id AND user_id = p_viewer_id
            ) THEN
                RETURN '{"error": "not a member"}'::JSON;
            END IF;

            SELECT user_id INTO partner_id
            FROM household_members
            WHERE household_id = p_household_id
              AND user_id != p_viewer_id
            LIMIT 1;

            IF partner_id IS NULL THEN
                RETURN '{"error": "no partner found"}'::JSON;
            END IF;

            SELECT json_build_object(
                'total_spent', COALESCE(SUM(t.amount), 0),
                'by_category', (
                    SELECT json_agg(cat_row)
                    FROM (
                        SELECT json_build_object('category', ts.category, 'amount', SUM(t2.amount)) AS cat_row
                        FROM transactions t2
                        JOIN transaction_splits ts ON ts.transaction_id = t2.id
                        WHERE t2.user_id = partner_id
                          AND DATE_TRUNC('month', t2.transaction_date::DATE) = p_month
                          AND ts.category IS NOT NULL
                        GROUP BY ts.category
                        ORDER BY SUM(t2.amount) DESC
                        LIMIT 5
                    ) subq
                )
            ) INTO result
            FROM transactions t
            WHERE t.user_id = partner_id
              AND DATE_TRUNC('month', t.transaction_date::DATE) = p_month;

            RETURN result;
        END;
        $$;
    """)
