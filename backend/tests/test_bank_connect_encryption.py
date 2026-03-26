import os
from unittest.mock import patch

import pytest

from modules.bank_connect.encryption import decrypt, encrypt

_TEST_KEY = "a" * 64  # 32 bytes as hex, valid for AES-256


@pytest.fixture(autouse=True)
def patch_encryption_key():
    """Inject a valid test key into settings for every test in this module."""
    with patch("modules.bank_connect.encryption.settings") as mock_settings:
        mock_settings.connect_encryption_key = _TEST_KEY
        yield mock_settings


def test_encrypt_decrypt_roundtrip():
    plaintext = "12345678-9"
    encrypted, iv = encrypt(plaintext)
    assert encrypted != plaintext.encode()
    assert len(iv) == 12  # GCM standard nonce
    result = decrypt(encrypted, iv)
    assert result == plaintext


def test_different_plaintexts_produce_different_ciphertexts():
    e1, iv1 = encrypt("password1")
    e2, iv2 = encrypt("password2")
    assert e1 != e2


def test_wrong_iv_fails():
    encrypted, iv = encrypt("secret")
    wrong_iv = os.urandom(12)
    with pytest.raises(Exception):
        decrypt(encrypted, wrong_iv)
