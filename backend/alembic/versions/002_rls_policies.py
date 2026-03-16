"""Enable RLS policies on transactions table.

Revision ID: 002
Down revision: 001
"""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    # Enable RLS on transactions
    op.execute("ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;")

    # Policy: users see their own transactions
    op.execute("""
        CREATE POLICY own_transactions ON transactions
        FOR SELECT
        USING (user_id = auth.uid());
    """)

    # Policy: all household members see shared transactions
    op.execute("""
        CREATE POLICY shared_transactions ON transactions
        FOR SELECT
        USING (
            household_id IN (
                SELECT household_id FROM household_members
                WHERE user_id = auth.uid()
            )
            AND id IN (
                SELECT transaction_id FROM transaction_splits
                WHERE split_type = 'shared'
            )
        );
    """)

    # INSERT/UPDATE/DELETE policies are not needed here:
    # The backend (ARQ worker + FastAPI) connects via Supabase service_role
    # which has BYPASSRLS privilege in Supabase — writes always succeed.

    # Partner aggregate stats function — SECURITY DEFINER so it can read all rows
    # but returns only aggregates, never raw partner rows
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
            -- Guard: viewer must be a member of this household
            IF NOT EXISTS (
                SELECT 1 FROM household_members
                WHERE household_id = p_household_id AND user_id = p_viewer_id
            ) THEN
                RETURN '{"error": "not a member"}'::JSON;
            END IF;

            -- Find partner (other member of household)
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


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS get_partner_stats;")
    op.execute("DROP POLICY IF EXISTS shared_transactions ON transactions;")
    op.execute("DROP POLICY IF EXISTS own_transactions ON transactions;")
    op.execute("ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;")
