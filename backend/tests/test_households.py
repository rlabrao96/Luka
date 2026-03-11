import pytest
from modules.households.service import create_household, create_invite, accept_invite


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_create_individual_household(db, mock_user):
    household = await create_household(
        db=db, owner=mock_user, name="Rafa", household_type="individual"
    )
    assert household.type == "individual"
    assert household.name == "Rafa"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_create_invite_generates_token(db, mock_user):
    household = await create_household(
        db=db, owner=mock_user, name="Rafa & Cami", household_type="couple"
    )
    invite = await create_invite(
        db=db, household=household, invited_by=mock_user, invited_email="cami@test.cl"
    )
    assert invite.token is not None
    assert len(invite.token) > 10
    assert invite.invited_email == "cami@test.cl"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_accept_invite_adds_member(db, mock_user, mock_partner):
    household = await create_household(
        db=db, owner=mock_user, name="Rafa & Cami", household_type="couple"
    )
    invite = await create_invite(
        db=db, household=household, invited_by=mock_user, invited_email=mock_partner.email
    )
    result = await accept_invite(db=db, token=invite.token, user=mock_partner)
    assert result.accepted_at is not None
