import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_all_tables_exist(db: AsyncSession):
    expected_tables = [
        "users",
        "households",
        "household_members",
        "household_invites",
        "bank_accounts",
        "household_budgets",
        "merchants",
        "merchant_category_selections",
        "transactions",
        "transaction_splits",
        "processed_webhooks",
        "failed_jobs",
    ]
    for table in expected_tables:
        result = await db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"), {"t": table}
        )
        assert result.scalar() == 1, f"Table '{table}' not found"
