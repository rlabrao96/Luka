"""Shared-card charge classification — pending, dual-visibility, four-way sort,
effective-payer. Real DB, savepoint-rollback db fixture (no mocks)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction


async def _couple(db):
    hh = Household(id=uuid.uuid4(), name="HH", type="couple")
    db.add(hh)
    await db.flush()
    users = {}
    for name, role in (("rafael", "owner"), ("camila", "member")):
        u = User(
            id=uuid.uuid4(),
            email=f"{name}-{uuid.uuid4().hex[:8]}@luka.test",
            full_name=name.title(),
            email_provider="gmail",
            whatsapp_verified=False,
            preferred_currency="USD",
        )
        db.add(u)
        await db.flush()
        db.add(HouseholdMember(household_id=hh.id, user_id=u.id, role=role))
        users[name] = u
    await db.flush()
    return users["rafael"], users["camila"], hh


async def _shared_card(db, owner, hh):
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=owner.id,
        bank_name="American Express",
        account_type="shared_card",
        account_kind="credit_card",
        account_name="Platinum",
        currency="USD",
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


async def _charge(
    db, owner, hh, acct, amount="-40.00", needs_classification=False, ttype="expense"
):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=owner.id,
        household_id=hh.id,
        bank_account_id=acct.id,
        raw_merchant_name="Sephora",
        amount=Decimal(amount),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type=ttype,
        needs_classification=needs_classification,
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_needs_classification_and_shared_card_persist(db):
    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    assert acct.account_type == "shared_card"
    txn = await _charge(db, rafael, hh, acct, needs_classification=True)
    row = (await db.execute(select(Transaction).where(Transaction.id == txn.id))).scalar_one()
    assert row.needs_classification is True


async def test_pending_charge_counts_for_nobody(db):
    from sqlalchemy import select
    from modules.transactions.models import Transaction
    from modules.transactions.totals import exclude_from_totals
    from modules.transactions.attribution import account_person_balances

    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    pending = await _charge(db, rafael, hh, acct, amount="-40.00", needs_classification=True)
    settled = await _charge(db, rafael, hh, acct, amount="-10.00", needs_classification=False)
    await db.flush()

    # totals exclusion: pending row must not be returned by an aggregate query
    q = exclude_from_totals(select(Transaction.id).where(Transaction.household_id == hh.id))
    ids = (await db.execute(q)).scalars().all()
    assert pending.id not in ids
    assert settled.id in ids

    # per-person balance: pending charge must not appear
    balances = await account_person_balances(db, acct.id)
    total_gastos = sum(b["gastos"] for b in balances)
    assert total_gastos == 10, (
        f"only the settled -10.00 charge should count (pending -40.00 excluded), got {total_gastos}"
    )


# ---------------------------------------------------------------- should_pend (pure helper)


def test_should_pend_non_transfer_on_shared_card():
    from modules.transactions.classification import should_pend

    assert should_pend("shared_card", "expense") is True


def test_should_pend_income_on_shared_card():
    from modules.transactions.classification import should_pend

    assert should_pend("shared_card", "income") is True


def test_should_pend_transfer_on_shared_card_is_false():
    from modules.transactions.classification import should_pend

    assert should_pend("shared_card", "transfer") is False


def test_should_pend_non_shared_card_is_false():
    from modules.transactions.classification import should_pend

    assert should_pend("personal", "expense") is False


# ---------------------------------------------------------------- ingestion wiring (Connect)


async def test_bank_connect_process_movements_shared_card_pends_classification(db):
    """A non-transfer movement landing on a shared_card account via Connect
    ingestion must be created with needs_classification=True."""
    import uuid as uuid_mod

    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.router import _process_movements

    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)

    cred = BankCredential(
        id=uuid_mod.uuid4(),
        user_id=rafael.id,
        bank_code="bci",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
    )
    db.add(cred)
    await db.flush()

    movement = {
        "accountName": acct.account_name,
        "currency": "USD",
        "source": "credit_card",
        "amount": -40.00,
        "description": "SEPHORA STORE",
        "date": "2025-01-15",
        "time": "12:30",
    }
    ba_map = {(acct.account_name, "USD"): acct.id}

    created, enriched, skipped = await _process_movements(db, cred, [movement], ba_map)
    assert created == 1, (
        f"expected 1 created, got created={created} enriched={enriched} skipped={skipped}"
    )
    await db.flush()

    txn = (
        await db.execute(
            select(Transaction).where(
                Transaction.user_id == rafael.id,
                Transaction.source == "connect",
            )
        )
    ).scalar_one()

    assert txn.transaction_type != "transfer"
    assert txn.needs_classification is True, (
        "non-transfer charge on a shared_card must be pended for classification"
    )


async def test_bank_connect_process_movements_shared_card_transfer_not_pended(db):
    """A CC-bill-payment transfer on a shared_card account must NEVER be pended,
    even though the account is shared_card."""
    import uuid as uuid_mod

    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.router import _process_movements

    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)

    cred = BankCredential(
        id=uuid_mod.uuid4(),
        user_id=rafael.id,
        bank_code="bci",
        encrypted_rut=b"x",
        encrypted_password=b"x",
        encryption_iv=b"x",
    )
    db.add(cred)
    await db.flush()

    movement = {
        "accountName": acct.account_name,
        "currency": "USD",
        "source": "credit_card",
        "amount": -150.00,
        "description": "Pago Tarjeta Visa",
        "date": "2025-01-15",
        "time": "12:30",
    }
    ba_map = {(acct.account_name, "USD"): acct.id}

    created, enriched, skipped = await _process_movements(db, cred, [movement], ba_map)
    assert created == 1, (
        f"expected 1 created, got created={created} enriched={enriched} skipped={skipped}"
    )
    await db.flush()

    txn = (
        await db.execute(
            select(Transaction).where(
                Transaction.user_id == rafael.id,
                Transaction.source == "connect",
            )
        )
    ).scalar_one()

    assert txn.transaction_type == "transfer"
    assert txn.needs_classification is False, (
        "a transfer on a shared_card must never be pended for classification"
    )


# ---------------------------------------------------------------- list_pending_for_household


async def test_list_pending_for_household_returns_shared_card_pending_rows():
    from modules.transactions.classification import list_pending_for_household

    assert callable(list_pending_for_household)


async def test_list_pending_for_household_both_members_see_same_set(db):
    from modules.transactions.classification import list_pending_for_household

    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    pending = await _charge(db, rafael, hh, acct, amount="-40.00", needs_classification=True)

    rows_rafael = await list_pending_for_household(db, hh.id)
    rows_camila = await list_pending_for_household(db, hh.id)

    ids_rafael = {t.id for t in rows_rafael}
    ids_camila = {t.id for t in rows_camila}
    assert ids_rafael == ids_camila == {pending.id}


async def test_list_pending_for_household_excludes_non_shared_card_account(db):
    from modules.transactions.classification import list_pending_for_household

    rafael, camila, hh = await _couple(db)
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=rafael.id,
        bank_name="Bci",
        account_type="personal",
        account_kind="checking",
        account_name="Cuenta Corriente",
        currency="USD",
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    txn = await _charge(db, rafael, hh, acct, amount="-40.00", needs_classification=True)

    rows = await list_pending_for_household(db, hh.id)
    assert txn.id not in {t.id for t in rows}


async def test_list_pending_for_household_excludes_settled_shared_card_charge(db):
    from modules.transactions.classification import list_pending_for_household

    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    settled = await _charge(db, rafael, hh, acct, amount="-10.00", needs_classification=False)

    rows = await list_pending_for_household(db, hh.id)
    assert settled.id not in {t.id for t in rows}


# ---------------------------------------------------------------- GET /transactions/por-clasificar


def _override(app, user, db):
    from core.database import get_db
    from core.security import get_current_user

    async def _fake_db():
        yield db

    async def _fake_user():
        return user

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user


async def test_por_clasificar_endpoint_active_member_gets_rows(app, db, http_client):
    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    pending = await _charge(db, rafael, hh, acct, amount="-40.00", needs_classification=True)
    _override(app, camila, db)

    r = await http_client.get(f"/transactions/por-clasificar?household_id={hh.id}")
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()}
    assert ids == {str(pending.id)}


async def test_por_clasificar_endpoint_non_member_forbidden(app, db, http_client):
    rafael, camila, hh = await _couple(db)
    acct = await _shared_card(db, rafael, hh)
    await _charge(db, rafael, hh, acct, amount="-40.00", needs_classification=True)

    outsider = User(
        id=uuid.uuid4(),
        email=f"outsider-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Outsider",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(outsider)
    await db.flush()
    _override(app, outsider, db)

    r = await http_client.get(f"/transactions/por-clasificar?household_id={hh.id}")
    assert r.status_code == 403
