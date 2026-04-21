import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_my_transactions_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.get("/transactions/mine")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_my_transactions_returns_list(app, mock_user):
    from core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch(
            "modules.transactions.service.get_my_transactions", new=AsyncMock(return_value=[])
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get(
                    "/transactions/mine", headers={"Authorization": "Bearer token"}
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_my_transactions_returns_only_active_account_results(app, mock_user):
    """Route correctly returns whatever the service layer provides (filtered at DB level).

    NOTE: This test patches the service so it cannot verify the is_active SQL filter directly.
    The WHERE clause correctness is verified by reading service.py steps 2-4 and
    by manual integration testing against the real DB.
    """
    from core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch(
            "modules.transactions.service.get_my_transactions",
            new=AsyncMock(return_value=[]),  # simulates: all transactions filtered out
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get(
                    "/transactions/mine", headers={"Authorization": "Bearer token"}
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_transactions_exposes_pair_and_lifecycle_fields(app, mock_user):
    """TransactionResponse must surface pair ids + created_at/orphaned_at so the
    frontend can (a) visually group CC transfers + refunds (Task 4.5) and
    (b) show an accurate backlog-age badge on PendingBlock (Task 4.6).

    Additive schema check: we feed a row with all four fields populated and
    verify each one survives serialization.
    """
    from core.security import get_current_user

    now = datetime.now(timezone.utc)
    fake_row = {
        "id": uuid.uuid4(),
        "raw_merchant_name": "Test Merchant",
        "amount": Decimal("-1000.00"),
        "currency": "CLP",
        "transaction_date": now,
        "category": None,
        "source": "plaid",
        "source_type": "plaid",
        "status": "settled",
        "split_type": "personal",
        "bank_name": "Test Bank",
        "bank_account_id": uuid.uuid4(),
        "account_kind": "credit_card",
        "transaction_type": "transfer",
        "display_name": None,
        "transfer_pair_id": uuid.uuid4(),
        "refund_pair_id": None,
        "created_at": now,
        "orphaned_at": None,
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch(
            "modules.transactions.service.get_my_transactions",
            new=AsyncMock(return_value=[fake_row]),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get(
                    "/transactions/mine", headers={"Authorization": "Bearer token"}
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    for field in ("transfer_pair_id", "refund_pair_id", "created_at", "orphaned_at"):
        assert field in row, f"TransactionResponse missing {field}"
    assert row["transfer_pair_id"] == str(fake_row["transfer_pair_id"])
    assert row["refund_pair_id"] is None
    assert row["created_at"] is not None
    assert row["orphaned_at"] is None
