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
    result = build_category_breakdown([])
    assert result == []


def test_settlement_50_50():
    """With 50/50 split, person who paid less owes their expected share minus what they paid."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("180500")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("294960")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert result["from_user_id"] == "u1"
    assert result["to_user_id"] == "u2"
    assert result["amount"] == Decimal("57230")


def test_settlement_60_40():
    """With 60/40, settlement accounts for unequal expected shares."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("100000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("100000")},
    ]
    result = calculate_settlement(members, [60, 40])
    assert result["from_user_id"] == "u1"
    assert result["to_user_id"] == "u2"
    assert result["amount"] == Decimal("20000")


def test_settlement_balanced():
    """When both paid their fair share, amount is 0."""
    members = [
        {"user_id": "u1", "full_name": "Rodrigo", "total": Decimal("50000")},
        {"user_id": "u2", "full_name": "María", "total": Decimal("50000")},
    ]
    result = calculate_settlement(members, [50, 50])
    assert result["amount"] == Decimal("0")
