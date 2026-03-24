import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from modules.households.models import Household, HouseholdMember, HouseholdInvite
from modules.auth.models import User


async def create_household(
    db: AsyncSession, owner: User, name: str, household_type: str
) -> Household:
    household = Household(name=name, type=household_type)
    db.add(household)
    await db.flush()

    member = HouseholdMember(household_id=household.id, user_id=owner.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(household)
    return household


async def create_invite(
    db: AsyncSession, household: Household, invited_by: User, invited_email: str
) -> HouseholdInvite:
    invite = HouseholdInvite(
        household_id=household.id,
        invited_by=invited_by.id,
        invited_email=invited_email,
        token=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def accept_invite(db: AsyncSession, token: str, user: User) -> HouseholdInvite:
    result = await db.execute(select(HouseholdInvite).where(HouseholdInvite.token == token))
    invite = result.scalar_one_or_none()
    if not invite or invite.expires_at < datetime.now(timezone.utc):
        raise ValueError("Invite not found or expired")
    if invite.accepted_at:
        raise ValueError("Invite already accepted")

    invite.accepted_at = datetime.now(timezone.utc)
    member = HouseholdMember(household_id=invite.household_id, user_id=user.id, role="member")
    db.add(member)
    await db.commit()
    await db.refresh(invite)
    return invite


async def get_contribution_summary(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Monthly household spending by member. No privacy restriction — both members see this."""
    result = await db.execute(
        text("""
        SELECT
            t.user_id,
            u.full_name,
            u.email,
            COALESCE(SUM(t.amount), 0) AS total_paid,
            COALESCE(SUM(t.amount) FILTER (WHERE ts.split_type = 'shared'), 0) AS shared_paid,
            COALESCE(SUM(t.amount) FILTER (WHERE ts.split_type = 'personal'), 0) AS personal_paid
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
        GROUP BY t.user_id, u.full_name, u.email
        """),
        {"household_id": str(household_id)},
    )
    return [dict(row._mapping) for row in result.all()]


async def get_partner_stats(
    db: AsyncSession, household_id: uuid.UUID, requester_id: uuid.UUID
) -> dict:
    """Aggregate stats for partner only — no individual transaction rows."""
    result = await db.execute(
        text("SELECT get_partner_stats(:household_id, :viewer_id)"),
        {"household_id": str(household_id), "viewer_id": str(requester_id)},
    )
    data = result.scalar()
    return data if data is not None else {"total_spent": 0, "by_category": []}
