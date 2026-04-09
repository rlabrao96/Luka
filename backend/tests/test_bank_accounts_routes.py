import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

HOUSEHOLD_ID = str(uuid.uuid4())
ACCOUNT_ID = str(uuid.uuid4())


def _make_bank_account(is_active=True, user_id=None):
    acc = MagicMock()
    acc.id = uuid.UUID(ACCOUNT_ID)
    acc.is_active = is_active
    acc.user_id = user_id  # caller must pass mock_current_user.id for ownership tests; None = unknown other user
    acc.account_type = "personal"
    return acc


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


# ---------------------------------------------------------------------------
# GET /bank-accounts — updated list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_bank_accounts_includes_currency_and_is_active(
    http_client, override_auth, override_db
):
    mock_member = MagicMock()

    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    mock_account.bank_name = "Banco de Chile"
    mock_account.account_type = "personal"
    mock_account.account_kind = "checking_account"
    mock_account.account_number = "****1234"
    mock_account.cardholder_name = None
    mock_account.currency = "CLP"
    mock_account.is_active = True
    mock_account.user_id = uuid.uuid4()

    member_result = _make_execute_result(mock_member)

    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [mock_account]

    override_db.execute = AsyncMock(side_effect=[member_result, accounts_result])

    response = await http_client.get(f"/bank-accounts?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["currency"] == "CLP"
    assert data[0]["is_active"] is True


@pytest.mark.asyncio
async def test_list_bank_accounts_returns_inactive_accounts(
    http_client, override_auth, override_db
):
    """Inactive accounts must be returned so the settings UI can render the toggle."""
    mock_member = MagicMock()

    mock_inactive = MagicMock()
    mock_inactive.id = uuid.uuid4()
    mock_inactive.bank_name = "Santander"
    mock_inactive.account_type = "personal"
    mock_inactive.account_kind = None
    mock_inactive.account_number = None
    mock_inactive.cardholder_name = None
    mock_inactive.currency = "CLP"
    mock_inactive.is_active = False
    mock_inactive.user_id = uuid.uuid4()

    member_result = _make_execute_result(mock_member)
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [mock_inactive]
    override_db.execute = AsyncMock(side_effect=[member_result, accounts_result])

    response = await http_client.get(f"/bank-accounts?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_active"] is False


@pytest.mark.asyncio
async def test_list_bank_accounts_filters_partner_personal_accounts(
    http_client, override_auth, override_db, mock_current_user
):
    """Regression: `/bank-accounts` must NEVER return a partner's personal or
    partner-type accounts to another household member. Only the current user's
    own accounts plus household joint accounts should come back.

    Context: Camila saw Rafael's Bank of America balance on her dashboard's
    BalanceCard because this endpoint filtered by household_id only.
    """
    mock_member = MagicMock()
    member_result = _make_execute_result(mock_member)

    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = []

    captured: list = []

    async def capturing_execute(stmt, *args, **kwargs):
        captured.append(stmt)
        # Return the member result for the first call, accounts for the second.
        return member_result if len(captured) == 1 else accounts_result

    override_db.execute = capturing_execute

    response = await http_client.get(f"/bank-accounts?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200

    # The second execute call is the bank-accounts select. Compile its WHERE
    # clause and verify it contains both the user-ownership filter and the
    # joint-account escape hatch.
    assert len(captured) >= 2
    compiled = str(captured[1].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "bank_accounts.household_id" in compiled
    assert "bank_accounts.user_id" in compiled, (
        "SELECT on /bank-accounts is missing the user_id filter — "
        "partner accounts will leak across the household."
    )
    assert "'joint'" in compiled, (
        "SELECT on /bank-accounts is missing the account_type='joint' filter — "
        "joint household accounts will be hidden from non-owners."
    )
