import json
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from modules.households.models import Household, HouseholdMember, HouseholdInvite
from modules.households.errors import (
    InviteError,
    INVITE_ALREADY_MEMBER,
    INVITE_ALREADY_USED,
    INVITE_EMAIL_MISMATCH,
    INVITE_EXPIRED,
    INVITE_HOUSEHOLD_FULL,
    INVITE_IN_OTHER_GROUP,
    INVITE_NOT_FOUND,
    INVITE_SELF,
)
from modules.auth.models import User

MAX_HOUSEHOLD_MEMBERS = 5


def _is_auto_equal_ratio(ratio: list[int], expected_n: int) -> bool:
    """Return True if `ratio` looks like the auto-generated equal split for
    `expected_n` members. We only rebalance on join/leave when the ratio is
    still the default — owner-customized ratios (e.g., [70, 30]) are preserved."""
    if not ratio or len(ratio) != expected_n:
        return False
    return ratio == _equal_ratio(expected_n)


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
    """Create a fresh invite, revoking any prior pending invite for the same
    (household, email) pair so old links stop working the moment a new one
    is sent. Token is 32 bytes of entropy — secrets.token_urlsafe is a
    capability token, not a UUID."""
    normalized_email = invited_email.lower().strip() if invited_email else None

    if normalized_email:
        await db.execute(
            text(
                """
                UPDATE household_invites
                SET expires_at = NOW()
                WHERE household_id = :hid
                  AND LOWER(invited_email) = :email
                  AND accepted_at IS NULL
                  AND expires_at > NOW()
                """
            ),
            {"hid": str(household.id), "email": normalized_email},
        )

    invite = HouseholdInvite(
        household_id=household.id,
        invited_by=invited_by.id,
        invited_email=normalized_email,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def accept_invite(db: AsyncSession, token: str, user: User) -> HouseholdInvite:
    """Accept an invite atomically.

    The claim is done as a single conditional UPDATE with RETURNING so two
    concurrent accepts cannot both "win" the same invite. After the claim,
    we take a row lock on the target household to serialize the 5-member
    cap check and the membership insert. User-customized split_ratio is
    preserved — we only rebalance when the ratio is still the auto-equal
    default. Orphan data (bank accounts + transactions) from the user's
    old individual household migrates to the new group household.
    """
    now = datetime.now(timezone.utc)

    # Does the invite even exist? (distinguish "wrong token" from "already used")
    existing_result = await db.execute(
        select(HouseholdInvite).where(HouseholdInvite.token == token)
    )
    existing = existing_result.scalar_one_or_none()
    if not existing:
        raise InviteError(INVITE_NOT_FOUND, "Este enlace no existe o ya no es válido.")
    if existing.accepted_at is not None:
        raise InviteError(INVITE_ALREADY_USED, "Este enlace ya fue usado.")
    if existing.expires_at < now:
        raise InviteError(INVITE_EXPIRED, "Este enlace expiró. Pide uno nuevo.")

    # Pre-flight checks that don't depend on the atomic claim.
    if existing.invited_by == user.id:
        raise InviteError(
            INVITE_SELF,
            "No puedes aceptar tu propia invitación. Abre el enlace en el navegador del otro miembro.",
        )
    if existing.invited_email and existing.invited_email.lower() != user.email.lower():
        raise InviteError(
            INVITE_EMAIL_MISMATCH,
            "Este enlace fue enviado a otra dirección de correo. Inicia sesión con la cuenta invitada.",
        )

    # Lock the target household row. Any concurrent accept for this household
    # queues behind us, making the 5-member cap check + insert race-free.
    household_result = await db.execute(
        text("SELECT id, type, split_ratio FROM households WHERE id = :id FOR UPDATE"),
        {"id": str(existing.household_id)},
    )
    household_row = household_result.one_or_none()
    if not household_row:
        raise InviteError(INVITE_NOT_FOUND, "El grupo ya no existe.")

    # Already a member?
    existing_in_target = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == existing.household_id,
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if existing_in_target.scalar_one_or_none():
        raise InviteError(INVITE_ALREADY_MEMBER, "Ya eres miembro de este grupo.")

    # 5-member cap (protected by the FOR UPDATE above).
    count_result = await db.execute(
        text(
            "SELECT COUNT(*) FROM household_members "
            "WHERE household_id = :hid AND left_at IS NULL"
        ),
        {"hid": str(existing.household_id)},
    )
    current_active = count_result.scalar() or 0
    if current_active >= MAX_HOUSEHOLD_MEMBERS:
        raise InviteError(
            INVITE_HOUSEHOLD_FULL,
            f"Este grupo ya tiene el máximo de {MAX_HOUSEHOLD_MEMBERS} miembros.",
        )

    # Resolve the caller's current active membership, if any.
    existing_elsewhere = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    current_membership = existing_elsewhere.scalar_one_or_none()
    old_household_id: uuid.UUID | None = None
    if current_membership:
        old_household_id = current_membership.household_id
        h_result = await db.execute(select(Household).where(Household.id == old_household_id))
        old_household = h_result.scalar_one_or_none()
        if not old_household or old_household.type != "individual":
            raise InviteError(
                INVITE_IN_OTHER_GROUP,
                "Ya eres miembro de otro grupo. Debes salir de ese grupo antes de unirte a uno nuevo.",
            )
        current_membership.left_at = now

    # Atomic claim — only succeeds if the invite is still pending + not expired.
    claim = await db.execute(
        text(
            """
            UPDATE household_invites
            SET accepted_at = :now
            WHERE token = :token
              AND accepted_at IS NULL
              AND expires_at > :now
            RETURNING id, household_id, invited_by, invited_email, accepted_at, expires_at, created_at
            """
        ),
        {"now": now, "token": token},
    )
    claimed = claim.one_or_none()
    if not claimed:
        # Lost the race to a concurrent accept.
        raise InviteError(INVITE_ALREADY_USED, "Este enlace ya fue usado.")

    db.add(HouseholdMember(household_id=existing.household_id, user_id=user.id, role="member"))

    # Migrate the user's orphan data from their old individual household so
    # they don't lose access to past transactions on join.
    if old_household_id is not None:
        await db.execute(
            text(
                "UPDATE bank_accounts SET household_id = :new "
                "WHERE household_id = :old AND user_id = :uid"
            ),
            {
                "new": str(existing.household_id),
                "old": str(old_household_id),
                "uid": str(user.id),
            },
        )
        await db.execute(
            text(
                "UPDATE transactions SET household_id = :new "
                "WHERE household_id = :old AND user_id = :uid"
            ),
            {
                "new": str(existing.household_id),
                "old": str(old_household_id),
                "uid": str(user.id),
            },
        )

    # Preserve owner-customized split_ratio; rebalance only when the current
    # ratio is still the auto-equal default for the old member count.
    new_count = current_active + 1
    current_ratio = household_row.split_ratio or []
    if _is_auto_equal_ratio(current_ratio, current_active):
        new_ratio = _equal_ratio(new_count)
        await db.execute(
            text("UPDATE households SET split_ratio = :ratio, type = 'group' " "WHERE id = :id"),
            {"ratio": json.dumps(new_ratio), "id": str(existing.household_id)},
        )
    else:
        # Custom ratio — leave untouched so we don't wipe out a 70/30 split.
        # Caller must re-set via PATCH /households/{id}/split-ratio.
        await db.execute(
            text("UPDATE households SET type = 'group' WHERE id = :id"),
            {"id": str(existing.household_id)},
        )

    await db.commit()
    await db.refresh(existing)
    return existing


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


async def get_contribution_summary(
    db: AsyncSession, household_id: uuid.UUID, currency: str | None = None
) -> list[dict]:
    """Monthly household spending by member. No privacy restriction — both members see this."""
    currency_clause = "AND t.currency = :currency" if currency else ""
    params: dict = {"household_id": str(household_id)}
    if currency:
        params["currency"] = currency
    result = await db.execute(
        text(f"""
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
          {currency_clause}
        GROUP BY t.user_id, u.full_name, u.email
        """),
        params,
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


async def get_category_breakdown(
    db: AsyncSession, household_id, month: str | None = None, currency: str | None = None
):
    """Returns per-category spending breakdown for shared transactions."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = (
            "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"
        )
    currency_clause = ""
    if currency:
        currency_clause = "AND t.currency = :currency"
        params["currency"] = currency

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
          {currency_clause}
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


async def get_settlement(
    db: AsyncSession, household_id, month: str | None = None, currency: str | None = None
):
    """Returns settlement suggestion for the household."""
    params: dict = {"household_id": str(household_id)}
    if month:
        month_clause = "DATE_TRUNC('month', t.transaction_date::DATE) = :month_start"
        params["month_start"] = f"{month}-01"
    else:
        month_clause = (
            "DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)"
        )
    currency_clause = ""
    if currency:
        currency_clause = "AND t.currency = :currency"
        params["currency"] = currency

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
          {currency_clause}
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
