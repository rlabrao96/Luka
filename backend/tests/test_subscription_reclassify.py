"""Tests for subscription split_type classification and cascade behavior."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from modules.auth.models import User
from modules.subscriptions.schemas import SubscriptionOverrideRequest
from modules.subscriptions.service import upsert_override


class TestSubscriptionOverrideRequestSchema:
    def test_accepts_optional_split_type_shared(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="shared")
        assert req.split_type == "shared"

    def test_accepts_optional_split_type_personal(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix", split_type="personal")
        assert req.split_type == "personal"

    def test_split_type_defaults_to_none(self):
        req = SubscriptionOverrideRequest(merchant_key="netflix")
        assert req.split_type is None

    def test_rejects_invalid_split_type(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SubscriptionOverrideRequest(merchant_key="netflix", split_type="partner")


async def _get_seed_user(db) -> User:
    res = await db.execute(select(User).where(User.email == "rafa-full@luka.test"))
    u = res.scalar_one_or_none()
    assert u is not None, "seed missing: rafa-full@luka.test"
    return u


class TestUpsertOverrideSplitType:
    @pytest.mark.asyncio
    async def test_upsert_persists_split_type(self, db):
        user = await _get_seed_user(db)
        await upsert_override(
            db,
            user_id=user.id,
            merchant_key="netflix-test-split",
            status=None,
            category=None,
            next_charge_day=None,
            split_type="shared",
        )
        row = await db.execute(
            text(
                "SELECT split_type FROM subscription_overrides "
                "WHERE user_id = :uid AND merchant_key = 'netflix-test-split'"
            ),
            {"uid": str(user.id)},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_upsert_update_changes_split_type(self, db):
        user = await _get_seed_user(db)
        await upsert_override(
            db,
            user_id=user.id,
            merchant_key="netflix-test-update",
            status=None,
            category=None,
            next_charge_day=None,
            split_type="personal",
        )
        await upsert_override(
            db,
            user_id=user.id,
            merchant_key="netflix-test-update",
            status=None,
            category=None,
            next_charge_day=None,
            split_type="shared",
        )
        row = await db.execute(
            text(
                "SELECT split_type FROM subscription_overrides "
                "WHERE user_id = :uid AND merchant_key = 'netflix-test-update'"
            ),
            {"uid": str(user.id)},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_upsert_without_split_type_leaves_existing(self, db):
        user = await _get_seed_user(db)
        await upsert_override(
            db,
            user_id=user.id,
            merchant_key="netflix-test-preserve",
            status=None,
            category=None,
            next_charge_day=None,
            split_type="shared",
        )
        await upsert_override(
            db,
            user_id=user.id,
            merchant_key="netflix-test-preserve",
            status="active",
            category="Entretenimiento",
            next_charge_day=None,
            split_type=None,
        )
        row = await db.execute(
            text(
                "SELECT split_type, status, category FROM subscription_overrides "
                "WHERE user_id = :uid AND merchant_key = 'netflix-test-preserve'"
            ),
            {"uid": str(user.id)},
        )
        got = row.one()
        assert got.split_type == "shared"  # preserved, NOT overwritten to NULL
        assert got.status == "active"
        assert got.category == "Entretenimiento"
