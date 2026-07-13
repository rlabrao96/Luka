import json
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from modules.households.models import Household, HouseholdMember, HouseholdInvite
from modules.transactions.totals import totals_exclusion_sql
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
            "SELECT COUNT(*) FROM household_members WHERE household_id = :hid AND left_at IS NULL"
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
            text("UPDATE households SET split_ratio = :ratio, type = 'group' WHERE id = :id"),
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
    # Invalidate the acceptor's cached household blob so /auth/me sees the
    # new membership immediately instead of after the 5-min TTL expires.
    from core.security import invalidate_user_cache

    await invalidate_user_cache(user.email)
    return existing


async def leave_household(
    db: AsyncSession, household_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """Let the caller leave a group household on their own.

    If the caller is the SOLE active owner and other active members remain,
    the oldest-joined remaining member is auto-promoted to owner first — so a
    group is never left ownerless and a sole owner isn't trapped (previously
    the only way out was deleting the account). Returns the caller's new
    individual-household id.
    """
    me = (
        await db.execute(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user_id,
                HouseholdMember.left_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if me is None:
        raise ValueError("No eres miembro activo de este grupo")

    other_active = (
        (
            await db.execute(
                select(HouseholdMember)
                .where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.left_at.is_(None),
                    HouseholdMember.user_id != user_id,
                )
                .order_by(HouseholdMember.joined_at.asc())
            )
        )
        .scalars()
        .all()
    )
    if not other_active:
        raise ValueError("Eres el único miembro del grupo. Elimina tu cuenta si deseas cerrarlo.")

    if me.role == "owner":
        remaining_owners = sum(1 for m in other_active if m.role == "owner")
        if remaining_owners == 0:
            # Promote the oldest remaining member so the group keeps an owner.
            other_active[0].role = "owner"
            await db.flush()

    return await remove_member(db, household_id, me.id)


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

    # Undo any charge attributions involving the leaving member (as recipient
    # or sender) — nothing should stay "owned" by a non-member.
    from modules.transactions.attribution import revert_attributions_for_member

    await revert_attributions_for_member(db, removed_user_id)

    # Create a new individual household for the removed user
    user_result = await db.execute(
        text("SELECT email, full_name FROM users WHERE id = :id"),
        {"id": str(removed_user_id)},
    )
    user_row = user_result.one_or_none()
    removed_user_email = user_row.email if user_row else None
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
    if removed_user_email:
        from core.security import invalidate_user_cache

        await invalidate_user_cache(removed_user_email)
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


def _month_range(month: str | None, currency: str | None):
    """Tz-aware [start, end) UTC instants for a YYYY-MM (or the current
    month in the currency's home timezone). See core.dates (M14)."""
    from core.dates import month_bounds_datetime, tz_for_currency

    if month:
        anchor = date.fromisoformat(f"{month}-01")
    else:
        anchor = datetime.now(tz_for_currency(currency)).date().replace(day=1)
    start, end, _ = month_bounds_datetime(anchor, currency)
    return start, end


async def get_contribution_summary(
    db: AsyncSession, household_id: uuid.UUID, currency: str | None = None
) -> list[dict]:
    """Monthly SHARED spending by member — the "contribution transparency" view.

    Privacy: only ``shared_paid`` is returned. A member's total or PERSONAL
    (non-shared) spending is private and must never reach another member —
    the frontend only ever displays the shared number, and the previous
    version leaked personal_paid/total_paid for every member in the response
    body (readable via devtools), contradicting the "no raw partner rows"
    guarantee in MEMORY.md.
    """
    currency_clause = "AND t.currency = :currency" if currency else ""
    params: dict = {"household_id": str(household_id)}
    if currency:
        params["currency"] = currency
    params["m_start"], params["m_end"] = _month_range(None, currency)
    # Shared expenses only, absolute amounts, shared totals-exclusion rule —
    # refunds/reimbursements/transfers must not distort the contribution total.
    result = await db.execute(
        text(f"""
        SELECT
            t.user_id,
            u.full_name,
            u.email,
            COALESCE(SUM(ABS(t.amount)) FILTER (WHERE ts.split_type = 'shared'), 0) AS shared_paid
        FROM transactions t
        JOIN transaction_splits ts ON ts.transaction_id = t.id
        JOIN users u ON u.id = t.user_id
        JOIN household_members hm ON hm.user_id = u.id AND hm.household_id = t.household_id
        WHERE t.household_id = :household_id
          AND t.transaction_type = 'expense'
          AND {totals_exclusion_sql("t")}
          AND t.transaction_date >= :m_start AND t.transaction_date < :m_end
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
    m_start, m_end = _month_range(month, currency)
    month_clause = "t.transaction_date >= :m_start AND t.transaction_date < :m_end"
    params["m_start"], params["m_end"] = m_start, m_end
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
          AND {totals_exclusion_sql("t")}
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
    """Pool-based settlement for N members. Returns minimal list of transfers.

    `members` MUST be ordered by household_members.joined_at ASC — the same
    canonical order budgets v2 `_caller_ratio_share` uses — because
    `split_ratio[i]` maps positionally onto members[i]. Falls back to an equal
    split when the ratio is missing, shorter than the member list, or sums to
    zero. Expected shares are quantized to one minor unit and the last member
    absorbs the rounding residual so balances always net to zero.
    """
    if len(members) <= 1:
        return []

    grand_total = sum(m["total"] for m in members)
    if grand_total == 0:
        return []

    n = len(members)
    if not split_ratio or len(split_ratio) < n or sum(split_ratio[:n]) <= 0:
        ratios = [Decimal(1) / Decimal(n)] * n
    else:
        ratio_sum = Decimal(sum(split_ratio[:n]))
        ratios = [Decimal(r) / ratio_sum for r in split_ratio[:n]]

    _ONE = Decimal("1")
    expected = [(grand_total * r).quantize(_ONE, rounding=ROUND_HALF_UP) for r in ratios]
    expected[-1] = grand_total - sum(expected[:-1])

    # Each member's balance (positive = overpaid/creditor, negative = underpaid/debtor)
    balances = []
    for i, member in enumerate(members):
        balance = member["total"] - expected[i]
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
    m_start, m_end = _month_range(month, currency)
    month_clause = "t.transaction_date >= :m_start AND t.transaction_date < :m_end"
    params["m_start"], params["m_end"] = m_start, m_end
    currency_clause = ""
    if currency:
        currency_clause = "AND t.currency = :currency"
        params["currency"] = currency

    # Members come from household_members (not from who happened to spend) so a
    # zero-spend partner still participates, and joined_at ASC keeps
    # split_ratio[i] mapped to the same person as budgets v2 _caller_ratio_share.
    sql = text(f"""
        SELECT u.id AS user_id, u.full_name,
               COALESCE(agg.total, 0) AS total
        FROM household_members hm
        JOIN users u ON u.id = hm.user_id
        LEFT JOIN (
            SELECT t.user_id, SUM(ABS(t.amount)) AS total
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            WHERE t.household_id = :household_id
              AND ts.split_type = 'shared'
              AND t.transaction_type = 'expense'
              AND {totals_exclusion_sql("t")}
              AND {month_clause}
              {currency_clause}
            GROUP BY t.user_id
        ) agg ON agg.user_id = hm.user_id
        WHERE hm.household_id = :household_id
          AND hm.left_at IS NULL
        ORDER BY hm.joined_at ASC
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


async def get_equity_report(
    db: AsyncSession, household_id: uuid.UUID, months: int = 6, currency: str = "CLP"
) -> dict:
    """Per-month fairness view: who fronted shared spending vs their ratio share.

    For each of the last `months` months (oldest→newest, current included):
    each ACTIVE member's shared-expense total, their expected share under the
    household ratio (joined_at ASC — same canonical ordering as settlement and
    budgets v2), and the net they fronted (paid − expected; positive = they
    put in more than their share). Uses the CURRENT ratio for all months —
    historical ratios aren't versioned.
    """
    months = max(1, min(months, 12))
    today = date.today()
    month_starts: list[date] = []
    y, m = today.year, today.month
    for _ in range(months):
        month_starts.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    month_starts.reverse()

    members_res = await db.execute(
        text(
            """
            SELECT hm.user_id, u.full_name
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            WHERE hm.household_id = :hid AND hm.left_at IS NULL
            ORDER BY hm.joined_at ASC
            """
        ),
        {"hid": str(household_id)},
    )
    members = [(r[0], r[1]) for r in members_res.all()]
    if not members:
        return {"months": [], "split_ratio": [], "currency": currency}

    totals_res = await db.execute(
        text(f"""
            SELECT t.user_id,
                   DATE_TRUNC('month', t.transaction_date::DATE)::DATE AS month_start,
                   COALESCE(SUM(ABS(t.amount)), 0) AS total
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            WHERE t.household_id = :hid
              AND ts.split_type = 'shared'
              AND t.transaction_type = 'expense'
              AND {totals_exclusion_sql("t")}
              AND t.currency = :ccy
              AND t.transaction_date >= CAST(:window_start AS DATE)
            GROUP BY t.user_id, DATE_TRUNC('month', t.transaction_date::DATE)
        """),
        {
            "hid": str(household_id),
            "ccy": currency,
            "window_start": month_starts[0],
        },
    )
    paid: dict[tuple, Decimal] = {}
    for user_id, month_start, total in totals_res.all():
        paid[(user_id, month_start)] = Decimal(str(total))

    ratio_row = await db.execute(
        text("SELECT split_ratio FROM households WHERE id = :id"),
        {"id": str(household_id)},
    )
    split_ratio = ratio_row.scalar_one_or_none() or []
    n = len(members)
    if not split_ratio or len(split_ratio) < n or sum(split_ratio[:n]) <= 0:
        ratios = [Decimal(1) / Decimal(n)] * n
    else:
        ratio_sum = Decimal(sum(split_ratio[:n]))
        ratios = [Decimal(r) / ratio_sum for r in split_ratio[:n]]

    _ONE = Decimal("1")
    out_months = []
    for ms in month_starts:
        month_total = sum((paid.get((uid, ms), Decimal("0")) for uid, _ in members), Decimal("0"))
        expected = [(month_total * r).quantize(_ONE, rounding=ROUND_HALF_UP) for r in ratios]
        if expected:
            expected[-1] = month_total - sum(expected[:-1])
        rows = []
        for i, (uid, name) in enumerate(members):
            p = paid.get((uid, ms), Decimal("0"))
            rows.append(
                {
                    "user_id": str(uid),
                    "full_name": name,
                    "paid": p,
                    "expected": expected[i] if expected else Decimal("0"),
                    "net": p - (expected[i] if expected else Decimal("0")),
                }
            )
        out_months.append({"month": ms.strftime("%Y-%m"), "total": month_total, "members": rows})

    return {
        "months": out_months,
        "split_ratio": split_ratio or [round(float(r * 100)) for r in ratios],
        "currency": currency,
    }


async def get_member_stats(
    db: AsyncSession, household_id: uuid.UUID, requester_id: uuid.UUID
) -> list[dict]:
    """Aggregate SHARED spending per active member — no individual rows.

    Privacy: scoped to shared-split expenses only. Returning each other
    member's TOTAL spend (personal included) would leak their private
    spending, same class of breach as get_contribution_summary once did.
    """
    result = await db.execute(
        text(f"""
            SELECT u.id AS user_id, u.full_name,
                   COALESCE(SUM(ABS(t.amount)), 0) AS total_spent
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            LEFT JOIN transactions t ON t.user_id = u.id AND t.household_id = :household_id
                 AND t.transaction_type = 'expense'
                 AND {totals_exclusion_sql("t")}
            LEFT JOIN transaction_splits ts
                 ON ts.transaction_id = t.id AND ts.split_type = 'shared'
            WHERE hm.household_id = :household_id
              AND hm.left_at IS NULL
              AND hm.user_id != :viewer_id
              AND (t.id IS NULL OR ts.id IS NOT NULL)
            GROUP BY u.id, u.full_name
        """),
        {"household_id": str(household_id), "viewer_id": str(requester_id)},
    )
    return [dict(r._mapping) for r in result.all()]
