"""Tests for Plaid CC-payment counterpart resolution + canonical 'settled' status.

Covers Tasks 2.5 + 2.6 of the transaction-consolidation fix:
  - Two-tier counterpart lookup (last-4 → name fallback) when a Plaid tx looks
    like a credit-card bill payment.
  - Modify-branch uses the shared amount helper (no 100× inflation on CLP).
  - Mapper writes canonical status='settled' (not legacy 'confirmed').
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

# Register every model so Base.metadata resolves each FK when the session flushes.
import modules.merchants.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.plaid.mapper import map_plaid_transaction, luka_amount_from_plaid
from modules.plaid.models import PlaidItem
from modules.plaid.sync import run_plaid_sync
from modules.transactions.models import Transaction


# ---------------------------------------------------------------- fakes


@dataclass
class FakePlaidBalances:
    current: float | None = 1000.0
    limit: float | None = None
    iso_currency_code: str | None = "USD"


@dataclass
class FakePlaidAccount:
    account_id: str
    name: str = "Checking"
    official_name: str | None = None
    mask: str | None = None
    type: str = "depository"
    subtype: str = "checking"
    balances: FakePlaidBalances = field(default_factory=FakePlaidBalances)


@dataclass
class FakePlaidTx:
    account_id: str
    transaction_id: str
    amount: float
    date: date
    name: str = ""
    merchant_name: str | None = None
    iso_currency_code: str = "USD"
    pending: bool = False
    category: list[str] | None = None
    personal_finance_category: object | None = None


@dataclass
class FakeSyncResponse:
    added: list = field(default_factory=list)
    modified: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    accounts: list = field(default_factory=list)
    has_more: bool = False
    next_cursor: str = "cursor-1"


# ---------------------------------------------------------------- helpers


async def _seed_plaid_household(
    db,
    *,
    amex_mask: str | None = "3100",
    amex_name: str = "American Express",
) -> tuple[User, Household, BankAccount, BankAccount, PlaidItem]:
    user = User(
        id=uuid.uuid4(),
        email=f"plaid-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Plaid Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Plaid HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    item = PlaidItem(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        plaid_item_id=f"item-{uuid.uuid4().hex[:8]}",
        access_token_enc="ignored",  # decrypt_token is patched in tests
        institution_id="ins_1",
        institution_name="Bank of America",
    )
    db.add(item)
    await db.flush()

    checking = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Bank Of America",
        account_type="personal",
        account_kind="checking_account",
        currency="USD",
        is_active=True,
        provider="plaid",
        country="US",
        plaid_item_id=item.id,
        plaid_account_id="plaid-checking",
    )
    amex = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=amex_name,
        account_type="personal",
        account_kind="credit_card",
        currency="USD",
        account_number=amex_mask,
        is_active=True,
        provider="plaid",
        country="US",
    )
    db.add_all([checking, amex])
    await db.flush()
    return user, household, checking, amex, item


async def _run_sync_with_fake(db, item, response: FakeSyncResponse) -> dict:
    """Run run_plaid_sync with the Plaid client and token decrypt stubbed."""
    with (
        patch("modules.plaid.sync.sync_transactions", return_value=response),
        patch("modules.plaid.sync.decrypt_token", return_value="fake-access-token"),
    ):
        return await run_plaid_sync(db, item.id)


# ---------------------------------------------------------------- tests — CC counterpart


@pytest.mark.asyncio
async def test_cc_payment_with_last_four_links_amex(db):
    user, hh, checking, amex, item = await _seed_plaid_household(db, amex_mask="3100")

    # Fake Plaid response: one TRANSFER+CREDIT_CARD payment from checking, mentions ****3100
    plaid_tx = FakePlaidTx(
        account_id="plaid-checking",
        transaction_id="tx-amex-pago-1",
        amount=2000.0,  # Plaid positive = outflow
        date=date.today(),
        name="Pago Tarjeta American Express ****3100",
        merchant_name="American Express",
        category=["Transfer", "Credit Card"],
    )
    plaid_account = FakePlaidAccount(account_id="plaid-checking")
    response = FakeSyncResponse(added=[plaid_tx], accounts=[plaid_account])

    stats = await _run_sync_with_fake(db, item, response)
    assert stats["added"] == 1

    result = await db.execute(
        select(Transaction).where(Transaction.plaid_transaction_id == "tx-amex-pago-1")
    )
    tx = result.scalar_one()
    assert tx.transaction_type == "transfer"
    assert tx.category is None
    assert tx.transfer_to_account_id == amex.id
    # Mapper stores expenses/transfers negative (USD cents here)
    assert tx.amount == Decimal("-200000")
    # And Task 2.6: settled status
    assert tx.status == "settled"


@pytest.mark.asyncio
async def test_cc_payment_without_last_four_falls_back_to_name_match(db):
    user, hh, checking, amex, item = await _seed_plaid_household(db, amex_mask=None)

    plaid_tx = FakePlaidTx(
        account_id="plaid-checking",
        transaction_id="tx-amex-pago-2",
        amount=150.0,
        date=date.today(),
        name="Online Payment American Express",
        merchant_name="American Express",
        category=["Transfer"],
    )
    response = FakeSyncResponse(
        added=[plaid_tx],
        accounts=[FakePlaidAccount(account_id="plaid-checking")],
    )

    stats = await _run_sync_with_fake(db, item, response)
    assert stats["added"] == 1

    result = await db.execute(
        select(Transaction).where(Transaction.plaid_transaction_id == "tx-amex-pago-2")
    )
    tx = result.scalar_one()
    assert tx.transaction_type == "transfer"
    assert tx.transfer_to_account_id == amex.id
    assert tx.category is None


@pytest.mark.asyncio
async def test_non_cc_expense_not_typed_transfer(db):
    user, hh, checking, amex, item = await _seed_plaid_household(db)

    plaid_tx = FakePlaidTx(
        account_id="plaid-checking",
        transaction_id="tx-starbucks",
        amount=6.75,
        date=date.today(),
        name="STARBUCKS STORE 12345",
        merchant_name="Starbucks",
        category=["Food and Drink", "Restaurants", "Coffee Shop"],
    )
    response = FakeSyncResponse(
        added=[plaid_tx],
        accounts=[FakePlaidAccount(account_id="plaid-checking")],
    )

    stats = await _run_sync_with_fake(db, item, response)
    assert stats["added"] == 1

    result = await db.execute(
        select(Transaction).where(Transaction.plaid_transaction_id == "tx-starbucks")
    )
    tx = result.scalar_one()
    assert tx.transaction_type == "expense"
    assert tx.transfer_to_account_id is None


# ---------------------------------------------------------------- tests — amount helper / modify branch


def test_luka_amount_from_plaid_usd_scales_to_cents():
    tx = FakePlaidTx(
        account_id="x",
        transaction_id="x",
        amount=27.43,
        date=date.today(),
        iso_currency_code="USD",
    )
    assert luka_amount_from_plaid(tx) == -2743


def test_luka_amount_from_plaid_clp_is_integer_units():
    """Modify branch previously multiplied by 100 — would inflate CLP 1.000 to CLP 100.000."""
    tx = FakePlaidTx(
        account_id="x",
        transaction_id="x",
        amount=1000.0,
        date=date.today(),
        iso_currency_code="CLP",
    )
    # CLP: 1000 outflow → stored as -1000 integer units (NOT -100000).
    assert luka_amount_from_plaid(tx) == -1000


def test_luka_amount_from_plaid_income_is_positive():
    tx = FakePlaidTx(
        account_id="x",
        transaction_id="x",
        amount=-50.0,
        date=date.today(),
        iso_currency_code="USD",
    )
    assert luka_amount_from_plaid(tx) == 5000


# ---------------------------------------------------------------- tests — Task 2.6


def test_mapper_writes_canonical_settled_status():
    tx = FakePlaidTx(
        account_id="x",
        transaction_id="x",
        amount=10.0,
        date=date.today(),
        name="Coffee",
        merchant_name="Coffee",
        pending=False,
    )
    mapped = map_plaid_transaction(
        tx,
        bank_account_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        household_id=str(uuid.uuid4()),
    )
    assert mapped["status"] == "settled"


def test_mapper_keeps_pending_status_for_pending_txn():
    tx = FakePlaidTx(
        account_id="x",
        transaction_id="x",
        amount=10.0,
        date=date.today(),
        name="Coffee",
        merchant_name="Coffee",
        pending=True,
    )
    mapped = map_plaid_transaction(
        tx,
        bank_account_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        household_id=str(uuid.uuid4()),
    )
    assert mapped["status"] == "pending"
