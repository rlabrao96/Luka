import pytest
from sqlalchemy import text

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


# -----------------------------------------------------------------------------
# Data-integrity regression tests
#
# These exist because a manual SQL UPDATE on 2026-04-08 left a user with zero
# active household_members rows, causing his next login to loop back into
# onboarding (/auth/me returned household_id=null). See migration 034.
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_partial_unique_index_exists(db):
    """Migration 034 must have created the partial unique index that prevents
    a user from having >1 active household_members rows."""
    result = await db.execute(
        text(
            """
            SELECT indexdef FROM pg_indexes
            WHERE tablename = 'household_members'
              AND indexname = 'uq_household_members_user_active'
            """
        )
    )
    indexdef = result.scalar()
    assert indexdef is not None, "uq_household_members_user_active index missing"
    assert "UNIQUE" in indexdef.upper()
    assert "left_at IS NULL" in indexdef


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_no_user_has_multiple_active_memberships(db):
    """Invariant: each user has AT MOST one active household_members row.
    Enforced by the partial unique index from migration 034."""
    result = await db.execute(
        text(
            """
            SELECT user_id, COUNT(*) AS active_count
            FROM household_members
            WHERE left_at IS NULL
            GROUP BY user_id
            HAVING COUNT(*) > 1
            """
        )
    )
    offenders = result.all()
    assert offenders == [], f"Users with multiple active memberships: {offenders}"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_no_orphaned_users(db):
    """Invariant: every users row has at least one active household_members row.
    Not enforced by DB constraints — this is the manual integrity check that
    would have caught Juan's orphaned state on 2026-04-08."""
    result = await db.execute(
        text(
            """
            SELECT u.id, u.email
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM household_members hm
                WHERE hm.user_id = u.id AND hm.left_at IS NULL
            )
            """
        )
    )
    orphans = result.all()
    assert orphans == [], (
        f"Users with zero active household memberships: {orphans}. "
        "These users will be redirected to onboarding on next login."
    )


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL — run manually after DB setup")
async def test_partial_unique_index_blocks_duplicate_active(db, mock_user):
    """Attempting to insert a second active membership for the same user must
    fail with a unique violation."""
    from sqlalchemy.exc import IntegrityError

    from modules.households.models import HouseholdMember

    h1 = await create_household(db, mock_user, "Primero", "individual")
    h2 = await create_household(db, mock_user, "Segundo", "individual")
    db.add(HouseholdMember(household_id=h2.id, user_id=mock_user.id, role="owner"))
    with pytest.raises(IntegrityError):
        await db.flush()
    # `h1` already created the first active row during create_household;
    # the second insert above must be rejected by uq_household_members_user_active.
    assert h1.id != h2.id
