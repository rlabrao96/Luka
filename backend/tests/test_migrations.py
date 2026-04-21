import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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


@pytest.mark.asyncio
async def test_039_adds_consolidation_columns(db: AsyncSession):
    """Migration 039 must add card_last_four, refund_pair_id, orphaned_at, dismissed_by_user."""
    result = await db.execute(
        text(
            """
            SELECT column_name, is_nullable, data_type
            FROM information_schema.columns
            WHERE table_name = 'transactions'
              AND column_name IN (
                'card_last_four', 'refund_pair_id', 'orphaned_at', 'dismissed_by_user'
              )
            """
        )
    )
    cols = {row[0]: (row[1], row[2]) for row in result}
    assert "card_last_four" in cols
    assert cols["card_last_four"][0] == "YES"
    assert "refund_pair_id" in cols
    assert cols["refund_pair_id"][0] == "YES"
    assert cols["refund_pair_id"][1] == "uuid"
    assert "orphaned_at" in cols
    assert cols["orphaned_at"][0] == "YES"
    assert "dismissed_by_user" in cols
    assert cols["dismissed_by_user"][0] == "NO"


@pytest.mark.asyncio
async def test_039_status_check_rejects_bogus_values(db: AsyncSession):
    """The new CHECK constraint must reject status values outside pending|settled|orphan."""
    # Pull an existing transaction id to target with an UPDATE (avoids FK/NOT-NULL pain on INSERT).
    existing = await db.execute(text("SELECT id FROM transactions LIMIT 1"))
    row = existing.first()
    if row is None:
        pytest.skip("No transactions in DB to exercise the CHECK constraint against")
    tx_id = row[0]

    await db.execute(text("SAVEPOINT s_bogus"))
    with pytest.raises(IntegrityError):
        await db.execute(
            text("UPDATE transactions SET status = 'bogus_status' WHERE id = :id"),
            {"id": tx_id},
        )
        await db.flush()
    await db.execute(text("ROLLBACK TO SAVEPOINT s_bogus"))


@pytest.mark.asyncio
async def test_039_status_check_accepts_valid_values(db: AsyncSession):
    """The new CHECK constraint must accept pending, settled, and orphan."""
    existing = await db.execute(text("SELECT id, status FROM transactions LIMIT 1"))
    row = existing.first()
    if row is None:
        pytest.skip("No transactions in DB to exercise the CHECK constraint against")
    tx_id, original_status = row[0], row[1]

    for valid in ("pending", "settled", "orphan"):
        await db.execute(
            text("UPDATE transactions SET status = :s WHERE id = :id"),
            {"s": valid, "id": tx_id},
        )
        await db.flush()

    # Restore (fixture rollback will also undo, but keep the row coherent for any later assertion).
    await db.execute(
        text("UPDATE transactions SET status = :s WHERE id = :id"),
        {"s": original_status, "id": tx_id},
    )


@pytest.mark.asyncio
async def test_039_pg_trgm_extension_enabled(db: AsyncSession):
    result = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_039_expected_indexes_exist(db: AsyncSession):
    result = await db.execute(
        text(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'transactions'
              AND indexname IN (
                'ix_transactions_household_date',
                'ix_transactions_user_pending',
                'ix_transactions_transfer_pair',
                'ix_transactions_refund_pair',
                'ix_transactions_raw_merchant_trgm'
              )
            """
        )
    )
    found = {row[0] for row in result}
    assert found == {
        "ix_transactions_household_date",
        "ix_transactions_user_pending",
        "ix_transactions_transfer_pair",
        "ix_transactions_refund_pair",
        "ix_transactions_raw_merchant_trgm",
    }
