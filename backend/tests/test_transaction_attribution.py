# backend/tests/test_transaction_attribution.py
"""Partner-card charge attribution — lifecycle, predicate, privacy.
Real DB, savepoint-rollback ``db`` fixture (no mocks, per CLAUDE.md)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

import modules.merchants.models  # noqa: F401
import modules.notifications.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember  # noqa: F401
from modules.transactions.models import (  # noqa: F401
    Transaction,
    TransactionAttribution,
    TransactionSplit,
)


async def _couple(db):
    """Rafael (owner) + Camila (member) in one household; returns (rafael, camila, hh)."""
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


async def _charge(db, owner, hh, amount="-40.00"):
    txn = Transaction(
        id=uuid.uuid4(),
        user_id=owner.id,
        household_id=hh.id,
        raw_merchant_name="Sephora",
        amount=Decimal(amount),
        currency="USD",
        transaction_date=datetime.now(timezone.utc),
        source="plaid",
        source_type="plaid",
        status="settled",
        transaction_type="expense",
    )
    db.add(txn)
    await db.flush()
    return txn


async def test_attribution_row_persists(db):
    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(
        TransactionAttribution(
            transaction_id=txn.id,
            attributed_to_user_id=camila.id,
            attributed_by_user_id=rafael.id,
            status="active",
        )
    )
    await db.flush()
    row = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert row.status == "active"
    assert row.attributed_to_user_id == camila.id


async def test_effective_owner_and_predicate(db):
    from modules.transactions.attribution import attributed_to_clause, effective_owner_id

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    attr = TransactionAttribution(
        transaction_id=txn.id,
        attributed_to_user_id=camila.id,
        attributed_by_user_id=rafael.id,
        status="active",
    )
    db.add(attr)
    await db.flush()

    assert effective_owner_id(rafael.id, attr) == camila.id
    assert effective_owner_id(rafael.id, None) == rafael.id
    attr.status = "rejected"
    assert effective_owner_id(rafael.id, attr) == rafael.id  # rejected → back to owner

    # Predicate: Camila's rows = her own OR active-attributed-to-her.
    attr.status = "active"
    await db.flush()
    rows = (
        (
            await db.execute(
                select(Transaction.id)
                .outerjoin(
                    TransactionAttribution,
                    TransactionAttribution.transaction_id == Transaction.id,
                )
                .where(attributed_to_clause(camila.id))
            )
        )
        .scalars()
        .all()
    )
    assert txn.id in rows


async def test_hand_off_reject_and_re_handoff(db):
    from modules.notifications.models import Notification
    from modules.transactions.attribution import hand_off, reject, resolve_recipient

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()

    assert await resolve_recipient(db, hh.id, rafael.id) == camila.id

    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert attr.status == "active"
    split = (
        await db.execute(select(TransactionSplit).where(TransactionSplit.transaction_id == txn.id))
    ).scalar_one()
    assert split.split_type == "partner"
    notif = (
        await db.execute(select(Notification).where(Notification.type == "charge_attributed"))
    ).scalar_one()
    assert notif.user_id == camila.id

    await reject(db, attr.id, by_user_id=camila.id)
    await db.flush()
    await db.refresh(attr)
    await db.refresh(split)
    assert attr.status == "rejected"
    assert split.split_type == "personal"
    assert (
        await db.execute(select(Notification).where(Notification.type == "attribution_rejected"))
    ).scalar_one().user_id == rafael.id

    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    rows = (
        (
            await db.execute(
                select(TransactionAttribution).where(
                    TransactionAttribution.transaction_id == txn.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].status == "active"


async def test_exactly_one_owner_in_dashboard(db):
    from modules.transactions.attribution import hand_off
    from modules.transactions.service import get_dashboard_summary, get_my_transactions

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh, amount="-40.00")
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r_sum = await get_dashboard_summary(db, rafael.id, month, "USD")
    c_sum = await get_dashboard_summary(db, camila.id, month, "USD")
    assert r_sum["expenses"] == 0, "handed-off charge must leave Rafael's totals"
    assert c_sum["expenses"] != 0, "handed-off charge must count for Camila"

    r_list = await get_my_transactions(db, rafael.id, since=txn.transaction_date.date())
    c_list = await get_my_transactions(db, camila.id, since=txn.transaction_date.date())
    assert any(t["id"] == txn.id for t in r_list), "sender still sees the handed-off row (labeled)"
    assert any(t["id"] == txn.id for t in c_list), "recipient sees the attributed row"


async def test_dashboard_includes_null_split_charge(db):
    """Email-ingested rows have NO TransactionSplit row (split_type IS NULL).
    The exclude-only-partner guard must be NULL-safe so they still count."""
    from modules.transactions.service import get_dashboard_summary

    rafael, _camila, hh = await _couple(db)
    await _charge(db, rafael, hh, amount="-40.00")  # deliberately no split row
    await db.flush()

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r_sum = await get_dashboard_summary(db, rafael.id, month, "USD")
    assert r_sum["expenses"] != 0, "null-split (email-ingested) charge must count in totals"
    assert any(c["amount"] for c in r_sum["categories"]), (
        "null-split charge must appear in categories"
    )


async def test_dashboard_rejected_attribution_reverts_to_owner(db):
    from modules.transactions.attribution import hand_off, reject
    from modules.transactions.service import get_dashboard_summary

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh, amount="-40.00")
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    await reject(db, attr.id, by_user_id=camila.id)
    await db.flush()

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    r_sum = await get_dashboard_summary(db, rafael.id, month, "USD")
    c_sum = await get_dashboard_summary(db, camila.id, month, "USD")
    assert r_sum["expenses"] != 0, "rejected attribution counts for the original owner again"
    assert c_sum["expenses"] == 0, "rejected attribution must not count for the recipient"


async def test_budget_personal_scope(db):
    """Real personal-budget entry point (`_month_category_sums`, view="personal"):
    (i) a charge handed to Camila lands in HER personal spend; (ii) Rafael's own
    shared-split charge never leaks into his personal spend (and his handed-off
    charge has left it), so his personal total is 0."""
    from modules.budgets.v2_queries import _month_category_sums
    from modules.transactions.attribution import hand_off

    rafael, camila, hh = await _couple(db)

    handed = await _charge(db, rafael, hh, amount="-40.00")
    db.add(TransactionSplit(transaction_id=handed.id, split_type="personal"))
    await db.flush()
    await hand_off(db, handed, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()

    shared = await _charge(db, rafael, hh, amount="-25.00")
    db.add(TransactionSplit(transaction_id=shared.id, split_type="shared"))
    await db.flush()

    month = datetime.now(timezone.utc).date().replace(day=1)
    camila_rows = await _month_category_sums(
        db, view="personal", user_id=camila.id, household_id=hh.id, month=month, currency="USD"
    )
    rafael_rows = await _month_category_sums(
        db, view="personal", user_id=rafael.id, household_id=hh.id, month=month, currency="USD"
    )
    assert sum((amt for _, amt in camila_rows), Decimal("0")) == Decimal("40.00"), (
        "handed-off charge must appear in Camila's personal budget spend"
    )
    assert sum((amt for _, amt in rafael_rows), Decimal("0")) == Decimal("0"), (
        "Rafael's own shared charge must NOT leak into personal; handed-off charge left too"
    )


# ---------------------------------------------------------------------------
# Endpoint tests — /transactions/{id}/attribute, /attributions/{id}/...
# Real DB + savepoint `db`; deps overridden per test_trips_router.py pattern.
# ---------------------------------------------------------------------------


def _override(app, user, db):
    from core.database import get_db
    from core.security import get_current_user

    async def _fake_db():
        yield db

    async def _fake_user():
        return user

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _fake_user


async def _notifs(db, user_id, type_):
    from modules.notifications.models import Notification

    return (
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.type == type_
                )
            )
        )
        .scalars()
        .all()
    )


async def test_attribute_endpoint_implicit_recipient(app, db, http_client):
    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    _override(app, rafael, db)

    r = await http_client.post(f"/transactions/{txn.id}/attribute", json={})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "recipient_id": str(camila.id)}

    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()
    assert attr.status == "active"
    assert attr.attributed_to_user_id == camila.id
    assert len(await _notifs(db, camila.id, "charge_attributed")) == 1


async def test_attribute_endpoint_redundant_no_second_notification(app, db, http_client):
    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    _override(app, rafael, db)

    r1 = await http_client.post(f"/transactions/{txn.id}/attribute", json={})
    assert r1.status_code == 200
    r2 = await http_client.post(
        f"/transactions/{txn.id}/attribute", json={"recipient_id": str(camila.id)}
    )
    assert r2.status_code == 200
    # Dedup: still exactly one charge_attributed notification.
    assert len(await _notifs(db, camila.id, "charge_attributed")) == 1


async def test_reject_endpoint_by_recipient(app, db, http_client):
    from modules.transactions.attribution import hand_off

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()

    _override(app, camila, db)
    r = await http_client.post(f"/transactions/attributions/{attr.id}/reject")
    assert r.status_code == 200, r.text

    await db.refresh(attr)
    assert attr.status == "rejected"
    split = (
        await db.execute(select(TransactionSplit).where(TransactionSplit.transaction_id == txn.id))
    ).scalar_one()
    assert split.split_type == "personal"
    assert len(await _notifs(db, rafael.id, "attribution_rejected")) == 1


async def test_reject_endpoint_forbidden_and_not_found(app, db, http_client):
    from modules.transactions.attribution import hand_off

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()

    # Rafael is NOT the recipient → 403.
    _override(app, rafael, db)
    r = await http_client.post(f"/transactions/attributions/{attr.id}/reject")
    assert r.status_code == 403

    # Unknown attribution id → 404.
    _override(app, camila, db)
    r = await http_client.post(f"/transactions/attributions/{uuid.uuid4()}/reject")
    assert r.status_code == 404


async def test_acknowledge_endpoint(app, db, http_client):
    from modules.transactions.attribution import hand_off

    rafael, camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    db.add(TransactionSplit(transaction_id=txn.id, split_type="personal"))
    await db.flush()
    await hand_off(db, txn, sender_id=rafael.id, recipient_id=camila.id)
    await db.flush()
    attr = (
        await db.execute(
            select(TransactionAttribution).where(TransactionAttribution.transaction_id == txn.id)
        )
    ).scalar_one()

    # Non-recipient → 403.
    _override(app, rafael, db)
    r = await http_client.post(f"/transactions/attributions/{attr.id}/acknowledge")
    assert r.status_code == 403

    # Recipient → 200, acknowledged_at set.
    _override(app, camila, db)
    r = await http_client.post(f"/transactions/attributions/{attr.id}/acknowledge")
    assert r.status_code == 200, r.text
    await db.refresh(attr)
    assert attr.acknowledged_at is not None


async def test_attribute_endpoint_explicit_recipient_not_member(app, db, http_client):
    rafael, _camila, hh = await _couple(db)
    txn = await _charge(db, rafael, hh)
    await db.flush()
    _override(app, rafael, db)

    r = await http_client.post(
        f"/transactions/{txn.id}/attribute", json={"recipient_id": str(uuid.uuid4())}
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "recipient_not_in_household"


async def test_attribute_endpoint_ambiguous(app, db, http_client):
    rafael, camila, hh = await _couple(db)
    # Third active member → ambiguous when no recipient is named.
    third = User(
        id=uuid.uuid4(),
        email=f"tomas-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Tomas",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="USD",
    )
    db.add(third)
    await db.flush()
    db.add(HouseholdMember(household_id=hh.id, user_id=third.id, role="member"))
    txn = await _charge(db, rafael, hh)
    await db.flush()
    _override(app, rafael, db)

    r = await http_client.post(f"/transactions/{txn.id}/attribute", json={})
    assert r.status_code == 409
    body = r.json()
    assert body["detail"] == "ambiguous_recipient"
    assert set(body["candidates"]) == {str(camila.id), str(third.id)}
