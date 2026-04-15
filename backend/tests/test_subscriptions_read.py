"""Unit tests for `modules.subscriptions.read`.

We monkey-patch `get_detected_subscriptions` so the test doesn't depend on
live subscription-detection or Redis — we only care that the household
helper correctly sums across active members for the requested currency.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.auth.models import User
from modules.households.models import Household, HouseholdMember
from modules.subscriptions import read as sub_read


@pytest.mark.asyncio
async def test_get_household_known_bills_sums_across_members(db, monkeypatch):
    """HOGAR FIXED has 2 active members — helper should call the underlying
    subscription detector once per member and sum the per-currency totals."""

    # Resolve the household (seeded by Task 0).
    h_row = await db.execute(select(Household).where(Household.name == "HOGAR FIXED"))
    household = h_row.scalar_one()

    member_rows = await db.execute(
        select(User.id, User.email)
        .join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(
            HouseholdMember.household_id == household.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    members = list(member_rows)
    assert len(members) >= 2, "HOGAR FIXED seed should have ≥2 active members"

    # Map user_id -> canned monthly totals (CLP and USD).
    # `get_household_known_bills` now reads `payload["items"]` filtered to
    # split_type='shared', so the canned data must include an `items` list.
    # We also keep `summary_by_currency` so the `get_user_known_bills` path
    # (which still reads that key) continues to work in the second test.
    canned: dict[str, dict] = {}
    for idx, (user_id, _email) in enumerate(members):
        clp_amount = Decimal(str((idx + 1) * 100_000))
        usd_amount = Decimal(str((idx + 1) * 50))
        canned[str(user_id)] = {
            "items": [
                {
                    "merchant_name": f"BillCLP-member{idx}",
                    "status": "active",
                    "currency": "CLP",
                    "split_type": "shared",
                    "last_amount": clp_amount,
                },
                {
                    "merchant_name": f"BillUSD-member{idx}",
                    "status": "active",
                    "currency": "USD",
                    "split_type": "shared",
                    "last_amount": usd_amount,
                },
            ],
            "summary_by_currency": {
                "CLP": {"total_recurring": clp_amount},
                "USD": {"total_recurring": usd_amount},
            },
        }

    async def _fake_detected(db_, user_id, months_back: int = 6):
        return canned[str(user_id)]

    monkeypatch.setattr(sub_read, "get_detected_subscriptions", _fake_detected)

    # Expected CLP = sum(100_000 * i for i in 1..n)
    expected_clp = sum(Decimal(str((i + 1) * 100_000)) for i in range(len(members)))
    expected_usd = sum(Decimal(str((i + 1) * 50)) for i in range(len(members)))

    clp_total = await sub_read.get_household_known_bills(db, household.id, "CLP")
    usd_total = await sub_read.get_household_known_bills(db, household.id, "USD")

    assert clp_total == expected_clp
    assert usd_total == expected_usd


@pytest.mark.asyncio
async def test_get_user_known_bills_returns_zero_on_missing_currency(db, monkeypatch):
    """Currency not present in summary_by_currency -> Decimal('0')."""

    u_row = await db.execute(select(User).where(User.email == "rafa-full@luka.test"))
    user = u_row.scalar_one()

    async def _fake(db_, user_id, months_back: int = 6):
        return {"summary_by_currency": {"CLP": {"total_recurring": Decimal("42000")}}}

    monkeypatch.setattr(sub_read, "get_detected_subscriptions", _fake)

    clp = await sub_read.get_user_known_bills(db, user.id, "CLP")
    usd = await sub_read.get_user_known_bills(db, user.id, "USD")
    assert clp == Decimal("42000")
    assert usd == Decimal("0")
