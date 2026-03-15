import pytest
from modules.households.service import get_contribution_summary, get_partner_stats


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_contribution_summary_returns_both_users(db, mock_user, mock_partner, mock_household):
    summary = await get_contribution_summary(db, household_id=mock_household.id)
    assert len(summary) == 2
    user_ids = {row["user_id"] for row in summary}
    assert mock_user.id in user_ids
    assert mock_partner.id in user_ids


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_partner_stats_returns_only_aggregates(db, mock_user, mock_partner, mock_household):
    stats = await get_partner_stats(db, household_id=mock_household.id, requester_id=mock_user.id)
    assert "total_spent" in stats
    assert "by_category" in stats
    # Must NOT contain individual transaction rows
    assert "transactions" not in stats
