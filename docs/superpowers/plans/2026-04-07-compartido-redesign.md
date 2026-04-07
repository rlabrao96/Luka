# Compartido Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the "Hogar" household page into "Compartido" — supporting up to 5 members, pool-based settlement with optional disable, currency toggle, in-page member management via shareable invite links, and pending invite ghost cards.

**Architecture:** Backend-first approach. Start with Alembic migration + model changes, then update service/settlement logic, then API endpoints, then frontend page rewrite. Each task is independently testable.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js + TanStack Query + shadcn/ui (frontend), Alembic (migrations), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-04-07-compartido-redesign-design.md`

---

## Task 1: Alembic Migration — Schema Changes

**Files:**
- Create: `backend/alembic/versions/032_compartido_redesign.py`
- Modify: `backend/modules/households/models.py`

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/032_compartido_redesign.py
"""Compartido redesign: settlement_enabled, left_at, nullable invited_email, couple->group migration

Revision ID: 032
Revises: 031
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add settlement_enabled to households
    op.add_column(
        "households",
        sa.Column("settlement_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # 2. Add left_at to household_members
    op.add_column(
        "household_members",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Make invited_email nullable on household_invites
    op.alter_column("household_invites", "invited_email", existing_type=sa.String(), nullable=True)

    # 4. Migrate couple -> group
    op.execute("UPDATE households SET type = 'group' WHERE type = 'couple'")

    # 5. Migrate partner split type -> compartido (if any remain)
    op.execute("UPDATE transaction_splits SET split_type = 'compartido' WHERE split_type = 'partner'")


def downgrade() -> None:
    op.execute("UPDATE transaction_splits SET split_type = 'partner' WHERE split_type = 'compartido'")
    op.execute("UPDATE households SET type = 'couple' WHERE type = 'group'")
    op.alter_column("household_invites", "invited_email", existing_type=sa.String(), nullable=False)
    op.drop_column("household_members", "left_at")
    op.drop_column("households", "settlement_enabled")
```

- [ ] **Step 2: Update models.py to match new schema**

In `backend/modules/households/models.py`:

```python
# Household class — update these lines:
# Line 15: change comment
type: Mapped[str] = mapped_column(String, nullable=False)  # 'individual' | 'group'
# Line 16: keep split_ratio as-is (JSONB, server_default="[50, 50]" is fine — dynamic arrays)
# Add after line 17:
settlement_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa.text("true"))

# HouseholdMember class — add after line 27:
left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

# HouseholdInvite class — line 36: change to nullable
invited_email: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 3: Run migration locally to verify**

Run: `cd backend && alembic upgrade head`
Expected: Migration applies cleanly

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/032_compartido_redesign.py backend/modules/households/models.py
git commit -m "feat(compartido): add migration for settlement_enabled, left_at, couple->group"
```

---

## Task 2: N-Member Settlement Algorithm

**Files:**
- Modify: `backend/modules/households/service.py:163-202`
- Modify: `backend/tests/test_household_settlement.py`

- [ ] **Step 1: Write tests for N-member settlement**

Add to `backend/tests/test_household_settlement.py`:

```python
def test_settlement_3_members_equal_split():
    """3 members, equal split. One paid everything, other two owe."""
    members = [
        {"user_id": "u1", "full_name": "Rafael", "total": Decimal("300000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "Carlos", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [34, 33, 33])
    # Rafael overpaid by ~200k, María and Carlos each owe ~100k
    assert len(result) == 2
    # Both transfers go TO Rafael
    assert all(t["to_user_id"] == "u1" for t in result)
    total_owed = sum(t["amount"] for t in result)
    assert total_owed == Decimal("198000")  # 300000 - 102000 (34% of 300k)


def test_settlement_4_members_custom_ratio():
    """4 members with custom ratio, multiple transfers needed."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("100000")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("50000")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("30000")},
        {"user_id": "u4", "full_name": "D", "total": Decimal("20000")},
    ]
    result = calculate_settlement(members, [25, 25, 25, 25])
    grand_total = Decimal("200000")
    expected_each = Decimal("50000")
    # A overpaid 50k, B is even, C underpaid 20k, D underpaid 30k
    assert len(result) == 2  # C->A and D->A
    total_to_a = sum(t["amount"] for t in result if t["to_user_id"] == "u1")
    assert total_to_a == Decimal("50000")


def test_settlement_single_member():
    """Single member — no transfers needed."""
    members = [
        {"user_id": "u1", "full_name": "Rafael", "total": Decimal("100000")},
    ]
    result = calculate_settlement(members, [100])
    assert result == []


def test_settlement_empty_members():
    """No members — no transfers."""
    result = calculate_settlement([], [])
    assert result == []


def test_settlement_all_zero():
    """All members paid zero — no transfers needed."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("0")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [34, 33, 33])
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_household_settlement.py -v`
Expected: New tests FAIL (calculate_settlement returns dict, not list)

- [ ] **Step 3: Rewrite calculate_settlement for N members**

Replace `calculate_settlement` in `backend/modules/households/service.py` (lines 163-202):

```python
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
        balances.append({
            "user_id": str(member["user_id"]),
            "full_name": member["full_name"],
            "balance": balance,
        })

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
            transfers.append({
                "from_user_id": debtor["user_id"],
                "from_user_name": debtor["full_name"],
                "to_user_id": creditor["user_id"],
                "to_user_name": creditor["full_name"],
                "amount": amount,
            })
        creditor["balance"] -= amount
        debtor["balance"] += amount
        if creditor["balance"] == 0:
            ci += 1
        if debtor["balance"] == 0:
            di += 1

    return transfers
```

- [ ] **Step 4: Update existing 2-member tests to match new return type**

The existing tests expect a dict return. Update them to expect a list:

```python
def test_settlement_50_50():
    """With 50/50 split, person who paid less owes their expected share minus what they paid."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("180500")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("294960")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert len(result) == 1
    assert result[0]["from_user_id"] == "u1"
    assert result[0]["to_user_id"] == "u2"
    assert result[0]["amount"] == Decimal("57230")


def test_settlement_60_40():
    """With 60/40, settlement accounts for unequal expected shares."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("100000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("100000")},
    ]
    result = calculate_settlement(members, [60, 40])
    assert len(result) == 1
    assert result[0]["from_user_id"] == "u1"
    assert result[0]["to_user_id"] == "u2"
    assert result[0]["amount"] == Decimal("20000")


def test_settlement_balanced():
    """When both paid their fair share, no transfers."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("50000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("50000")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert result == []
```

- [ ] **Step 5: Run all settlement tests**

Run: `cd backend && python -m pytest tests/test_household_settlement.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/modules/households/service.py backend/tests/test_household_settlement.py
git commit -m "feat(compartido): rewrite settlement algorithm for N members with greedy minimization"
```

---

## Task 3: Backend Schemas & Settlement Endpoint

**Files:**
- Modify: `backend/modules/households/schemas.py`
- Modify: `backend/modules/households/service.py:205-242` (get_settlement function)
- Modify: `backend/modules/households/router.py:114-155`

- [ ] **Step 1: Update schemas for N-member settlement**

Replace contents of `backend/modules/households/schemas.py`:

```python
import uuid
from decimal import Decimal
from pydantic import BaseModel, EmailStr


class CreateHouseholdRequest(BaseModel):
    name: str
    type: str  # 'individual' | 'group'


class InviteRequest(BaseModel):
    email: EmailStr | None = None  # nullable for link-only invites


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str

    model_config = {"from_attributes": True}


class MemberTotal(BaseModel):
    user_id: str
    full_name: str
    amount: Decimal
    pct: float


class CategoryBreakdownRow(BaseModel):
    category: str
    member_totals: list[MemberTotal]
    total: Decimal
    pct_of_overall: float


class HouseholdSummaryResponse(BaseModel):
    total: Decimal
    members: list[MemberTotal]
    by_category: list[CategoryBreakdownRow]


class SettlementTransfer(BaseModel):
    from_user_id: str
    from_user_name: str
    to_user_id: str
    to_user_name: str
    amount: Decimal


class SettlementResponse(BaseModel):
    settlement_enabled: bool
    transfers: list[SettlementTransfer]
    split_ratio: list[int]
    month: str


class SplitRatioRequest(BaseModel):
    ratio: list[int]


class SplitRatioResponse(BaseModel):
    split_ratio: list[int]


class SettlementEnabledRequest(BaseModel):
    enabled: bool


class MemberRoleRequest(BaseModel):
    role: str  # 'owner' | 'member'
```

- [ ] **Step 2: Update get_settlement service to return new format**

Replace `get_settlement` in `backend/modules/households/service.py` (lines 205-242).

**IMPORTANT:** All household queries (`get_settlement`, `get_contribution_summary`, `get_category_breakdown`) must filter out removed members by joining `household_members` and checking `hm.left_at IS NULL`:

```python
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
```

Also update `get_contribution_summary` (lines 73-93) to add the same join:

```python
async def get_contribution_summary(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Monthly household spending by member. Only active members."""
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
          AND hm.left_at IS NULL
          AND DATE_TRUNC('month', t.transaction_date::DATE) = DATE_TRUNC('month', NOW()::DATE)
        GROUP BY t.user_id, u.full_name, u.email
        """),
        {"household_id": str(household_id)},
    )
    return [dict(row._mapping) for row in result.all()]
```

And update `get_category_breakdown` (lines 133-160) similarly — add `JOIN household_members hm ON hm.user_id = u.id AND hm.household_id = t.household_id` and `AND hm.left_at IS NULL` to the WHERE clause.

- [ ] **Step 3: Update router — split ratio validation for N members**

In `backend/modules/households/router.py`, update the `update_split_ratio` endpoint (line 148):

```python
@router.patch("/{household_id}/split-ratio", response_model=SplitRatioResponse)
async def update_split_ratio(
    household_id: uuid.UUID,
    body: SplitRatioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)

    # Validate: 2-5 elements, all non-negative, sum to 100
    if (
        len(body.ratio) < 2
        or len(body.ratio) > 5
        or sum(body.ratio) != 100
        or any(r < 0 for r in body.ratio)
    ):
        raise HTTPException(400, "Ratio must be 2-5 non-negative integers summing to 100")

    # Validate length matches active member count
    active_count_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
        """),
        {"hid": str(household_id)},
    )
    active_count = active_count_result.scalar()
    if len(body.ratio) != active_count:
        raise HTTPException(400, f"Ratio length ({len(body.ratio)}) must match active member count ({active_count})")

    await db.execute(
        text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
        {"ratio": json.dumps(body.ratio), "id": str(household_id)},
    )
    await db.commit()
    return {"split_ratio": body.ratio}
```

- [ ] **Step 4: Update settlement endpoint import in router**

In `backend/modules/households/router.py`, update the import at line 12 to include new schemas:

```python
from modules.households.schemas import (
    CreateHouseholdRequest,
    HouseholdResponse,
    InviteRequest,
    SplitRatioRequest,
    SplitRatioResponse,
    SettlementResponse,
    SettlementEnabledRequest,
    MemberRoleRequest,
)
```

- [ ] **Step 5: Update split-ratio GET default**

In router.py line 136, change the fallback:

```python
ratio = result.scalar_one_or_none() or [50, 50]  # keep as-is, dynamic arrays are fine
```

No change needed — the existing code already returns a dynamic list.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_household_settlement.py tests/test_households.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/modules/households/schemas.py backend/modules/households/service.py backend/modules/households/router.py
git commit -m "feat(compartido): update schemas and endpoints for N-member settlement"
```

---

## Task 4: New Backend Endpoints — Settlement Toggle, Member Management, Create-and-Invite

**Files:**
- Modify: `backend/modules/households/router.py`
- Modify: `backend/modules/households/service.py`

- [ ] **Step 1: Add settlement toggle endpoint**

Add to `backend/modules/households/router.py`:

```python
@router.patch("/{household_id}/settlement-enabled")
async def update_settlement_enabled(
    household_id: uuid.UUID,
    body: SettlementEnabledRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    await db.execute(
        text("UPDATE households SET settlement_enabled = :enabled WHERE id = :id"),
        {"enabled": body.enabled, "id": str(household_id)},
    )
    await db.commit()
    return {"settlement_enabled": body.enabled}
```

- [ ] **Step 2: Add member role update endpoint**

Add to `backend/modules/households/router.py`:

```python
@router.patch("/{household_id}/members/{member_id}/role")
async def update_member_role(
    household_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only owners can change roles
    owner_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.role == "owner",
            HouseholdMember.left_at.is_(None),
        )
    )
    if not owner_result.scalar_one_or_none():
        raise HTTPException(403, "Only owners can change member roles")

    if body.role not in ("owner", "member"):
        raise HTTPException(400, "Role must be 'owner' or 'member'")

    # If demoting from owner, ensure at least one owner remains
    if body.role == "member":
        owner_count = await db.execute(
            text("""
                SELECT COUNT(*) FROM household_members
                WHERE household_id = :hid AND role = 'owner' AND left_at IS NULL
            """),
            {"hid": str(household_id)},
        )
        if owner_count.scalar() <= 1:
            raise HTTPException(400, "Debe haber al menos un administrador en el grupo")

    await db.execute(
        text("UPDATE household_members SET role = :role WHERE id = :id AND household_id = :hid"),
        {"role": body.role, "id": str(member_id), "hid": str(household_id)},
    )
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 3: Add member removal endpoint**

Add to `backend/modules/households/service.py`:

```python
async def remove_member(db: AsyncSession, household_id: uuid.UUID, member_id: uuid.UUID):
    """Soft-remove a member: set left_at, unlink bank accounts, create individual household."""
    # Get the member being removed
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise ValueError("Member not found or already removed")

    user_id = member.user_id

    # Soft delete
    member.left_at = datetime.now(timezone.utc)

    # Unlink bank accounts from this household
    await db.execute(
        text("""
            UPDATE bank_accounts SET is_active = false
            WHERE user_id = :uid AND household_id = :hid
        """),
        {"uid": str(user_id), "hid": str(household_id)},
    )

    # Create a new individual household for the removed member
    new_household = Household(name="Mi cuenta", type="individual")
    db.add(new_household)
    await db.flush()
    new_member = HouseholdMember(household_id=new_household.id, user_id=user_id, role="owner")
    db.add(new_member)

    # Auto-adjust split ratio to equal parts for remaining active members
    active_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
        """),
        {"hid": str(household_id)},
    )
    active_count = active_result.scalar()
    if active_count > 0:
        base = 100 // active_count
        remainder = 100 % active_count
        ratio = [base + (1 if i < remainder else 0) for i in range(active_count)]
        await db.execute(
            text("UPDATE households SET split_ratio = :ratio WHERE id = :id"),
            {"ratio": json.dumps(ratio), "id": str(household_id)},
        )

    await db.commit()
    return new_household.id
```

Add endpoint in router:

```python
@router.delete("/{household_id}/members/{member_id}")
async def remove_member(
    household_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only owners can remove members
    owner_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.role == "owner",
            HouseholdMember.left_at.is_(None),
        )
    )
    if not owner_result.scalar_one_or_none():
        raise HTTPException(403, "Only owners can remove members")

    # Cannot remove last owner
    target_result = await db.execute(
        select(HouseholdMember).where(HouseholdMember.id == member_id)
    )
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "Member not found")
    if target.role == "owner":
        owner_count = await db.execute(
            text("""
                SELECT COUNT(*) FROM household_members
                WHERE household_id = :hid AND role = 'owner' AND left_at IS NULL
            """),
            {"hid": str(household_id)},
        )
        if owner_count.scalar() <= 1:
            raise HTTPException(400, "No puedes eliminar al último administrador")

    try:
        new_household_id = await service.remove_member(db, household_id, member_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "new_household_id": str(new_household_id)}
```

- [ ] **Step 4: Add create-and-invite endpoint**

Add to `backend/modules/households/router.py`:

```python
@router.post("/create-and-invite")
async def create_and_invite(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atomically create household (if none) + generate invite link."""
    # Check if user already has a household
    existing = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    member = existing.scalar_one_or_none()

    if member:
        household_id = member.household_id
    else:
        # Create new group household
        household = await service.create_household(db, current_user, "Mi grupo", "group")
        household_id = household.id

    # Fetch the actual household object
    h_result = await db.execute(select(Household).where(Household.id == household_id))
    household_obj = h_result.scalar_one()

    # Generate invite
    invite = await service.create_invite(db, household_obj, current_user, None)
    return {
        "household_id": str(household_id),
        "token": invite.token,
        "expires_at": invite.expires_at,
    }
```

Note: `create_invite` needs to accept `None` for email. Update the `create_invite` function signature in service.py:

```python
async def create_invite(
    db: AsyncSession, household: Household, invited_by: User, invited_email: str | None
) -> HouseholdInvite:
```

- [ ] **Step 5: Update invite endpoint to not require email**

In router.py, update `invite_partner` (line 35-65):

```python
@router.post("/{household_id}/invite")
async def invite_member(
    household_id: uuid.UUID,
    body: InviteRequest = InviteRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Household).where(Household.id == household_id))
    household = result.scalar_one_or_none()
    if not household:
        raise HTTPException(404, "Household not found")

    # Check user is owner
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.role == "owner",
            HouseholdMember.left_at.is_(None),
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(403, "Only owners can invite members")

    # Check max 5 active members
    active_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
        """),
        {"hid": str(household_id)},
    )
    if active_result.scalar() >= 5:
        raise HTTPException(400, "Este grupo ya tiene el máximo de miembros (5)")

    invite = await service.create_invite(db, household, current_user, body.email)
    return {"token": invite.token, "expires_at": invite.expires_at}
```

- [ ] **Step 6: Update accept_invite to handle edge cases**

In `backend/modules/households/service.py`, update `accept_invite`:

```python
async def accept_invite(db: AsyncSession, token: str, user: User) -> HouseholdInvite:
    result = await db.execute(select(HouseholdInvite).where(HouseholdInvite.token == token))
    invite = result.scalar_one_or_none()
    if not invite or invite.expires_at < datetime.now(timezone.utc):
        raise ValueError("Este enlace ha expirado, pide uno nuevo")
    if invite.accepted_at:
        raise ValueError("Esta invitación ya fue aceptada")

    # Self-invite check
    if invite.invited_by == user.id:
        raise ValueError("No puedes unirte a tu propio grupo")

    # Already a member of THIS household
    existing = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == invite.household_id,
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Ya eres parte de este grupo")

    # Already in ANOTHER household
    other_membership = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    other = other_membership.scalar_one_or_none()
    if other and other.household_id != invite.household_id:
        # Check if the other household is just an individual (single member)
        count_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM household_members
                WHERE household_id = :hid AND left_at IS NULL
            """),
            {"hid": str(other.household_id)},
        )
        other_count = count_result.scalar()
        if other_count > 1:
            raise ValueError(
                "Ya perteneces a un grupo compartido. Debes salir del grupo actual para unirte a otro."
            )
        # Single-member individual household — just leave it
        other.left_at = datetime.now(timezone.utc)

    # Check max members
    active_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM household_members
            WHERE household_id = :hid AND left_at IS NULL
        """),
        {"hid": str(invite.household_id)},
    )
    active_count = active_result.scalar()
    if active_count >= 5:
        raise ValueError("Este grupo ya tiene el máximo de miembros")

    invite.accepted_at = datetime.now(timezone.utc)
    member = HouseholdMember(household_id=invite.household_id, user_id=user.id, role="member")
    db.add(member)

    # Auto-adjust split ratio to equal parts
    new_active = active_count + 1
    base = 100 // new_active
    remainder = 100 % new_active
    ratio = [base + (1 if i < remainder else 0) for i in range(new_active)]
    await db.execute(
        text("UPDATE households SET split_ratio = :ratio, type = 'group' WHERE id = :id"),
        {"ratio": json.dumps(ratio), "id": str(invite.household_id)},
    )

    await db.commit()
    await db.refresh(invite)
    return invite
```

- [ ] **Step 7: Add get_household_members service function**

Add to `backend/modules/households/service.py`:

```python
async def get_household_members(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Get all active members of a household with their roles."""
    result = await db.execute(
        text("""
            SELECT hm.id AS member_id, hm.user_id, hm.role, hm.joined_at,
                   u.full_name, u.email
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            WHERE hm.household_id = :hid AND hm.left_at IS NULL
            ORDER BY hm.joined_at
        """),
        {"hid": str(household_id)},
    )
    return [dict(r._mapping) for r in result.all()]


async def get_pending_invites(db: AsyncSession, household_id: uuid.UUID) -> list[dict]:
    """Get pending (non-accepted, non-expired) invites."""
    result = await db.execute(
        text("""
            SELECT id, token, invited_email, expires_at, created_at
            FROM household_invites
            WHERE household_id = :hid
              AND accepted_at IS NULL
              AND expires_at > NOW()
            ORDER BY created_at DESC
        """),
        {"hid": str(household_id)},
    )
    return [dict(r._mapping) for r in result.all()]
```

Add endpoints in router:

```python
@router.get("/{household_id}/members")
async def get_members(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    members = await service.get_household_members(db, household_id)
    invites = await service.get_pending_invites(db, household_id)
    return {"members": members, "pending_invites": invites}
```

- [ ] **Step 8: Add json import to service.py if not present**

At top of `backend/modules/households/service.py`, ensure `import json` is present.

- [ ] **Step 9: Run tests**

Run: `cd backend && python -m pytest tests/ -v -k household`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add backend/modules/households/
git commit -m "feat(compartido): add settlement toggle, member management, create-and-invite endpoints"
```

---

## Task 5: Update household_members auth to filter active members

**Files:**
- Modify: `backend/modules/households/auth.py`

- [ ] **Step 1: Update require_membership to check left_at**

```python
async def require_membership(household_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
    """Raise 403 if user is not an active member of the household."""
    result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this household")
```

- [ ] **Step 2: Verify budget personal_service.py (no code change)**

In `backend/modules/budgets/personal_service.py` line 92: `mode = "single" if household.type == "individual" else "waterfall"`. This already works correctly — `group` is not `individual`, so it falls into `waterfall` mode. Verification only, no code change required.

- [ ] **Step 3: Commit**

```bash
git add backend/modules/households/auth.py
git commit -m "feat(compartido): filter active members in auth check (respect left_at)"
```

---

## Task 6: Frontend — API Types, Hooks, and API Methods

**Files:**
- Modify: `frontend/app/lib/api.ts` (types + methods)
- Modify: `frontend/app/lib/hooks/useHousehold.ts`

- [ ] **Step 1: Update SettlementResponse type**

In `frontend/app/lib/api.ts`, replace the `SettlementResponse` interface (lines 94-102):

```typescript
export interface SettlementTransfer {
  from_user_id: string;
  from_user_name: string;
  to_user_id: string;
  to_user_name: string;
  amount: number;
}

export interface SettlementResponse {
  settlement_enabled: boolean;
  transfers: SettlementTransfer[];
  split_ratio: number[];
  month: string;
}
```

- [ ] **Step 2: Add new types for members and invites**

Add to `frontend/app/lib/api.ts` near the other household types:

```typescript
export interface HouseholdMember {
  member_id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: "owner" | "member";
  joined_at: string;
}

export interface PendingInvite {
  id: string;
  token: string;
  invited_email: string | null;
  expires_at: string;
  created_at: string;
}

export interface HouseholdMembersResponse {
  members: HouseholdMember[];
  pending_invites: PendingInvite[];
}
```

- [ ] **Step 3: Add new API methods**

Add to the `api` object in `frontend/app/lib/api.ts`:

```typescript
  getHouseholdMembers: (householdId: string) =>
    apiFetch<HouseholdMembersResponse>(`/households/${householdId}/members`),

  createAndInvite: () =>
    apiFetch<{ household_id: string; token: string; expires_at: string }>(
      "/households/create-and-invite",
      { method: "POST" }
    ),

  updateSettlementEnabled: (householdId: string, enabled: boolean) =>
    apiFetch<{ settlement_enabled: boolean }>(
      `/households/${householdId}/settlement-enabled`,
      { method: "PATCH", body: JSON.stringify({ enabled }) }
    ),

  updateMemberRole: (householdId: string, memberId: string, role: string) =>
    apiFetch<{ ok: boolean }>(
      `/households/${householdId}/members/${memberId}/role`,
      { method: "PATCH", body: JSON.stringify({ role }) }
    ),

  removeMember: (householdId: string, memberId: string) =>
    apiFetch<{ ok: boolean; new_household_id: string }>(
      `/households/${householdId}/members/${memberId}`,
      { method: "DELETE" }
    ),
```

Update existing methods:

```typescript
  // Change createHousehold type parameter
  createHousehold: (name: string, type: "individual" | "group") =>
    apiFetch<{ id: string; name: string; type: string }>("/households", {
      method: "POST",
      body: JSON.stringify({ name, type }),
    }),

  // Rename invitePartner to inviteMember, make email optional
  inviteMember: (householdId: string) =>
    apiFetch<{ token: string; expires_at: string }>(
      `/households/${householdId}/invite`,
      { method: "POST", body: JSON.stringify({}) }
    ),
```

- [ ] **Step 4: Add new hooks**

Add to `frontend/app/lib/hooks/useHousehold.ts`:

```typescript
export function useHouseholdMembers() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "members", householdId],
    queryFn: () => api.getHouseholdMembers(householdId!),
    enabled: !!householdId,
  });
}

export function useCreateAndInvite() {
  const queryClient = useQueryClient();
  const setHousehold = useLukaStore((s) => s.setHousehold);
  return useMutation({
    mutationFn: () => api.createAndInvite(),
    onSuccess: (data) => {
      setHousehold(data.household_id);
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useUpdateSettlementEnabled() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => api.updateSettlementEnabled(householdId!, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useRemoveMember() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) => api.removeMember(householdId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}

export function useUpdateMemberRole() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: string }) =>
      api.updateMemberRole(householdId!, memberId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["household"] });
    },
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/app/lib/api.ts frontend/app/lib/hooks/useHousehold.ts
git commit -m "feat(compartido): update frontend types, hooks, and API methods for N-member support"
```

---

## Task 7: Frontend — Compartido Page Rewrite

**Files:**
- Rewrite: `frontend/app/(dashboard)/household/page.tsx`

- [ ] **Step 1: Rewrite the household page**

Replace the entire contents of `frontend/app/(dashboard)/household/page.tsx`:

```tsx
"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, UserPlus } from "lucide-react";
import {
  useHouseholdSummary,
  useCategoryBreakdown,
  useSettlement,
  useSplitRatio,
  useHouseholdMembers,
  useCreateAndInvite,
} from "@/app/lib/hooks/useHousehold";
import { useLukaStore } from "@/app/lib/store";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import RatioSettingsModal from "./RatioSettingsModal";
import InviteModal from "./InviteModal";
import MemberCard from "./MemberCard";

function fmt(n: number, currency: string = "CLP") {
  if (currency === "USD") {
    return `US$${Math.round(n).toLocaleString("en-US")}`;
  }
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function getLast6Months(): { value: string; label: string }[] {
  const now = new Date();
  const months: { value: string; label: string }[] = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
    months.push({ value, label });
  }
  return months;
}

// Member colors (up to 5)
const MEMBER_COLORS = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6"];

export default function CompartidoPage() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const [selectedMonth, setSelectedMonth] = useState<string | undefined>(undefined);
  const [ratioModalOpen, setRatioModalOpen] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [currency, setCurrency] = useState("CLP");

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const { data: summary = [], isLoading: loadingSummary } = useHouseholdSummary();
  const { data: breakdown = [], isLoading: loadingBreakdown } = useCategoryBreakdown(selectedMonth);
  const { data: settlement } = useSettlement(selectedMonth);
  const { data: splitRatio } = useSplitRatio();
  const { data: membersData } = useHouseholdMembers();
  const createAndInvite = useCreateAndInvite();

  const monthOptions = getLast6Months();
  const now = new Date();
  const displayMonth = selectedMonth
    ? monthOptions.find((m) => m.value === selectedMonth)?.label ?? selectedMonth
    : `${MONTH_NAMES[now.getMonth()]} ${now.getFullYear()}`;

  // Sync currency from user preference
  const preferredCurrency = me?.preferred_currency;
  useEffect(() => {
    if (preferredCurrency) setCurrency(preferredCurrency);
  }, [preferredCurrency]);

  const ratio = splitRatio?.split_ratio ?? [];
  const members = membersData?.members ?? [];
  const pendingInvites = membersData?.pending_invites ?? [];
  const isOwner = members.some((m) => m.user_id === userId && m.role === "owner");
  const settlementEnabled = settlement?.settlement_enabled ?? true;

  // Compute member balances from settlement transfers
  const memberBalances = useMemo(() => {
    const balances: Record<string, number> = {};
    if (!settlement?.transfers) return balances;
    for (const t of settlement.transfers) {
      balances[t.from_user_id] = (balances[t.from_user_id] ?? 0) - t.amount;
      balances[t.to_user_id] = (balances[t.to_user_id] ?? 0) + t.amount;
    }
    return balances;
  }, [settlement]);

  // Filter summary by currency (if the API supports it, otherwise show all)
  const totalShared = summary.reduce((sum, r) => sum + r.shared_paid, 0);

  // Category breakdown totals — dynamic for N members
  const breakdownTotalByMember: Record<string, number> = {};
  let breakdownGrandTotal = 0;
  for (const row of breakdown) {
    breakdownGrandTotal += row.total;
    for (const mt of row.member_totals) {
      breakdownTotalByMember[mt.user_id] = (breakdownTotalByMember[mt.user_id] ?? 0) + mt.amount;
    }
  }

  // Get ordered list of member user_ids from summary for consistent column ordering
  const memberOrder = summary.map((s) => s.user_id);
  const memberNameMap: Record<string, string> = {};
  for (const s of summary) {
    memberNameMap[s.user_id] = s.full_name;
  }

  // Loading state
  if (loadingSummary) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <p className="text-sm text-luka-muted">Cargando...</p>
      </div>
    );
  }

  // Empty state — no household or no members
  if (!householdId || summary.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <Card className="bg-white">
          <CardContent className="py-16 text-center space-y-4">
            <p className="text-sm text-luka-muted">No tienes un grupo compartido</p>
            <Button
              onClick={() => setInviteModalOpen(true)}
              className="bg-luka-primary hover:bg-blue-700"
            >
              <UserPlus size={16} className="mr-2" />
              Agregar mi primer miembro
            </Button>
          </CardContent>
        </Card>
        <InviteModal
          open={inviteModalOpen}
          onOpenChange={setInviteModalOpen}
          householdId={householdId}
          onCreateAndInvite={() => createAndInvite.mutate()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedMonth ?? ""}
            onChange={(e) => setSelectedMonth(e.target.value || undefined)}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Mes actual</option>
            {monthOptions.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <CurrencyToggle value={currency} onChange={setCurrency} />
          {!settlementEnabled && (
            <button
              onClick={() => setRatioModalOpen(true)}
              className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
              title="Configurar ratios"
            >
              <Settings size={16} />
            </button>
          )}
          {isOwner && members.length < 5 && (
            <Button
              onClick={() => setInviteModalOpen(true)}
              size="sm"
              className="bg-luka-primary hover:bg-blue-700"
            >
              <UserPlus size={14} className="mr-1.5" />
              Agregar miembro
            </Button>
          )}
        </div>
      </div>

      {/* Member cards row */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {summary.map((member, i) => (
          <MemberCard
            key={member.user_id}
            name={member.full_name}
            amount={member.shared_paid}
            percentage={totalShared > 0 ? Math.round((member.shared_paid / totalShared) * 100) : 0}
            color={MEMBER_COLORS[i % MEMBER_COLORS.length]}
            balance={memberBalances[member.user_id]}
            settlementEnabled={settlementEnabled}
            currency={currency}
            isOwner={isOwner}
            memberId={members.find((m) => m.user_id === member.user_id)?.member_id}
            memberRole={members.find((m) => m.user_id === member.user_id)?.role}
            isSelf={member.user_id === userId}
          />
        ))}
        {/* Pending invite ghost cards */}
        {pendingInvites.map((invite) => (
          <div
            key={invite.id}
            className="flex-shrink-0 w-48 rounded-xl border-2 border-dashed border-slate-300 p-4 text-center opacity-50"
          >
            <div className="w-9 h-9 rounded-full bg-slate-200 text-slate-400 flex items-center justify-center mx-auto mb-2 text-sm font-bold">
              ?
            </div>
            <p className="text-xs font-medium text-slate-400 truncate">
              {invite.invited_email ?? "Invitación pendiente"}
            </p>
            <p className="text-xs text-slate-400 mt-1">⏳ Pendiente</p>
          </div>
        ))}
      </div>

      {/* Total summary bar */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm px-5 py-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-luka-primary">
            Total compartido — {displayMonth}
          </p>
          <p className="text-2xl font-bold text-luka-dark">{fmt(totalShared, currency)}</p>
        </div>
      </div>

      {/* Settlement transfers (only when enabled) */}
      {settlementEnabled && settlement && settlement.transfers.length > 0 && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-blue-900">Transferencias sugeridas</h3>
            <button
              onClick={() => setRatioModalOpen(true)}
              className="text-xs text-luka-primary font-medium border border-blue-300 rounded-lg px-3 py-1 hover:bg-blue-100 transition-colors"
            >
              ⚙ Ratios ({ratio.join("/")})
            </button>
          </div>
          {settlement.transfers.map((t, i) => (
            <div key={i} className="bg-white rounded-lg px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-xs font-bold">
                  {t.from_user_name.charAt(0)}
                </span>
                <span>{t.from_user_name}</span>
                <span className="text-slate-400">→</span>
                <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-xs font-bold">
                  {t.to_user_name.charAt(0)}
                </span>
                <span>{t.to_user_name}</span>
              </div>
              <span className="font-bold text-luka-dark">{fmt(t.amount, currency)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Settlement enabled but balanced */}
      {settlementEnabled && settlement && settlement.transfers.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
          <p className="text-sm font-medium text-emerald-800">Están equilibrados ✓</p>
          <button
            onClick={() => setRatioModalOpen(true)}
            className="text-xs text-emerald-700 font-medium border border-emerald-300 rounded-lg px-3 py-1 hover:bg-emerald-100 transition-colors"
          >
            ⚙ Ratios ({ratio.join("/")})
          </button>
        </div>
      )}

      {/* Category breakdown table */}
      <Card className="bg-white">
        <CardContent className="py-5">
          <h3 className="text-sm font-semibold text-luka-dark mb-4">Desglose por categoría</h3>

          {loadingBreakdown ? (
            <p className="text-sm text-luka-muted">Cargando...</p>
          ) : breakdown.length === 0 ? (
            <p className="text-sm text-luka-muted">Sin gastos compartidos este mes.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left py-2 pr-4 font-medium text-slate-500">Categoría</th>
                    {memberOrder.map((uid, i) => (
                      <th key={uid} className="text-right py-2 px-4 font-medium text-slate-500">
                        {memberNameMap[uid]?.split(" ")[0] ?? "Miembro"}
                      </th>
                    ))}
                    <th className="text-right py-2 pl-4 font-medium text-slate-500">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row) => {
                    const mtMap: Record<string, { amount: number; pct: number }> = {};
                    for (const mt of row.member_totals) {
                      mtMap[mt.user_id] = { amount: mt.amount, pct: mt.pct };
                    }
                    return (
                      <tr key={row.category} className="border-b border-slate-50">
                        <td className="py-3 pr-4">
                          <div className="font-medium text-slate-700">{row.category}</div>
                          <div className="flex h-1 rounded-full overflow-hidden mt-1 max-w-[120px]">
                            {memberOrder.map((uid, i) => {
                              const pct = mtMap[uid]?.pct ?? 0;
                              return (
                                <div
                                  key={uid}
                                  style={{
                                    width: `${pct}%`,
                                    backgroundColor: MEMBER_COLORS[i % MEMBER_COLORS.length],
                                  }}
                                />
                              );
                            })}
                          </div>
                        </td>
                        {memberOrder.map((uid) => {
                          const mt = mtMap[uid];
                          return (
                            <td key={uid} className="text-right py-3 px-4">
                              <div className="font-medium text-slate-700">
                                {fmt(mt?.amount ?? 0, currency)}
                              </div>
                              <div className="text-xs text-slate-400">{mt?.pct ?? 0}%</div>
                            </td>
                          );
                        })}
                        <td className="text-right py-3 pl-4">
                          <div className="font-bold text-slate-800">{fmt(row.total, currency)}</div>
                          <div className="text-xs text-slate-400">{row.pct_of_overall}%</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-200">
                    <td className="py-3 pr-4 font-bold text-slate-800">Total</td>
                    {memberOrder.map((uid, i) => (
                      <td
                        key={uid}
                        className="text-right py-3 px-4 font-bold"
                        style={{ color: MEMBER_COLORS[i % MEMBER_COLORS.length] }}
                      >
                        {fmt(breakdownTotalByMember[uid] ?? 0, currency)}
                      </td>
                    ))}
                    <td className="text-right py-3 pl-4 font-bold text-slate-800">
                      {fmt(breakdownGrandTotal, currency)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <RatioSettingsModal
        open={ratioModalOpen}
        onOpenChange={setRatioModalOpen}
        currentRatio={ratio}
        members={members}
        settlementEnabled={settlementEnabled}
      />
      <InviteModal
        open={inviteModalOpen}
        onOpenChange={setInviteModalOpen}
        householdId={householdId}
        onCreateAndInvite={() => createAndInvite.mutate()}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/household/page.tsx
git commit -m "feat(compartido): rewrite household page for N-member support with member cards"
```

---

## Task 8: Frontend — MemberCard Component

**Files:**
- Create: `frontend/app/(dashboard)/household/MemberCard.tsx`

- [ ] **Step 1: Create MemberCard component**

```tsx
// frontend/app/(dashboard)/household/MemberCard.tsx
"use client";

import { useState } from "react";
import { useRemoveMember, useUpdateMemberRole } from "@/app/lib/hooks/useHousehold";

interface Props {
  name: string;
  amount: number;
  percentage: number;
  color: string;
  balance?: number;
  settlementEnabled: boolean;
  currency: string;
  isOwner: boolean;
  memberId?: string;
  memberRole?: string;
  isSelf: boolean;
}

function fmt(n: number, currency: string = "CLP") {
  if (currency === "USD") {
    return `US$${Math.round(Math.abs(n)).toLocaleString("en-US")}`;
  }
  return `$${Math.round(Math.abs(n)).toLocaleString("es-CL")}`;
}

export default function MemberCard({
  name,
  amount,
  percentage,
  color,
  balance,
  settlementEnabled,
  currency,
  isOwner,
  memberId,
  memberRole,
  isSelf,
}: Props) {
  const [showMenu, setShowMenu] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const removeMutation = useRemoveMember();
  const roleMutation = useUpdateMemberRole();

  const initials = name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div
      className="relative flex-shrink-0 w-48 bg-white rounded-xl border border-slate-100 shadow-sm p-4 text-center cursor-pointer"
      onClick={() => isOwner && !isSelf && setShowMenu(!showMenu)}
    >
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold text-white"
        style={{ backgroundColor: color }}
      >
        {initials}
      </div>
      <p className="text-sm font-semibold text-slate-700 truncate">{name}</p>
      <p className="text-xl font-bold text-luka-dark mt-1">{fmt(amount, currency)}</p>
      <p className="text-xs text-slate-400">{percentage}% del total</p>

      {/* Settlement badge */}
      {settlementEnabled && balance !== undefined && balance !== 0 && (
        <div
          className={`mt-2 inline-block px-2 py-0.5 rounded text-xs font-semibold ${
            balance > 0
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-600"
          }`}
        >
          {balance > 0 ? `+${fmt(balance, currency)} a favor` : `-${fmt(balance, currency)} debe`}
        </div>
      )}

      {/* Owner menu */}
      {showMenu && isOwner && !isSelf && memberId && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 text-left">
          <button
            onClick={(e) => {
              e.stopPropagation();
              roleMutation.mutate({
                memberId,
                role: memberRole === "owner" ? "member" : "owner",
              });
              setShowMenu(false);
            }}
            className="w-full px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 text-left"
          >
            {memberRole === "owner" ? "Quitar administrador" : "Hacer administrador"}
          </button>
          {!confirmRemove ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setConfirmRemove(true);
              }}
              className="w-full px-3 py-2 text-xs text-red-600 hover:bg-red-50 text-left"
            >
              Eliminar miembro
            </button>
          ) : (
            <div className="px-3 py-2 space-y-1">
              <p className="text-xs text-red-600">¿Confirmar eliminación?</p>
              <div className="flex gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeMutation.mutate(memberId);
                    setShowMenu(false);
                    setConfirmRemove(false);
                  }}
                  className="flex-1 px-2 py-1 text-xs bg-red-600 text-white rounded"
                >
                  Sí
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmRemove(false);
                  }}
                  className="flex-1 px-2 py-1 text-xs bg-slate-100 text-slate-600 rounded"
                >
                  No
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/household/MemberCard.tsx
git commit -m "feat(compartido): add MemberCard component with owner menu"
```

---

## Task 9: Frontend — RatioSettingsModal (replaces SplitRatioModal)

**Files:**
- Create: `frontend/app/(dashboard)/household/RatioSettingsModal.tsx`
- Delete: `frontend/app/(dashboard)/household/SplitRatioModal.tsx`

- [ ] **Step 1: Create RatioSettingsModal**

```tsx
// frontend/app/(dashboard)/household/RatioSettingsModal.tsx
"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  useUpdateSplitRatio,
  useUpdateSettlementEnabled,
} from "@/app/lib/hooks/useHousehold";
import type { HouseholdMember } from "@/app/lib/api";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentRatio: number[];
  members: HouseholdMember[];
  settlementEnabled: boolean;
}

export default function RatioSettingsModal({
  open,
  onOpenChange,
  currentRatio,
  members,
  settlementEnabled,
}: Props) {
  const [ratios, setRatios] = useState<number[]>(currentRatio);
  const [settlement, setSettlement] = useState(settlementEnabled);
  const ratioMutation = useUpdateSplitRatio();
  const settlementMutation = useUpdateSettlementEnabled();

  useEffect(() => {
    setRatios(currentRatio);
    setSettlement(settlementEnabled);
  }, [currentRatio, settlementEnabled]);

  const total = ratios.reduce((s, r) => s + r, 0);
  const valid = total === 100 && ratios.every((r) => r >= 0);

  function handleEqualSplit() {
    const n = members.length;
    const base = Math.floor(100 / n);
    const remainder = 100 % n;
    setRatios(members.map((_, i) => base + (i < remainder ? 1 : 0)));
  }

  function handleSave() {
    if (!valid) return;
    const promises: Promise<unknown>[] = [];
    if (JSON.stringify(ratios) !== JSON.stringify(currentRatio)) {
      promises.push(ratioMutation.mutateAsync(ratios));
    }
    if (settlement !== settlementEnabled) {
      promises.push(settlementMutation.mutateAsync(settlement));
    }
    Promise.all(promises).then(() => onOpenChange(false));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Configurar ratios</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {/* Per-member ratio inputs */}
          <div className="space-y-3">
            {members.map((member, i) => (
              <div key={member.user_id} className="flex items-center gap-3">
                <label className="text-sm text-slate-600 flex-1 truncate">
                  {member.full_name.split(" ")[0]}
                </label>
                <div className="flex items-center gap-1">
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={ratios[i] ?? 0}
                    onChange={(e) => {
                      const next = [...ratios];
                      next[i] = Number(e.target.value);
                      setRatios(next);
                    }}
                    className="w-20 text-center text-lg font-bold"
                  />
                  <span className="text-sm text-slate-400">%</span>
                </div>
              </div>
            ))}
          </div>

          {/* Sum indicator */}
          <div className={`text-xs text-center ${valid ? "text-emerald-600" : "text-red-500"}`}>
            Total: {total}% {!valid && "(debe sumar 100%)"}
          </div>

          {/* Equal split button */}
          <Button variant="outline" onClick={handleEqualSplit} className="w-full" size="sm">
            Repartir equitativamente
          </Button>

          {/* Settlement toggle */}
          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <label className="text-sm text-slate-600">Activar liquidación</label>
            <Switch checked={settlement} onCheckedChange={setSettlement} />
          </div>

          <Button
            onClick={handleSave}
            disabled={!valid || ratioMutation.isPending || settlementMutation.isPending}
            className="w-full"
          >
            {ratioMutation.isPending || settlementMutation.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Delete old SplitRatioModal**

```bash
rm frontend/app/\(dashboard\)/household/SplitRatioModal.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/household/RatioSettingsModal.tsx
git rm frontend/app/\(dashboard\)/household/SplitRatioModal.tsx
git commit -m "feat(compartido): replace SplitRatioModal with N-member RatioSettingsModal"
```

---

## Task 10: Frontend — InviteModal

**Files:**
- Create: `frontend/app/(dashboard)/household/InviteModal.tsx`

- [ ] **Step 1: Create InviteModal**

```tsx
// frontend/app/(dashboard)/household/InviteModal.tsx
"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { Link2, Check, Copy } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  householdId: string | null;
  onCreateAndInvite: () => void;
}

export default function InviteModal({ open, onOpenChange, householdId, onCreateAndInvite }: Props) {
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: async () => {
      if (!householdId) {
        // Create household and invite atomically
        const data = await api.createAndInvite();
        return data;
      }
      const data = await api.inviteMember(householdId);
      return data;
    },
    onSuccess: (data) => {
      setInviteLink(`${window.location.origin}/invite/${data.token}`);
    },
  });

  async function handleCopy() {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleClose(open: boolean) {
    if (!open) {
      setInviteLink(null);
      setCopied(false);
    }
    onOpenChange(open);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Invitar miembro</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {!inviteLink ? (
            <>
              <p className="text-sm text-slate-500">
                Genera un enlace de invitación para compartir con quien quieras agregar al grupo.
              </p>
              <Button
                onClick={() => inviteMutation.mutate()}
                disabled={inviteMutation.isPending}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                <Link2 size={14} className="mr-2" />
                {inviteMutation.isPending ? "Generando..." : "Generar enlace"}
              </Button>
              {inviteMutation.isError && (
                <p className="text-xs text-red-500">Error al generar invitación. Intenta de nuevo.</p>
              )}
            </>
          ) : (
            <>
              <p className="text-sm text-emerald-600 font-medium">
                Enlace creado. Compártelo con el nuevo miembro:
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inviteLink}
                  readOnly
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 truncate"
                />
                <Button onClick={handleCopy} size="sm" variant="outline">
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                </Button>
              </div>
              <p className="text-xs text-slate-400">
                El enlace expira en 7 días.
              </p>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(dashboard\)/household/InviteModal.tsx
git commit -m "feat(compartido): add InviteModal with shareable link generation"
```

---

## Task 11: Frontend — Navigation & Settings Renaming

**Files:**
- Modify: `frontend/app/(dashboard)/components/Sidebar.tsx`
- Modify: `frontend/app/(dashboard)/components/BottomNav.tsx`
- Modify: `frontend/app/(dashboard)/settings/components/HogarSection.tsx`

- [ ] **Step 1: Update Sidebar label**

In `frontend/app/(dashboard)/components/Sidebar.tsx`, change line with "Hogar":

```typescript
{ href: "/household", label: "Compartido", icon: Users }
```

- [ ] **Step 2: Update BottomNav label**

In `frontend/app/(dashboard)/components/BottomNav.tsx`, change line with "Hogar":

```typescript
{ href: "/household", label: "Compartido", icon: Users }
```

- [ ] **Step 3: Rename HogarSection to CompartidoSection**

Rename the component and update all "pareja" language to "miembros". Update the settings section to show all members (not just "partner"):

In `frontend/app/(dashboard)/settings/components/HogarSection.tsx`:
- Rename export to `CompartidoSection`
- Change heading from "Hogar" to "Compartido"
- Change type display from "Pareja" to "Grupo"
- Replace "Pareja" label with a members list
- Remove the invite form (invites now happen from the Compartido page)

Update the import in the parent settings page accordingly.

- [ ] **Step 4: Find and update the parent settings page import**

Search for `HogarSection` import in settings page and update to `CompartidoSection`.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/components/Sidebar.tsx frontend/app/\(dashboard\)/components/BottomNav.tsx frontend/app/\(dashboard\)/settings/
git commit -m "feat(compartido): rename Hogar to Compartido in navigation and settings"
```

---

## Task 12: Rename partner-stats to member-stats

**Files:**
- Modify: `backend/modules/households/service.py:245-254`
- Modify: `backend/modules/households/router.py:92-99`
- Modify: `frontend/app/lib/hooks/useHousehold.ts` (usePartnerStats)
- Modify: `frontend/app/lib/api.ts` (getPartnerStats, PartnerStats type)

The spec requires renaming `get_partner_stats` RPC to `get_member_stats` and updating it for N members.

- [ ] **Step 1: Update backend service — rename and adapt**

In `backend/modules/households/service.py`, rename `get_partner_stats` to `get_member_stats`:

```python
async def get_member_stats(
    db: AsyncSession, household_id: uuid.UUID, requester_id: uuid.UUID
) -> list[dict]:
    """Aggregate stats for all active members — no individual transaction rows."""
    result = await db.execute(
        text("""
            SELECT u.id AS user_id, u.full_name,
                   COALESCE(SUM(ABS(t.amount)), 0) AS total_spent,
                   json_agg(json_build_object(
                       'category', COALESCE(t.category, 'Sin categoría'),
                       'amount', ABS(t.amount)
                   )) AS by_category
            FROM household_members hm
            JOIN users u ON u.id = hm.user_id
            LEFT JOIN transactions t ON t.user_id = u.id AND t.household_id = :household_id
                AND t.transaction_type = 'expense'
            WHERE hm.household_id = :household_id
              AND hm.left_at IS NULL
              AND hm.user_id != :viewer_id
            GROUP BY u.id, u.full_name
        """),
        {"household_id": str(household_id), "viewer_id": str(requester_id)},
    )
    return [dict(r._mapping) for r in result.all()]
```

- [ ] **Step 2: Update router endpoint**

In `backend/modules/households/router.py`, rename the endpoint:

```python
@router.get("/{household_id}/member-stats")
async def member_stats(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_member_stats(db, household_id, current_user.id)
```

- [ ] **Step 3: Update frontend API and hooks**

In `frontend/app/lib/api.ts`, rename `getPartnerStats` to `getMemberStats` and update URL to `/member-stats`.
In `frontend/app/lib/hooks/useHousehold.ts`, rename `usePartnerStats` to `useMemberStats`.

- [ ] **Step 4: Search for remaining partner-stats references**

Search codebase for `partner-stats`, `getPartnerStats`, `usePartnerStats` and update all references.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/households/ frontend/app/lib/
git commit -m "feat(compartido): rename partner-stats to member-stats for N-member support"
```

---

## Task 13: Frontend — Onboarding Changes

**Files:**
- Modify: `frontend/app/(auth)/onboarding/setup-household/page.tsx`

- [ ] **Step 1: Update onboarding to new flow**

Replace contents of `frontend/app/(auth)/onboarding/setup-household/page.tsx`:

```tsx
"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const setOnboardingDraft = useLukaStore((s) => s.setOnboardingDraft);
  const draft = useLukaStore((s) => s.onboardingDraft);

  // Check if user came from an invite link — skip this question
  const inviteToken = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("invite_token") ||
      localStorage.getItem("pending_invite_token")
    : null;

  if (inviteToken) {
    // Skip — they came from an invite, intent is clear
    setOnboardingDraft({ type: "individual", partnerEmail: "" });
    router.push("/onboarding/verify-whatsapp");
    return null;
  }

  const [wantsShared, setWantsShared] = useState<boolean | null>(
    draft?.type === "individual" ? false : draft?.type ? true : null
  );

  const nextStep = () => {
    setOnboardingDraft({
      type: wantsShared ? "group" : "individual",
      partnerEmail: "",
    });
    router.push("/onboarding/verify-whatsapp");
  };

  return (
    <Card className="w-full shadow-sm">
      <CardHeader>
        <CardTitle className="text-luka-dark">¿Vas a compartir gastos?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button
          variant={wantsShared === true ? "default" : "outline"}
          className="w-full rounded-xl"
          onClick={() => setWantsShared(true)}
        >
          Sí — quiero dividir gastos con otros
        </Button>
        <Button
          variant={wantsShared === false ? "default" : "outline"}
          className="w-full rounded-xl"
          onClick={() => setWantsShared(false)}
        >
          No — solo quiero controlar mis gastos
        </Button>
        {wantsShared !== null && (
          <Button
            className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl"
            onClick={nextStep}
          >
            Continuar →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(auth\)/onboarding/setup-household/page.tsx
git commit -m "feat(compartido): update onboarding to compartido question, skip for invite links"
```

---

## Task 14: Frontend — Invite Page Redesign

**Files:**
- Modify: `frontend/app/(auth)/invite/[token]/page.tsx`

The spec requires a pre-auth landing page with "Ya tengo cuenta" / "Crear cuenta" options instead of auto-accepting immediately. The current page tries to accept immediately and redirects to login on 401.

- [ ] **Step 1: Rewrite invite page with two-button landing**

The page should:
1. First show a landing page with the Luka logo and two buttons: "Ya tengo cuenta" and "Crear cuenta"
2. "Ya tengo cuenta" → saves token to localStorage (`pending_invite_token`) → redirects to `/login?redirect=/invite/${token}`
3. "Crear cuenta" → saves token to localStorage → redirects to `/login?redirect=/invite/${token}` (same OAuth flow, new user auto-provisions)
4. If user is already logged in → auto-accept immediately (current behavior), handle edge cases:
   - "Ya eres parte de este grupo" → show message
   - "Ya perteneces a un grupo compartido" → show message with option to leave
   - "Este grupo ya tiene el máximo de miembros" → show message
   - "Este enlace ha expirado" → show message
5. On success → `localStorage.removeItem("pending_invite_token")` → redirect to `/household`

Update all text: "hogar" → "grupo", "pareja" → "miembro"

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(auth\)/invite/\[token\]/page.tsx
git commit -m "feat(compartido): redesign invite page with pre-auth landing and edge cases"
```

---

## Task 15: Run Full Test Suite & Fix Issues

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Fix any issues found**

Address any test failures or type errors from the changes.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "fix(compartido): resolve test failures and type errors from redesign"
```

---

## Task 16: Remove old invitePartner references

**Files:**
- Modify: `frontend/app/lib/api.ts` — remove `invitePartner` method (replaced by `inviteMember`)
- Search for any remaining `invitePartner` calls and update

- [ ] **Step 1: Search and replace**

Search for `invitePartner` across the codebase and replace with `inviteMember`.

- [ ] **Step 2: Search for "pareja" in frontend**

Search for remaining "pareja" strings in frontend code and update to appropriate "miembro" or "grupo" language.

- [ ] **Step 3: Search for "couple" in backend**

Search for remaining "couple" references in backend code and update.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(compartido): remove all couple/pareja references, use group/miembro terminology"
```
