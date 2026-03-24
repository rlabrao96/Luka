import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_fernet():
    """Reset singleton between tests."""
    import core.encryption as enc

    enc._fernet = None
    yield
    enc._fernet = None


def test_encrypt_decrypt_round_trip():
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key
        from core.encryption import encrypt_token, decrypt_token

        ciphertext = encrypt_token("my-secret-token")
        assert ciphertext != "my-secret-token"
        assert decrypt_token(ciphertext) == "my-secret-token"


def test_decrypt_with_wrong_key_raises():
    from cryptography.fernet import Fernet, InvalidToken

    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()

    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key1
        from core.encryption import encrypt_token

        ciphertext = encrypt_token("secret")

    import core.encryption as enc

    enc._fernet = None

    with patch("core.encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = key2
        from core.encryption import decrypt_token

        with pytest.raises(InvalidToken):
            decrypt_token(ciphertext)
