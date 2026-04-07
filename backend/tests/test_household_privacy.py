import pytest
from modules.households.service import get_contribution_summary, get_member_stats


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
async def test_member_stats_returns_only_aggregates(db, mock_user, mock_partner, mock_household):
    stats = await get_member_stats(db, household_id=mock_household.id, requester_id=mock_user.id)
    assert isinstance(stats, list)
    # Must return list of members with aggregate data, not individual transaction rows
    for member in stats:
        assert "user_id" in member
        assert "full_name" in member
        assert "total_spent" in member
