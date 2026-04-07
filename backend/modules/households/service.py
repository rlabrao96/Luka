import json
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
    db: AsyncSession, household: Household, invited_by: User, invited_email: str | None
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
            "No puedes aceptar tu propia invitación. Abre el enlace en el navegador del otro miembro."
        )

    # Prevent user who is already a member of this household
    existing_in_target = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == invite.household_id,
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if existing_in_target.scalar_one_or_none():
        raise ValueError("Ya eres miembro de este hogar.")

    # Max 5 members check
    active_count_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM household_members WHERE household_id = :hid AND left_at IS NULL"
        ),
        {"hid": str(invite.household_id)},
    )
    if active_count_result.scalar() >= 5:
        raise ValueError("Este grupo ya tiene el máximo de 5 miembros.")

    # If user is in another group, auto-leave their individual household (only if individual)
    existing_elsewhere = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    current_membership = existing_elsewhere.scalar_one_or_none()
    if current_membership:
        # Check if it's an individual household — if so, soft-leave it
        h_result = await db.execute(
            select(Household).where(Household.id == current_membership.household_id)
        )
        current_household = h_result.scalar_one_or_none()
        if current_household and current_household.type == "individual":
            current_membership.left_at = datetime.now(timezone.utc)
        else:
            raise ValueError(
                "Ya eres miembro de otro grupo. Debes salir de ese grupo antes de unirte a uno nuevo."
            )

    invite.accepted_at = datetime.now(timezone.utc)
    member = HouseholdMember(household_id=invite.household_id, user_id=user.id, role="member")
    db.add(member)

    # Auto-adjust split ratio to equal shares for new member count
    new_count_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM household_members WHERE household_id = :hid AND left_at IS NULL"
        ),
        {"hid": str(invite.household_id)},
    )
    # +1 for the member we just added (not yet committed)
    new_count = new_count_result.scalar() + 1
    equal_ratio = _equal_ratio(new_count)
    await db.execute(
        text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
        {"ratio": json.dumps(equal_ratio), "id": str(invite.household_id)},
    )

    await db.commit()
    await db.refresh(invite)
    return invite


async def remove_member(
    db: AsyncSession, household_id: uuid.UUID, member_id: uuid.UUID
) -> uuid.UUID:
    """Soft-delete a member from a household. Returns the new individual household id."""
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise ValueError("Member not found in this household")

    removed_user_id = member.user_id

    # Soft-delete the membership
    member.left_at = datetime.now(timezone.utc)

    # Deactivate bank accounts belonging to this user in this household
    await db.execute(
        text(
            "UPDATE bank_accounts SET is_active = false WHERE user_id = :uid AND household_id = :hid"
        ),
        {"uid": str(removed_user_id), "hid": str(household_id)},
    )

    # Create a new individual household for the removed user
    user_result = await db.execute(
        text("SELECT full_name FROM users WHERE id = :id"),
        {"id": str(removed_user_id)},
    )
    user_row = user_result.one_or_none()
    new_name = f"Personal de {user_row.full_name}" if user_row else "Mi cuenta personal"
    new_household = Household(name=new_name, type="individual")
    db.add(new_household)
    await db.flush()

    new_member = HouseholdMember(
        household_id=new_household.id, user_id=removed_user_id, role="owner"
    )
    db.add(new_member)

    # Auto-adjust split ratio for remaining members
    remaining_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM household_members WHERE household_id = :hid AND left_at IS NULL"
        ),
        {"hid": str(household_id)},
    )
    # -1 for the member we just soft-deleted (not yet committed)
    remaining_count = remaining_result.scalar() - 1
    if remaining_count >= 2:
        equal_ratio = _equal_ratio(remaining_count)
        await db.execute(
            text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
            {"ratio": json.dumps(equal_ratio), "id": str(household_id)},
        )

    await db.commit()
    await db.refresh(new_household)
    return new_household.id


async def get_household_members(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Return active members with their roles."""
    result = await db.execute(
        text("""
            SELECT hm.id, hm.user_id, hm.role, hm.joined_at,
                   u.full_name, u.email
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            WHERE hm.household_id = :hid AND hm.left_at IS NULL
            ORDER BY hm.joined_at ASC
        """),
        {"hid": str(household_id)},
    )
    return [dict(row._mapping) for row in result.all()]


async def get_pending_invites(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Return non-accepted, non-expired invites."""
    result = await db.execute(
        text("""
            SELECT hi.id, hi.token, hi.invited_email, hi.expires_at, hi.created_at,
                   u.full_name AS invited_by_name
            FROM household_invites hi
            JOIN users u ON u.id = hi.invited_by
            WHERE hi.household_id = :hid
              AND hi.accepted_at IS NULL
              AND hi.expires_at > NOW()
            ORDER BY hi.created_at DESC
        """),
        {"hid": str(household_id)},
    )
    return [dict(row._mapping) for row in result.all()]


def _equal_ratio(n: int) -> list[int]:
    """Return equal split ratio for n members summing to 100."""
    base = 100 // n
    remainder = 100 % n
    ratio = [base] * n
    for i in range(remainder):
        ratio[i] += 1
    return ratio


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
        JOIN household_members hm ON hm.user_id = u.id AND hm.household_id = t.household_id
        WHERE t.household_id = :household_id
          AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
          AND hm.left_at IS NULL
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
        JOIN household_members hm ON hm.user_id = u.id AND hm.household_id = t.household_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND hm.left_at IS NULL
          AND {month_clause}
        GROUP BY u.id, u.full_name, COALESCE(t.category, 'Sin categoría')
        ORDER BY amount DESC
    """)
    result = await db.execute(sql, params)
    rows = [dict(r._mapping) for r in result.all()]
    return build_category_breakdown(rows)


def calculate_settlement(members: list[dict], split_ratio: list[int]) -> list[dict]:
    """Pool-based settlement for N members. Returns minimal list of transfers."""
    if len(members) <= 1 or not split_ratio:
        return []

    grand_total = sum(m["total"] for m in members)
    if grand_total == 0:
        return []

    # Calculate each member's balance (positive = overpaid/creditor, negative = underpaid/debtor)
    balances = []
    for i, member in enumerate(members):
        ratio = Decimal(split_ratio[i]) if i < len(split_ratio) else Decimal(0)
        expected = grand_total * ratio / Decimal(100)
        balance = member["total"] - expected
        balances.append(
            {
                "user_id": str(member["user_id"]),
                "full_name": member["full_name"],
                "balance": balance,
            }
        )

    # Greedy algorithm: match largest creditor with largest debtor
    transfers = []
    creditors = sorted(
        [b for b in balances if b["balance"] > 0],
        key=lambda x: x["balance"],
        reverse=True,
    )
    debtors = sorted(
        [b for b in balances if b["balance"] < 0],
        key=lambda x: x["balance"],
    )

    ci, di = 0, 0
    while ci < len(creditors) and di < len(debtors):
        creditor = creditors[ci]
        debtor = debtors[di]
        amount = min(creditor["balance"], abs(debtor["balance"]))
        if amount > 0:
            transfers.append(
                {
                    "from_user_id": debtor["user_id"],
                    "from_user_name": debtor["full_name"],
                    "to_user_id": creditor["user_id"],
                    "to_user_name": creditor["full_name"],
                    "amount": amount,
                }
            )
        creditor["balance"] -= amount
        debtor["balance"] += amount
        if creditor["balance"] == 0:
            ci += 1
        if debtor["balance"] == 0:
            di += 1

    return transfers


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
        JOIN household_members hm ON hm.user_id = u.id AND hm.household_id = t.household_id
        WHERE t.household_id = :household_id
          AND ts.split_type = 'shared'
          AND t.transaction_type = 'expense'
          AND hm.left_at IS NULL
          AND {month_clause}
        GROUP BY u.id, u.full_name
        ORDER BY total DESC
    """)
    result = await db.execute(sql, params)
    members = [dict(r._mapping) for r in result.all()]

    h_result = await db.execute(
        text("SELECT split_ratio, settlement_enabled FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    row = h_result.one_or_none()
    split_ratio = row.split_ratio if row and row.split_ratio else [50, 50]
    settlement_enabled = row.settlement_enabled if row else True

    transfers = calculate_settlement(members, split_ratio) if settlement_enabled else []

    return {
        "settlement_enabled": settlement_enabled,
        "transfers": transfers,
        "split_ratio": split_ratio,
        "month": month or "current",
    }


async def get_member_stats(
    db: AsyncSession, household_id: uuid.UUID, requester_id: uuid.UUID
) -> list[dict]:
    """Aggregate stats for all active members — no individual transaction rows."""
    result = await db.execute(
        text("""
            SELECT u.id AS user_id, u.full_name,
                   COALESCE(SUM(ABS(t.amount)) FILTER (WHERE t.transaction_type = 'expense'), 0) AS total_spent
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            LEFT JOIN transactions t ON t.user_id = u.id AND t.household_id = :household_id
            WHERE hm.household_id = :household_id
              AND hm.left_at IS NULL
              AND hm.user_id != :viewer_id
            GROUP BY u.id, u.full_name
        """),
        {"household_id": str(household_id), "viewer_id": str(requester_id)},
    )
    return [dict(r._mapping) for r in result.all()]
