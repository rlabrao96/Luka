"""Tests for email-to-bank dedup correctness in modules/reconciliation/dedup.py.

Covers Task 2.3 (_find_single_match filters) and Task 2.4 (user_id guard +
transfer-type propagation on apply_match_and_delete_emails).

Uses the `db` savepoint fixture from conftest.py. All inserts roll back at end.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

# Register every model so Base.metadata resolves each FK when the session flushes.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.reconciliation.dedup import (
    _find_single_match,
    apply_match_and_delete_emails,
)
from modules.transactions.models import Transaction, TransactionSplit


# ---------------------------------------------------------------- helpers


async def _seed_household(db, *, currency: str = "USD") -> tuple[User, Household, BankAccount]:
    user = User(
        id=uuid.uuid4(),
        email=f"dedup-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Dedup Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Dedup HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


def _email_tx(
    *,
    user: User,
    household: Household,
    account: BankAccount | None,
    amount: Decimal,
    when: datetime,
    merchant: str = "Amazon",
    currency: str = "USD",
    tx_type: str = "expense",
    category: str | None = None,
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id if account else None,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=when,
        category=category,
        source="gmail",
        source_type="email",
        status="pending",
        transaction_type=tx_type,
    )


def _bank_tx(
    *,
    user: User,
    household: Household,
    account: BankAccount,
    amount: Decimal,
    when: datetime,
    merchant: str = "Amazon",
    currency: str = "USD",
    tx_type: str = "expense",
) -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        bank_account_id=account.id,
        raw_merchant_name=merchant,
        amount=amount,
        currency=currency,
        transaction_date=when,
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type=tx_type,
    )


async def _reload(db, tx_id: uuid.UUID) -> Transaction | None:
    res = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    return res.scalar_one_or_none()


# ---------------------------------------------------------------- Task 2.3 tests


@pytest.mark.asyncio
async def test_find_single_match_rejects_different_currency(db):
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)
    # Email stored in CLP
    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-27.43"),
        when=when,
        merchant="Amazon",
        currency="CLP",
    )
    db.add(email)
    await db.flush()

    # Looking up USD -27.43 should not match the CLP row
    match = await _find_single_match(
        db,
        user.id,
        "Amazon",
        -27.43,
        when,
        day_window=2,
        amount_tolerance=0.0,
        currency="USD",
        incoming_transaction_type="expense",
        bank_account_id=acc.id,
    )
    assert match is None


@pytest.mark.asyncio
async def test_find_single_match_rejects_opposite_sign(db):
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)
    # Email is POSITIVE (income)
    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("27.43"),
        when=when,
        merchant="Amazon",
        currency="USD",
        tx_type="income",
    )
    db.add(email)
    await db.flush()

    # Bank comes in as negative (expense) — must not match
    match = await _find_single_match(
        db,
        user.id,
        "Amazon",
        -27.43,
        when,
        day_window=2,
        amount_tolerance=0.0,
        currency="USD",
        incoming_transaction_type="expense",
        bank_account_id=acc.id,
    )
    assert match is None


@pytest.mark.asyncio
async def test_find_single_match_matches_transfer_with_divergent_merchant_strings(db):
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)
    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-150.00"),
        when=when,
        merchant="Pago Tarjeta ****3100",
        currency="USD",
        tx_type="transfer",
    )
    db.add(email)
    await db.flush()

    # Bank side has a totally different merchant string
    match = await _find_single_match(
        db,
        user.id,
        "American Express",
        -150.00,
        when,
        day_window=2,
        amount_tolerance=0.0,
        currency="USD",
        incoming_transaction_type="transfer",
        bank_account_id=acc.id,
    )
    assert match is not None
    assert match.id == email.id


@pytest.mark.asyncio
async def test_find_single_match_requires_same_bank_account_when_both_set(db):
    user, hh, acc = await _seed_household(db, currency="USD")
    acc2 = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Chase",
        account_type="personal",
        currency="USD",
        is_active=True,
    )
    db.add(acc2)
    await db.flush()

    when = datetime.now(timezone.utc) - timedelta(days=1)
    # Two email candidates, same merchant / date / amount, different bank_account_id
    wrong = _email_tx(
        user=user,
        household=hh,
        account=acc2,
        amount=Decimal("-50.00"),
        when=when,
        merchant="Amazon",
    )
    right = _email_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-50.00"),
        when=when,
        merchant="Amazon",
    )
    db.add_all([wrong, right])
    await db.flush()

    match = await _find_single_match(
        db,
        user.id,
        "Amazon",
        -50.00,
        when,
        day_window=2,
        amount_tolerance=0.0,
        currency="USD",
        incoming_transaction_type="expense",
        bank_account_id=acc.id,
    )
    assert match is not None
    assert match.id == right.id


# ---------------------------------------------------------------- Task 2.4 tests


@pytest.mark.asyncio
async def test_apply_match_does_not_touch_other_users_rows(db):
    user_a, hh_a, acc_a = await _seed_household(db, currency="USD")
    user_b, hh_b, acc_b = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email_a = _email_tx(
        user=user_a,
        household=hh_a,
        account=None,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
    )
    email_b = _email_tx(
        user=user_b,
        household=hh_b,
        account=None,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
    )
    bank_a = _bank_tx(
        user=user_a, household=hh_a, account=acc_a, amount=Decimal("-42.00"), when=when
    )
    db.add_all([email_a, email_b, bank_a])
    await db.flush()

    await apply_match_and_delete_emails(
        db,
        bank_a.id,
        [email_a.id, email_b.id],
        {"merchant_id": None, "category": None, "transaction_type": "expense"},
        user_id=user_a.id,
    )
    await db.flush()

    assert await _reload(db, email_a.id) is None
    reloaded_b = await _reload(db, email_b.id)
    assert reloaded_b is not None, "user B's email tx must not be deleted"


@pytest.mark.asyncio
async def test_apply_match_propagates_transfer_type_and_nulls_category(db):
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-150.00"),
        when=when,
        merchant="Pago Tarjeta ****3100",
        tx_type="transfer",
        category="Servicios",
    )
    bank = _bank_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-150.00"),
        when=when,
        merchant="American Express",
    )
    db.add_all([email, bank])
    await db.flush()

    await apply_match_and_delete_emails(
        db,
        bank.id,
        [email.id],
        {
            "merchant_id": None,
            "category": "Servicios",
            "transaction_type": "transfer",
        },
        user_id=user.id,
    )
    await db.flush()

    reloaded = await _reload(db, bank.id)
    assert reloaded is not None
    assert reloaded.transaction_type == "transfer"
    assert reloaded.category is None


# ---------------------------------------------------------------- user-edit-wins tests


async def _enrichment_from_email(db, tx_id: uuid.UUID) -> dict:
    from modules.reconciliation.dedup import _extract_enrichment

    return await _extract_enrichment(db, tx_id)


@pytest.mark.asyncio
async def test_user_edit_on_email_preserved_after_consolidation(db):
    """User sets category on email pending → Plaid arrives → category preserved
    AND the marker propagates onto the bank row."""
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
        category="Comida",
    )
    # Simulate user PATCH /category by stamping the marker.
    email.user_edited_fields = {"category": True}
    bank = _bank_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
    )
    db.add_all([email, bank])
    await db.flush()

    enrichment = await _enrichment_from_email(db, email.id)
    await apply_match_and_delete_emails(db, bank.id, [email.id], enrichment, user_id=user.id)
    await db.flush()

    reloaded = await _reload(db, bank.id)
    assert reloaded is not None
    assert reloaded.category == "Comida"
    assert reloaded.user_edited_fields.get("category") is True


@pytest.mark.asyncio
async def test_user_edit_on_bank_not_overwritten_by_late_email(db):
    """Plaid pending edited by user → email pending arrives later via reconciliation
    → bank's user-set category survives even if the email row carries another value."""
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
        category="Servicios",  # email-side category — must NOT win
    )
    bank = _bank_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-42.00"),
        when=when,
        merchant="Amazon",
    )
    bank.category = "Comida"
    bank.user_edited_fields = {"category": True}
    db.add_all([email, bank])
    await db.flush()

    enrichment = await _enrichment_from_email(db, email.id)
    await apply_match_and_delete_emails(db, bank.id, [email.id], enrichment, user_id=user.id)
    await db.flush()

    reloaded = await _reload(db, bank.id)
    assert reloaded is not None
    assert reloaded.category == "Comida"
    assert reloaded.user_edited_fields.get("category") is True


@pytest.mark.asyncio
async def test_vendor_name_prefers_plaid_enriched_when_no_user_edits(db):
    """Bank row has 'Best Buy' (Plaid enriched), email has 'Bestbuy.com',
    no user edits anywhere — consolidated bank row keeps 'Best Buy'."""
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-99.00"),
        when=when,
        merchant="Bestbuy.com",
    )
    bank = _bank_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-99.00"),
        when=when,
        merchant="Best Buy",
    )
    db.add_all([email, bank])
    await db.flush()

    enrichment = await _enrichment_from_email(db, email.id)
    await apply_match_and_delete_emails(db, bank.id, [email.id], enrichment, user_id=user.id)
    await db.flush()

    reloaded = await _reload(db, bank.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "Best Buy"


@pytest.mark.asyncio
async def test_vendor_name_user_edit_on_email_wins_over_plaid(db):
    """User renamed email row to 'My Best Buy' — that wins over Plaid's enriched name."""
    user, hh, acc = await _seed_household(db, currency="USD")
    when = datetime.now(timezone.utc) - timedelta(days=1)

    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-99.00"),
        when=when,
        merchant="My Best Buy",
    )
    email.user_edited_fields = {"merchant_name": True}
    bank = _bank_tx(
        user=user,
        household=hh,
        account=acc,
        amount=Decimal("-99.00"),
        when=when,
        merchant="Best Buy",
    )
    db.add_all([email, bank])
    await db.flush()

    enrichment = await _enrichment_from_email(db, email.id)
    await apply_match_and_delete_emails(db, bank.id, [email.id], enrichment, user_id=user.id)
    await db.flush()

    reloaded = await _reload(db, bank.id)
    assert reloaded is not None
    assert reloaded.raw_merchant_name == "My Best Buy"
    assert reloaded.user_edited_fields.get("merchant_name") is True


@pytest.mark.asyncio
async def test_joint_account_overrides_personal_split_marker(db):
    """Even if the user marked split_type=personal, a joint-account merge target
    must end up with split_type=shared. Joint always wins."""
    user, hh, _ = await _seed_household(db, currency="USD")
    joint = BankAccount(
        id=uuid.uuid4(),
        household_id=hh.id,
        user_id=user.id,
        bank_name="Joint Bank",
        account_type="joint",
        currency="USD",
        is_active=True,
    )
    db.add(joint)
    await db.flush()

    when = datetime.now(timezone.utc) - timedelta(days=1)
    email = _email_tx(
        user=user,
        household=hh,
        account=None,
        amount=Decimal("-25.00"),
        when=when,
        merchant="Costco",
    )
    bank = _bank_tx(
        user=user,
        household=hh,
        account=joint,
        amount=Decimal("-25.00"),
        when=when,
        merchant="Costco",
    )
    bank.user_edited_fields = {"split_type": True}
    db.add_all([email, bank])
    await db.flush()
    # Pre-existing personal split on the bank row.
    db.add(
        TransactionSplit(  # type: ignore[name-defined]
            id=uuid.uuid4(), transaction_id=bank.id, split_type="personal"
        )
    )
    await db.flush()

    enrichment = await _enrichment_from_email(db, email.id)
    await apply_match_and_delete_emails(db, bank.id, [email.id], enrichment, user_id=user.id)
    await db.flush()

    split_row = await db.execute(
        select(TransactionSplit).where(TransactionSplit.transaction_id == bank.id)  # type: ignore[name-defined]
    )
    split = split_row.scalar_one_or_none()
    assert split is not None
    assert split.split_type == "shared"
