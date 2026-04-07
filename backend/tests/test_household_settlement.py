from decimal import Decimal
from modules.households.service import build_category_breakdown, calculate_settlement


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
