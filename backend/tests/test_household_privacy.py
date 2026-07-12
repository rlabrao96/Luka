import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

# Register models for FK resolution.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.households.service import get_contribution_summary, get_member_stats
from modules.transactions.models import Transaction, TransactionSplit


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_contribution_summary_returns_both_users(db, mock_user, mock_partner, mock_household):
    summary = await get_contribution_summary(db, household_id=mock_household.id)
    assert len(summary) == 2
    user_ids = {row["user_id"] for row in summary}
    assert mock_user.id in user_ids
    assert mock_partner.id in user_ids


@pytest.mark.skip(reason="Requires live Supabase DATABASE_URL")
@pytest.mark.asyncio
async def test_member_stats_returns_only_aggregates(db, mock_user, mock_partner, mock_household):
    stats = await get_member_stats(db, household_id=mock_household.id, requester_id=mock_user.id)
    assert isinstance(stats, list)
    # Must return list of members with aggregate data, not individual transaction rows
    for member in stats:
        assert "user_id" in member
        assert "full_name" in member
        assert "total_spent" in member


# ---------------------------------------------------------------------------
# Regression: get_contribution_summary must NOT leak a member's personal or
# total spending — only shared_paid is the legitimately-shared number.
# ---------------------------------------------------------------------------


async def _member(db, household, name):
    u = User(
        id=_uuid.uuid4(),
        email=f"{name}-{_uuid.uuid4().hex[:6]}@luka.test",
        full_name=name,
        email_provider="gmail",
        whatsapp_verified=False,
    )
    db.add(u)
    await db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=u.id, role="member"))
    await db.flush()
    return u


async def _expense(db, user, household, amount, split_type):
    tx = Transaction(
        id=_uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        raw_merchant_name="X",
        amount=Decimal(amount),
        currency="CLP",
        transaction_date=datetime.now(timezone.utc),
        source="connect",
        source_type="connect",
        status="settled",
        transaction_type="expense",
    )
    db.add(tx)
    await db.flush()
    db.add(TransactionSplit(transaction_id=tx.id, split_type=split_type))
    await db.flush()


async def test_contribution_summary_never_leaks_personal_spending(db):
    h = Household(id=_uuid.uuid4(), name="Priv HH", type="couple")
    db.add(h)
    await db.flush()
    a = await _member(db, h, "Ana")
    b = await _member(db, h, "Beto")

    # Beto has BIG personal spending nobody else should see, plus small shared.
    await _expense(db, b, h, "-900000", "personal")
    await _expense(db, b, h, "-50000", "shared")
    await _expense(db, a, h, "-30000", "shared")

    summary = await get_contribution_summary(db, h.id, currency="CLP")
    by_user = {r["user_id"]: r for r in summary}

    # Only shared_paid is exposed — no personal/total keys at all.
    for row in summary:
        assert set(row.keys()) == {"user_id", "full_name", "email", "shared_paid"}
        assert "personal_paid" not in row
        assert "total_paid" not in row

    # Beto's 900k personal spend must not surface anywhere.
    assert by_user[b.id]["shared_paid"] == Decimal("50000")
    assert by_user[a.id]["shared_paid"] == Decimal("30000")
    for row in summary:
        assert Decimal(row["shared_paid"]) != Decimal("900000")
        assert Decimal(row["shared_paid"]) != Decimal("950000")


async def test_member_stats_excludes_personal_spending(db):
    h = Household(id=_uuid.uuid4(), name="MS HH", type="couple")
    db.add(h)
    await db.flush()
    viewer = await _member(db, h, "Viewer")
    other = await _member(db, h, "Other")

    # Other member: big personal spend + small shared. Viewer must only see shared.
    await _expense(db, other, h, "-700000", "personal")
    await _expense(db, other, h, "-40000", "shared")

    stats = await get_member_stats(db, h.id, requester_id=viewer.id)
    by_user = {r["user_id"]: r for r in stats}
    assert other.id in by_user
    assert viewer.id not in by_user  # viewer excluded by design
    assert by_user[other.id]["total_spent"] == Decimal("40000")
    assert by_user[other.id]["total_spent"] != Decimal("740000")
