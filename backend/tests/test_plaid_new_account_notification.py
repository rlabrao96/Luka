"""ensure_plaid_accounts must notify when a NEW account appears on an
already-connected Plaid item — e.g. a spouse's authorized-user Amex opened
AFTER the initial connection — so its spending isn't silently attributed to
the owner. The initial connection (item had zero accounts) must NOT notify.

Real database, savepoint-rollback ``db`` fixture (per CLAUDE.md, no mocks).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import select

# Register every model so Base.metadata resolves each FK on flush.
import modules.merchants.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.notifications.models import Notification
from modules.plaid.models import PlaidItem
from modules.plaid.sync import ensure_plaid_accounts


def _fake_plaid_account(account_id: str, *, name: str, subtype: str, mask: str):
    """Minimal duck-typed stand-in for a Plaid Account object."""
    return SimpleNamespace(
        account_id=account_id,
        type="credit" if subtype == "credit card" else "depository",
        subtype=subtype,
        name=name,
        official_name=name,
        mask=mask,
        balances=SimpleNamespace(current=100.0, limit=1000.0, iso_currency_code="USD"),
    )


async def _seed_item(db) -> tuple[User, Household, PlaidItem]:
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

    household = Household(id=uuid.uuid4(), name="HH", type="couple")
    db.add(household)
    await db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))

    item = PlaidItem(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        plaid_item_id=f"item-{uuid.uuid4().hex[:8]}",
        access_token_enc="enc",
        institution_id="ins_amex",
        institution_name="American Express",
    )
    db.add(item)
    await db.flush()
    return user, household, item


async def _notifications_for(db, user_id) -> list[Notification]:
    rows = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "new_account_detected",
        )
    )
    return list(rows.scalars().all())


async def test_initial_connection_does_not_notify(db):
    """First sync (item has zero accounts) — the accounts that appear are the
    expected setup, so NO new-account notification should fire."""
    user, _household, item = await _seed_item(db)

    accounts = [
        _fake_plaid_account("acc-primary", name="Platinum", subtype="credit card", mask="1001"),
        _fake_plaid_account("acc-checking", name="Checking", subtype="checking", mask="2002"),
    ]
    await ensure_plaid_accounts(db, item, accounts)
    await db.flush()

    assert await _notifications_for(db, user.id) == [], (
        "initial connection must not raise new-account notifications"
    )


async def test_new_card_after_connection_notifies(db):
    """Second sync surfaces an additional card that wasn't there before — it
    MUST raise exactly one notification carrying the new account's id."""
    user, _household, item = await _seed_item(db)

    # Initial connection: one card.
    await ensure_plaid_accounts(
        db,
        item,
        [_fake_plaid_account("acc-primary", name="Platinum", subtype="credit card", mask="1001")],
    )
    await db.flush()
    assert await _notifications_for(db, user.id) == []

    # Later sync: the same card PLUS a new authorized-user card.
    await ensure_plaid_accounts(
        db,
        item,
        [
            _fake_plaid_account("acc-primary", name="Platinum", subtype="credit card", mask="1001"),
            _fake_plaid_account("acc-added", name="Platinum", subtype="credit card", mask="4012"),
        ],
    )
    await db.flush()

    notifs = await _notifications_for(db, user.id)
    assert len(notifs) == 1, f"expected exactly 1 new-account notification, got {len(notifs)}"

    # Payload must point at the newly created account (the ••4012 card).
    new_ba = (
        await db.execute(select(BankAccount).where(BankAccount.account_number == "4012"))
    ).scalar_one()
    assert notifs[0].payload["account_id"] == str(new_ba.id)
    assert notifs[0].payload["household_id"] == str(item.household_id)
    assert new_ba.account_type == "personal", "new card defaults personal until user classifies it"
