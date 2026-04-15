"""Tests for subscription split_type classification and cascade behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select, text

# Register all models so Base.metadata resolves FKs across modules.
import modules.households.models  # noqa: F401
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.subscriptions.schemas import SubscriptionOverrideRequest
from modules.subscriptions.service import reclassify_subscription_split, upsert_override
from modules.transactions.models import Transaction, TransactionSplit


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


async def _get_seed_household_id(db, user_id) -> str:
    res = await db.execute(
        text(
            "SELECT household_id FROM household_members "
            "WHERE user_id = :uid AND left_at IS NULL LIMIT 1"
        ),
        {"uid": str(user_id)},
    )
    hid = res.scalar_one_or_none()
    assert hid is not None, f"seed user {user_id} has no active household"
    return hid


class TestReclassifySubscriptionSplit:
    @pytest.mark.asyncio
    async def test_cascade_updates_last_3_months_only(self, db):
        """5 months of Netflix txns; reclassify; verify only last 3 months'
        transaction_splits are updated."""
        user = await _get_seed_user(db)
        user_id = user.id
        household_id = await _get_seed_household_id(db, user_id)
        now = datetime.now(timezone.utc)
        merchant_key = "Netflix-cascade-3mo"

        # Create 5 transactions spaced 31 days apart so month-index 3 (93 days ago)
        # and month-index 4 (124 days ago) fall clearly outside the 3-month window
        # (3 calendar months before Apr 15 = Jan 15; 93 days ago = Jan 12 < Jan 15).
        tx_ids = []
        for months_ago in range(5):
            tx = Transaction(
                user_id=user_id,
                household_id=household_id,
                raw_merchant_name=merchant_key,
                amount=Decimal("-9.99"),
                currency="USD",
                transaction_date=now - timedelta(days=31 * months_ago),
                source="email",
                transaction_type="expense",
                category="Entretenimiento",
            )
            db.add(tx)
            await db.flush()
            split = TransactionSplit(
                transaction_id=tx.id,
                split_type="personal",
                decided_by_user_id=user_id,
            )
            db.add(split)
            tx_ids.append(tx.id)
        await db.commit()

        # Act: reclassify merchant to 'shared'
        updated_count = await reclassify_subscription_split(
            db,
            user_id=user_id,
            merchant_key=merchant_key,
            new_split_type="shared",
            window_months=3,
        )

        # Assert: only the 3 most recent txns got their split updated
        assert updated_count == 3
        for i, tx_id in enumerate(tx_ids):
            row = await db.execute(
                text("SELECT split_type FROM transaction_splits WHERE transaction_id = :tid"),
                {"tid": str(tx_id)},
            )
            split_type = row.scalar()
            if i < 3:
                assert split_type == "shared", f"tx at month {i} should be shared"
            else:
                assert split_type == "personal", f"tx at month {i} should still be personal"

    @pytest.mark.asyncio
    async def test_cascade_inserts_missing_splits(self, db):
        """Txns with no existing transaction_splits row get one inserted."""
        user = await _get_seed_user(db)
        user_id = user.id
        household_id = await _get_seed_household_id(db, user_id)
        now = datetime.now(timezone.utc)
        merchant_key = "Spotify-cascade-insert"

        tx = Transaction(
            user_id=user_id,
            household_id=household_id,
            raw_merchant_name=merchant_key,
            amount=Decimal("-7.55"),
            currency="USD",
            transaction_date=now - timedelta(days=10),
            source="email",
            transaction_type="expense",
            category="Entretenimiento",
        )
        db.add(tx)
        await db.commit()
        # No TransactionSplit row for this transaction

        count = await reclassify_subscription_split(
            db,
            user_id=user_id,
            merchant_key=merchant_key,
            new_split_type="shared",
            window_months=3,
        )
        assert count == 1

        row = await db.execute(
            text(
                "SELECT split_type, decided_by_user_id FROM transaction_splits "
                "WHERE transaction_id = :tid"
            ),
            {"tid": str(tx.id)},
        )
        got = row.one()
        assert got.split_type == "shared"
        assert str(got.decided_by_user_id) == str(user_id)

    @pytest.mark.asyncio
    async def test_cascade_persists_override_row(self, db):
        user = await _get_seed_user(db)
        user_id = user.id
        merchant_key = "Netflix-cascade-override"

        await reclassify_subscription_split(
            db,
            user_id=user_id,
            merchant_key=merchant_key,
            new_split_type="shared",
            window_months=3,
        )
        row = await db.execute(
            text(
                "SELECT split_type FROM subscription_overrides "
                "WHERE user_id = :uid AND merchant_key = :mk"
            ),
            {"uid": str(user_id), "mk": merchant_key},
        )
        assert row.scalar() == "shared"

    @pytest.mark.asyncio
    async def test_cascade_invalidates_cache(self, db):
        user = await _get_seed_user(db)
        user_id = user.id
        merchant_key = "Netflix-cascade-cache"

        # Prime the cache with an arbitrary result
        await db.execute(
            text("""
                INSERT INTO detected_subscriptions_cache (user_id, result_json, computed_at)
                VALUES (:uid, CAST('[]' AS jsonb), NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET result_json = CAST('[]' AS jsonb), computed_at = NOW()
            """),
            {"uid": str(user_id)},
        )
        await db.commit()

        await reclassify_subscription_split(
            db,
            user_id=user_id,
            merchant_key=merchant_key,
            new_split_type="shared",
            window_months=3,
        )
        row = await db.execute(
            text("SELECT COUNT(*) FROM detected_subscriptions_cache WHERE user_id = :uid"),
            {"uid": str(user_id)},
        )
        assert row.scalar() == 0  # cache row deleted

    @pytest.mark.asyncio
    async def test_rejects_invalid_split_type(self, db):
        user = await _get_seed_user(db)
        merchant_key = "Netflix-cascade-invalid"

        with pytest.raises(ValueError):
            await reclassify_subscription_split(
                db,
                user_id=user.id,
                merchant_key=merchant_key,
                new_split_type="bogus",
                window_months=3,
            )
