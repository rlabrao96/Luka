import uuid as _uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Register models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.households.service import (
    build_category_breakdown,
    calculate_settlement,
    get_settlement,
)
from modules.transactions.models import Transaction, TransactionSplit


def test_build_category_breakdown_groups_by_category():
    """Given raw rows from SQL, builds category breakdown with member totals and percentages."""
    rows = [
        {
            "user_id": "u1",
            "full_name": "Rodrigo",
            "category": "Supermercado",
            "amount": Decimal("52300"),
        },
        {
            "user_id": "u2",
            "full_name": "María",
            "category": "Supermercado",
            "amount": Decimal("78400"),
        },
        {
            "user_id": "u1",
            "full_name": "Rodrigo",
            "category": "Restaurantes",
            "amount": Decimal("45200"),
        },
        {
            "user_id": "u2",
            "full_name": "María",
            "category": "Restaurantes",
            "amount": Decimal("32100"),
        },
    ]
    result = build_category_breakdown(rows)
    assert len(result) == 2
    supermercado = next(r for r in result if r["category"] == "Supermercado")
    assert supermercado["total"] == Decimal("130700")
    assert len(supermercado["member_totals"]) == 2
    rodrigo = next(m for m in supermercado["member_totals"] if m["user_id"] == "u1")
    assert rodrigo["amount"] == Decimal("52300")
    assert round(rodrigo["pct"], 1) == 40.0


def test_build_category_breakdown_empty():
    """Returns empty list when no rows."""
    assert build_category_breakdown([]) == []


def test_settlement_50_50():
    """With 50/50 split, person who paid less owes the difference."""
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


def test_settlement_3_members_equal_split():
    """3 members, equal split. One paid everything, other two owe."""
    members = [
        {"user_id": "u1", "full_name": "Rafael", "total": Decimal("300000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "Carlos", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [34, 33, 33])
    assert len(result) == 2
    assert all(t["to_user_id"] == "u1" for t in result)
    total_owed = sum(t["amount"] for t in result)
    assert total_owed == Decimal("198000")


def test_settlement_4_members_custom_ratio():
    """4 members with equal ratio, multiple transfers needed."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("100000")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("50000")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("30000")},
        {"user_id": "u4", "full_name": "D", "total": Decimal("20000")},
    ]
    result = calculate_settlement(members, [25, 25, 25, 25])
    # A overpaid 50k, B is even, C underpaid 20k, D underpaid 30k
    assert len(result) == 2
    total_to_a = sum(t["amount"] for t in result if t["to_user_id"] == "u1")
    assert total_to_a == Decimal("50000")


def test_settlement_single_member():
    """Single member — no transfers needed."""
    members = [{"user_id": "u1", "full_name": "Rafael", "total": Decimal("100000")}]
    result = calculate_settlement(members, [100])
    assert result == []


def test_settlement_empty_members():
    """No members — no transfers."""
    assert calculate_settlement([], []) == []


def test_settlement_all_zero():
    """All members paid zero — no transfers needed."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("0")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [34, 33, 33])
    assert result == []


def test_settlement_ratio_shorter_than_members_falls_back_to_equal():
    """A stale 2-entry ratio with 3 members must not zero-out the third member."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("90000")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert len(result) == 2
    assert all(t["to_user_id"] == "u1" for t in result)
    assert sum(t["amount"] for t in result) == Decimal("60000")


def test_settlement_amounts_are_whole_minor_units():
    """Expected shares are quantized; no fractional minor units in transfers."""
    members = [
        {"user_id": "u1", "full_name": "A", "total": Decimal("100")},
        {"user_id": "u2", "full_name": "B", "total": Decimal("0")},
        {"user_id": "u3", "full_name": "C", "total": Decimal("0")},
    ]
    result = calculate_settlement(members, [34, 33, 33])
    for t in result:
        assert t["amount"] == t["amount"].to_integral_value()
    # Balances net to zero: everything owed flows back to u1.
    assert sum(t["amount"] for t in result) == Decimal("66")


# ---------------------------------------------------------------------------
# Integration regressions (real DB): get_settlement must include zero-spend
# members and map split_ratio by joined_at ASC, not by spend order.
# ---------------------------------------------------------------------------


async def _seed_couple(db, split_ratio=None):
    """Household with two members; member A joined before member B."""
    a = User(
        id=_uuid.uuid4(),
        email=f"a-{_uuid.uuid4().hex[:8]}@luka.test",
        full_name="Ana First",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    b = User(
        id=_uuid.uuid4(),
        email=f"b-{_uuid.uuid4().hex[:8]}@luka.test",
        full_name="Beto Second",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add_all([a, b])
    await db.flush()

    h = Household(id=_uuid.uuid4(), name="Settle HH", type="couple")
    if split_ratio is not None:
        h.split_ratio = split_ratio
    db.add(h)
    await db.flush()

    now = datetime.now(timezone.utc)
    db.add(
        HouseholdMember(
            household_id=h.id, user_id=a.id, role="owner", joined_at=now - timedelta(days=2)
        )
    )
    db.add(HouseholdMember(household_id=h.id, user_id=b.id, role="member", joined_at=now))
    await db.flush()
    return a, b, h


async def _shared_expense(db, user, household, amount: str):
    tx = Transaction(
        id=_uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        raw_merchant_name="JUMBO",
        amount=Decimal(amount),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc),
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
    )
    db.add(tx)
    await db.flush()
    db.add(TransactionSplit(transaction_id=tx.id, split_type="shared"))
    await db.flush()
    return tx


async def test_get_settlement_includes_zero_spend_member(db):
    """One partner paid everything → the other still owes their half (was: no settlement)."""
    a, b, h = await _seed_couple(db)
    await _shared_expense(db, a, h, "-300000")

    result = await get_settlement(db, h.id, currency="CLP")
    transfers = result["transfers"]
    assert len(transfers) == 1
    assert transfers[0]["from_user_id"] == str(b.id)
    assert transfers[0]["to_user_id"] == str(a.id)
    assert transfers[0]["amount"] == Decimal("150000")


async def test_get_settlement_ratio_maps_by_join_order_not_spend(db):
    """split_ratio[0] belongs to the first joiner even when the second joiner outspends."""
    a, b, h = await _seed_couple(db, split_ratio=[70, 30])
    # B (joined second, ratio 30) paid everything.
    await _shared_expense(db, b, h, "-200000")

    result = await get_settlement(db, h.id, currency="CLP")
    transfers = result["transfers"]
    # A owes 70% of 200000 = 140000 to B — regardless of who spent more.
    assert len(transfers) == 1
    assert transfers[0]["from_user_id"] == str(a.id)
    assert transfers[0]["to_user_id"] == str(b.id)
    assert transfers[0]["amount"] == Decimal("140000")
