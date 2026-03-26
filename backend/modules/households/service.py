import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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

    # Prevent inviter from accepting their own invite
    if invite.invited_by == user.id:
        raise ValueError(
            "No puedes aceptar tu propia invitación. Abre el enlace en el navegador de tu pareja."
        )

    # Prevent user who is already a member of this household
    existing = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == invite.household_id,
            HouseholdMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Ya eres miembro de este hogar.")

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


def build_category_breakdown(rows: list[dict]) -> list[dict]:
    """Pure function: groups SQL rows into category breakdown with percentages."""
    if not rows:
        return []

    cats: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        cats[row["category"]].append(row)

    grand_total = sum(r["amount"] for r in rows)
    result = []
    for category, members in sorted(
        cats.items(), key=lambda x: sum(m["amount"] for m in x[1]), reverse=True
    ):
        cat_total = sum(m["amount"] for m in members)
        member_totals = [
            {
                "user_id": str(m["user_id"]),
                "full_name": m["full_name"],
                "amount": m["amount"],
                "pct": round(float(m["amount"]) / float(cat_total) * 100, 1) if cat_total else 0,
            }
            for m in members
        ]
        result.append(
            {
                "category": category,
                "member_totals": member_totals,
                "total": cat_total,
                "pct_of_overall": round(float(cat_total) / float(grand_total) * 100, 1)
                if grand_total
                else 0,
            }
        )
    return result


async def get_category_breakdown(db: AsyncSession, household_id, month: str | None = None):
    """Returns per-category spending breakdown for shared transactions."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = (
            "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"
        )

    sql = text(f"""
        SELECT u.id AS user_id, u.full_name,
               COALESCE(t.category, 'Sin categoría') AS category,
               COALESCE(SUM(ABS(t.amount)), 0) AS amount
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND {month_clause}
        GROUP BY u.id, u.full_name, COALESCE(t.category, 'Sin categoría')
        ORDER BY amount DESC
    """)
    result = await db.execute(sql, params)
    rows = [dict(r._mapping) for r in result.all()]
    return build_category_breakdown(rows)


def calculate_settlement(members: list[dict], split_ratio: list[int]) -> dict:
    """Pure function: calculates who owes whom based on actual spending and ratio."""
    if len(members) != 2:
        return {
            "from_user_id": "",
            "from_user_name": "",
            "to_user_id": "",
            "to_user_name": "",
            "amount": Decimal("0"),
        }

    grand_total = sum(m["total"] for m in members)
    if grand_total == 0:
        return {
            "from_user_id": str(members[0]["user_id"]),
            "from_user_name": members[0]["full_name"],
            "to_user_id": str(members[1]["user_id"]),
            "to_user_name": members[1]["full_name"],
            "amount": Decimal("0"),
        }

    expected_0 = grand_total * Decimal(split_ratio[0]) / Decimal(100)
    diff_0 = expected_0 - members[0]["total"]

    if diff_0 > 0:
        return {
            "from_user_id": str(members[0]["user_id"]),
            "from_user_name": members[0]["full_name"],
            "to_user_id": str(members[1]["user_id"]),
            "to_user_name": members[1]["full_name"],
            "amount": diff_0,
        }
    else:
        return {
            "from_user_id": str(members[1]["user_id"]),
            "from_user_name": members[1]["full_name"],
            "to_user_id": str(members[0]["user_id"]),
            "to_user_name": members[0]["full_name"],
            "amount": abs(diff_0),
        }


async def get_settlement(db: AsyncSession, household_id, month: str | None = None):
    """Returns settlement suggestion for the household."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = (
            "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"
        )

    sql = text(f"""
        SELECT u.id AS user_id, u.full_name,
               COALESCE(SUM(ABS(t.amount)), 0) AS total
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND {month_clause}
        GROUP BY u.id, u.full_name
        ORDER BY total DESC
    """)
    result = await db.execute(sql, params)
    members = [dict(r._mapping) for r in result.all()]

    h_result = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    row = h_result.scalar_one_or_none()
    split_ratio = row if row else [50, 50]

    settlement = calculate_settlement(members, split_ratio)
    settlement["split_ratio"] = split_ratio
    settlement["month"] = month or "current"
    return settlement


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
