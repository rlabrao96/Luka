"""Initial-sync cutoff: bulk-history ingestion skips transactions dated before
``users.transactions_since``. Tests the Luka Connect path directly (the Plaid
path applies the identical ``since_cutoff`` guard in run_plaid_sync's loop).

Real DB, savepoint-rollback ``db`` fixture (no mocks, per CLAUDE.md).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.bank_connect.models import BankCredential
from modules.bank_connect.router import _process_movements
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction


async def _seed(db, transactions_since: date | None):
    user = User(
        id=uuid.uuid4(),
        email=f"cutoff-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Cutoff Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
        transactions_since=transactions_since,
    )
    db.add(user)
    await db.flush()
    hh = Household(id=uuid.uuid4(), name="HH", type="couple")
    db.add(hh)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))
    account = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Banco de Chile",
        account_type="personal",
        account_kind="checking_account",
        account_name="Cuenta Corriente",
        currency="CLP",
        is_active=True,
    )
    db.add(account)
    cred = BankCredential(
        id=uuid.uuid4(),
        user_id=user.id,
        bank_code="bchile",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
    )
    db.add(cred)
    await db.flush()
    return user, hh, account, cred


def _mov(account_name, day, amount, desc):
    return {
        "accountName": account_name,
        "currency": "CLP",
        "source": "checking_account",
        "amount": amount,
        "description": desc,
        "date": day,  # YYYY-MM-DD
        "time": "12:00",
    }


async def test_movements_before_cutoff_are_skipped(db):
    user, hh, account, cred = await _seed(db, transactions_since=date(2026, 6, 1))
    ba_map = {(account.account_name, "CLP"): account.id}
    movements = [
        _mov(account.account_name, "2026-05-20", -5000, "MAYO ANTES DEL CORTE"),
        _mov(account.account_name, "2026-06-10", -7000, "JUNIO DESPUES DEL CORTE"),
    ]
    created, enriched, skipped = await _process_movements(db, cred, movements, ba_map)
    await db.flush()

    assert created == 1, f"only the post-cutoff movement should create a txn (got {created})"
    assert skipped >= 1, "the pre-cutoff movement should be skipped"

    txns = (
        (await db.execute(select(Transaction).where(Transaction.user_id == user.id)))
        .scalars()
        .all()
    )
    descs = {t.raw_merchant_name for t in txns}
    assert any("JUNIO" in d for d in descs)
    assert not any("MAYO" in d for d in descs), "pre-cutoff movement must not be ingested"


async def test_no_cutoff_ingests_all(db):
    user, hh, account, cred = await _seed(db, transactions_since=None)
    ba_map = {(account.account_name, "CLP"): account.id}
    movements = [
        _mov(account.account_name, "2026-05-20", -5000, "MAYO SIN CORTE"),
        _mov(account.account_name, "2026-06-10", -7000, "JUNIO SIN CORTE"),
    ]
    created, enriched, skipped = await _process_movements(db, cred, movements, ba_map)
    assert created == 2, f"with no cutoff both movements ingest (got {created})"
