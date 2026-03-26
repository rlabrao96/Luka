import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.config import settings


def _get_key() -> bytes:
    key_hex = settings.connect_encryption_key
    if not key_hex or len(key_hex) != 64:
        raise ValueError("CONNECT_ENCRYPTION_KEY must be a 64-char hex string (32 bytes)")
    return bytes.fromhex(key_hex)


def encrypt(plaintext: str) -> tuple[bytes, bytes]:
    """Encrypt plaintext with AES-256-GCM. Returns (ciphertext, iv)."""
    key = _get_key()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return ciphertext, iv


def decrypt(ciphertext: bytes, iv: bytes) -> str:
    """Decrypt ciphertext with AES-256-GCM. Returns plaintext string."""
    key = _get_key()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext.decode("utf-8")
