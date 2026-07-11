"""Regression tests for the Plaid pending→settled swap (removed path).

The bug: the settled replacement received a default split in the added path
AND inherited the pending txn's split in the removed path — two split rows on
one transaction, double-counted by every JOIN-based money aggregate.

Also pins:
  - pending_transaction_id is preferred as the deterministic replacement link
    (amount can change on settle — tip adjustments).
  - the modified path never reverts a user-renamed merchant.

Real DB, savepoint-rolled-back via the ``db`` fixture in conftest.py. The
Plaid SDK call is monkeypatched — everything below it is real.
"""

from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

from sqlalchemy import select

# Register models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.plaid.models import PlaidItem
from modules.plaid import sync as plaid_sync
from modules.transactions.models import Transaction, TransactionSplit


# ---------------------------------------------------------------- fakes


def _fake_account(account_id: str = "acc-1"):
    return SimpleNamespace(
        account_id=account_id,
        type="depository",
        subtype="checking",
        official_name="Test Checking",
        name="Checking",
        mask="1234",
        balances=SimpleNamespace(iso_currency_code="USD", current=100.0, limit=None),
    )


def _fake_tx(
    txn_id: str,
    amount: float,
    *,
    pending: bool,
    account_id: str = "acc-1",
    name: str = "STARBUCKS STORE 123",
    merchant_name: str | None = "Starbucks",
    pending_transaction_id: str | None = None,
    tx_date: date | None = None,
):
    return SimpleNamespace(
        transaction_id=txn_id,
        account_id=account_id,
        amount=amount,
        iso_currency_code="USD",
        unofficial_currency_code=None,
        name=name,
        merchant_name=merchant_name,
        pending=pending,
        pending_transaction_id=pending_transaction_id,
        date=tx_date or date(2026, 7, 1),
        category=None,
        personal_finance_category=None,
    )


def _fake_response(added=(), modified=(), removed=(), accounts=()):
    return SimpleNamespace(
        added=list(added),
        modified=list(modified),
        removed=list(removed),
        accounts=list(accounts),
        has_more=False,
        next_cursor="cursor-1",
    )


def _patch_sync(monkeypatch, response):
    monkeypatch.setattr(plaid_sync, "sync_transactions", lambda **kw: response)
    monkeypatch.setattr(plaid_sync, "decrypt_token", lambda s: "access-token")


async def _seed_item(db):
    user = User(
        id=uuid.uuid4(),
        email=f"plaid-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Plaid Tester",
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(user)
    await db.flush()
    household = Household(id=uuid.uuid4(), name="Plaid HH", type="couple")
    db.add(household)
    await db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    item = PlaidItem(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        plaid_item_id=f"item-{uuid.uuid4().hex[:8]}",
        access_token_enc="enc",
        institution_id="ins_1",
        institution_name="Test Bank",
    )
    db.add(item)
    await db.flush()
    return user, household, item


async def _splits_for(db, tx_id):
    res = await db.execute(select(TransactionSplit).where(TransactionSplit.transaction_id == tx_id))
    return res.scalars().all()


# ---------------------------------------------------------------- tests


async def test_pending_swap_leaves_exactly_one_split(db, monkeypatch):
    user, household, item = await _seed_item(db)

    # Sync 1: pending transaction arrives.
    _patch_sync(
        monkeypatch,
        _fake_response(
            added=[_fake_tx("plaid-pending-1", 25.00, pending=True)],
            accounts=[_fake_account()],
        ),
    )
    await plaid_sync.run_plaid_sync(db, item.id)

    old_tx = (
        await db.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == "plaid-pending-1")
        )
    ).scalar_one()
    assert len(await _splits_for(db, old_tx.id)) == 1
    # User categorizes + flips the split — enrichment that must survive the swap.
    old_tx.category = "Cafés"
    split = (await _splits_for(db, old_tx.id))[0]
    split.split_type = "shared"
    await db.flush()

    # Sync 2: settled replacement (different amount — tip adjusted) + removal
    # of the pending row, linked via pending_transaction_id.
    _patch_sync(
        monkeypatch,
        _fake_response(
            added=[
                _fake_tx(
                    "plaid-settled-1",
                    28.00,
                    pending=False,
                    pending_transaction_id="plaid-pending-1",
                )
            ],
            removed=[SimpleNamespace(transaction_id="plaid-pending-1")],
            accounts=[_fake_account()],
        ),
    )
    await plaid_sync.run_plaid_sync(db, item.id)

    # Old row gone, replacement present.
    assert (
        await db.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == "plaid-pending-1")
        )
    ).scalar_one_or_none() is None
    replacement = (
        await db.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == "plaid-settled-1")
        )
    ).scalar_one()

    # THE regression: exactly one split row — and it's the user's, not the default.
    splits = await _splits_for(db, replacement.id)
    assert len(splits) == 1
    assert splits[0].split_type == "shared"
    # Enrichment carried despite the amount change (pending_transaction_id link).
    assert replacement.category == "Cafés"
    assert replacement.amount == -2800  # cents, tip-adjusted


async def test_modified_path_preserves_user_renamed_merchant(db, monkeypatch):
    user, household, item = await _seed_item(db)

    _patch_sync(
        monkeypatch,
        _fake_response(
            added=[_fake_tx("plaid-mod-1", 40.00, pending=True)],
            accounts=[_fake_account()],
        ),
    )
    await plaid_sync.run_plaid_sync(db, item.id)

    tx = (
        await db.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == "plaid-mod-1")
        )
    ).scalar_one()
    tx.raw_merchant_name = "Mi Cafetería"
    tx.user_edited_fields = {"merchant_name": True}
    await db.flush()

    # Tip adjustment arrives as a "modified" event.
    _patch_sync(
        monkeypatch,
        _fake_response(
            modified=[_fake_tx("plaid-mod-1", 44.00, pending=False)],
            accounts=[_fake_account()],
        ),
    )
    await plaid_sync.run_plaid_sync(db, item.id)

    await db.refresh(tx)
    assert tx.raw_merchant_name == "Mi Cafetería"  # user edit wins
    assert tx.amount == -4400
    assert tx.status == "settled"
