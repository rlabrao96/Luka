import uuid
from datetime import datetime, timedelta, timezone
from random import randint

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.bank_connect.encryption import encrypt, decrypt
from modules.bank_connect.models import BankCredential

_MIN_SYNC_INTERVAL = timedelta(hours=1)


async def store_credentials(
    db: AsyncSession, user_id: str, bank_code: str, rut: str, password: str
) -> BankCredential:
    """Encrypt and store bank credentials. Sets initial sync schedule."""
    encrypted_rut, iv_rut = encrypt(rut)
    encrypted_password, iv_password = encrypt(password)
    iv = iv_rut + iv_password  # 24 bytes: 12 for rut + 12 for password

    cred = BankCredential(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        bank_code=bank_code,
        encrypted_rut=encrypted_rut,
        encrypted_password=encrypted_password,
        encryption_iv=iv,
        next_sync_at=_random_next_sync(),
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def delete_credentials(db: AsyncSession, user_id: str, bank_code: str) -> None:
    """Hard delete credentials for a user+bank."""
    await db.execute(
        delete(BankCredential).where(
            BankCredential.user_id == uuid.UUID(user_id),
            BankCredential.bank_code == bank_code,
        )
    )
    await db.commit()


async def get_connection_status(
    db: AsyncSession, user_id: str, bank_code: str
) -> BankCredential | None:
    """Get credential record (without decrypting)."""
    result = await db.execute(
        select(BankCredential).where(
            BankCredential.user_id == uuid.UUID(user_id),
            BankCredential.bank_code == bank_code,
        )
    )
    return result.scalar_one_or_none()


async def get_user_connections(db: AsyncSession, user_id: str) -> list[BankCredential]:
    """List all bank connections for a user."""
    result = await db.execute(
        select(BankCredential).where(BankCredential.user_id == uuid.UUID(user_id))
    )
    return list(result.scalars().all())


async def decrypt_credentials(cred: BankCredential) -> tuple[str, str]:
    """Decrypt rut and password from a BankCredential."""
    iv_rut = cred.encryption_iv[:12]
    iv_password = cred.encryption_iv[12:24]
    rut = decrypt(cred.encrypted_rut, iv_rut)
    password = decrypt(cred.encrypted_password, iv_password)
    return rut, password


async def trigger_sync(
    db: AsyncSession,
    cred: BankCredential,
    mode: str = "recent",
    callback_url: str | None = None,
) -> dict:
    """Call Luka Connect to start a scrape. Returns sync response."""
    if cred.last_sync_at and (datetime.now(timezone.utc) - cred.last_sync_at) < _MIN_SYNC_INTERVAL:
        return {"error": "rate_limited", "message": "Max 1 sync per hour"}

    rut, password = await decrypt_credentials(cred)
    job_id = str(uuid.uuid4())

    cred.current_job_id = uuid.UUID(job_id)
    cred.last_sync_status = "in_progress"
    await db.commit()

    payload = {
        "bank": cred.bank_code,
        "rut": rut,
        "password": password,
        "mode": mode,
        "jobId": job_id,
    }
    if callback_url:
        payload["callbackUrl"] = callback_url

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        resp = await client.post(
            f"{settings.luka_connect_url}/scrape",
            json=payload,
            headers={"X-API-Key": settings.luka_connect_api_key},
        )
        return resp.json()


def _random_next_sync() -> datetime:
    """Random time in the next 24h window."""
    now = datetime.now(timezone.utc)
    offset_minutes = randint(60, 1440)
    return now + timedelta(minutes=offset_minutes)
