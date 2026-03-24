import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from modules.auth.models import User


@pytest.fixture
def user_no_tokens():
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=True,
        phone_whatsapp="+56912345678",
        google_access_token_enc=None,
        google_refresh_token_enc=None,
    )


@pytest.fixture
def user_with_tokens():
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=True,
        phone_whatsapp="+56912345678",
        google_access_token_enc="enc_access",
        google_refresh_token_enc="enc_refresh",
    )


@pytest.mark.asyncio
async def test_process_email_skips_when_no_tokens(user_no_tokens):
    """process_email should return early if user has no Google tokens."""
    from jobs.tasks import process_email

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_no_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("jobs.tasks.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_email(
            ctx={},
            provider="gmail",
            email_address="rafa@test.cl",
            history_id="123",
        )


@pytest.mark.asyncio
async def test_process_email_clears_tokens_on_refresh_error(user_with_tokens):
    """process_email should null tokens when Google returns RefreshError."""
    from jobs.tasks import process_email

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=user_with_tokens)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_provider = AsyncMock()
    mock_provider.fetch_new_emails = AsyncMock(
        side_effect=Exception("invalid_grant: Token has been revoked")
    )

    with (
        patch("jobs.tasks.AsyncSessionLocal") as mock_session_cls,
        patch("jobs.tasks.decrypt_token", return_value="decrypted"),
        patch("jobs.tasks.get_email_provider", return_value=mock_provider),
    ):
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_email(
            ctx={},
            provider="gmail",
            email_address="rafa@test.cl",
            history_id="123",
        )

    assert user_with_tokens.google_access_token_enc is None
    assert user_with_tokens.google_refresh_token_enc is None
