import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
