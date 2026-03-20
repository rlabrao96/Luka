import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

HOUSEHOLD_ID = str(uuid.uuid4())
ACCOUNT_ID = str(uuid.uuid4())


def _make_bank_account(import_status="done", is_active=True, user_id=None):
    acc = MagicMock()
    acc.id = uuid.UUID(ACCOUNT_ID)
    acc.import_status = import_status
    acc.is_active = is_active
    acc.user_id = user_id  # caller must pass mock_current_user.id for ownership tests; None = unknown other user
    acc.account_type = "personal"
    return acc


@pytest.mark.asyncio
async def test_get_fintoc_accounts_returns_list(http_client, override_auth, override_db):
    mock_accounts = [
        {
            "id": "acc_1",
            "name": "Cuenta Corriente",
            "type": "checking_account",
            "number": "****1234",
        },
    ]
    with patch("modules.bank_accounts.router.FintocClient") as MockClient:
        instance = AsyncMock()
        instance.fetch_accounts = AsyncMock(return_value=mock_accounts)
        MockClient.return_value = instance

        response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")

    assert response.status_code == 200
    assert response.json() == mock_accounts


@pytest.mark.asyncio
async def test_get_fintoc_accounts_requires_auth(http_client):
    response = await http_client.get("/bank-accounts/fintoc/accounts?link_token=lt_test")
    assert response.status_code in (401, 403)  # unauthenticated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_execute_result(scalar_value):
    """Return a mock execute result where .scalar_one_or_none() returns scalar_value.

    Note: SQLAlchemy's CursorResult methods (scalar_one_or_none, scalars) are
    synchronous on the result object — only the execute() call itself is async.
    """
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    result.scalars.return_value.first.return_value = scalar_value
    return result


# ---------------------------------------------------------------------------
# Task 8: POST /bank-accounts/fintoc/connect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_fintoc_returns_403_if_not_member(http_client, override_auth, override_db):
    # _require_membership uses db.execute(...).scalar_one_or_none() -> None = not a member
    override_db.execute = AsyncMock(return_value=_make_execute_result(None))

    response = await http_client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_test",
            "household_id": HOUSEHOLD_ID,
            "accounts": [{"fintoc_account_id": "acc_1", "label": "personal"}],
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_connect_fintoc_creates_accounts(
    http_client, override_auth, override_db, mock_current_user
):
    mock_member = MagicMock()
    # _require_membership: db.execute returns member found
    override_db.execute = AsyncMock(return_value=_make_execute_result(mock_member))
    # db.scalar: duplicate checks return None (no duplicate)
    override_db.scalar = AsyncMock(side_effect=[None, None])
    override_db.flush = AsyncMock()

    with patch("modules.bank_accounts.router.enqueue_job", AsyncMock(return_value=None)):
        response = await http_client.post(
            "/bank-accounts/fintoc/connect",
            json={
                "link_token": "lt_abc",
                "household_id": HOUSEHOLD_ID,
                "accounts": [
                    {"fintoc_account_id": "acc_1", "label": "personal"},
                    {"fintoc_account_id": "acc_2", "label": "joint"},
                ],
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 2


@pytest.mark.asyncio
async def test_connect_fintoc_returns_409_on_duplicate(http_client, override_auth, override_db):
    mock_member = MagicMock()
    mock_existing = MagicMock()  # existing account found
    # _require_membership: execute returns member
    override_db.execute = AsyncMock(return_value=_make_execute_result(mock_member))
    # db.scalar: duplicate check returns existing account
    override_db.scalar = AsyncMock(return_value=mock_existing)

    response = await http_client.post(
        "/bank-accounts/fintoc/connect",
        json={
            "link_token": "lt_abc",
            "household_id": HOUSEHOLD_ID,
            "accounts": [{"fintoc_account_id": "acc_duplicate", "label": "personal"}],
        },
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Task 9: GET /bank-accounts/import-status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_status_403_if_not_member(http_client, override_auth, override_db):
    # _require_membership: execute returns None = not a member
    override_db.execute = AsyncMock(return_value=_make_execute_result(None))
    response = await http_client.get(f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_status_true_when_pending_accounts_exist(
    http_client, override_auth, override_db
):
    mock_member = MagicMock()
    mock_pending_account = MagicMock()

    # First execute call: _require_membership (member found)
    # Second execute call: query for pending accounts (pending found)
    member_result = _make_execute_result(mock_member)
    pending_result = MagicMock()
    pending_result.scalars.return_value.first.return_value = mock_pending_account

    override_db.execute = AsyncMock(side_effect=[member_result, pending_result])

    response = await http_client.get(f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    assert response.json() == {"importing": True}


@pytest.mark.asyncio
async def test_import_status_false_when_all_done(http_client, override_auth, override_db):
    mock_member = MagicMock()

    # First execute call: _require_membership (member found)
    # Second execute call: no pending accounts
    member_result = _make_execute_result(mock_member)
    no_pending_result = MagicMock()
    no_pending_result.scalars.return_value.first.return_value = None

    override_db.execute = AsyncMock(side_effect=[member_result, no_pending_result])

    response = await http_client.get(f"/bank-accounts/import-status?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    assert response.json() == {"importing": False}


# ---------------------------------------------------------------------------
# PATCH /bank-accounts/{account_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_bank_account_updates_type(
    http_client, override_auth, override_db, mock_current_user
):
    mock_member = MagicMock()
    mock_account = _make_bank_account(user_id=mock_current_user.id)

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)
    override_db.commit = AsyncMock()

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"account_type": "joint"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["account_type"] == "joint"


@pytest.mark.asyncio
async def test_patch_bank_account_403_for_non_owner(
    http_client, override_auth, override_db, mock_current_user
):
    mock_member = MagicMock()
    # account owned by a different user
    mock_account = _make_bank_account(user_id=uuid.uuid4())

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"account_type": "joint"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_bank_account_409_disable_while_importing(
    http_client, override_auth, override_db, mock_current_user
):
    mock_member = MagicMock()
    mock_account = _make_bank_account(import_status="importing", user_id=mock_current_user.id)

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"is_active": False},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_bank_account_404_not_found(http_client, override_auth, override_db):
    mock_member = MagicMock()
    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=None)  # account not found

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"is_active": False},
    )
    assert response.status_code == 404
