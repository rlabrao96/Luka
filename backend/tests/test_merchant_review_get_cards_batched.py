"""Baseline tests for `get_review_cards` ahead of N+1 elimination.

The shape test pins the response contract. The query-count test asserts
that `get_review_cards` runs at most 4 SQL statements — it WILL FAIL on
the current implementation (which fires several queries per canonical),
and will start passing after the Task 5 batched refactor.

Uses the `db` savepoint fixture from conftest.py — all rows roll back.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event

# Register every model so Base.metadata resolves all FKs at flush time.
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.merchant_review.service import get_review_cards
from modules.merchants.models import Merchant
from modules.transactions.models import Transaction


# ---------------------------------------------------------------- helpers


async def _seed_user_and_account(db, *, currency: str = "CLP"):
    user = User(
        id=uuid.uuid4(),
        email=f"review-{uuid.uuid4().hex[:8]}@luka.test",
        full_name="Review Test",
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency=currency,
    )
    db.add(user)
    await db.flush()

    household = Household(id=uuid.uuid4(), name="Review HH", type="individual")
    db.add(household)
    await db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await db.flush()

    account = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name="Banco Test",
        account_type="personal",
        currency=currency,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return user, household, account


async def _seed_canonical_with_txs(
    db,
    *,
    user: User,
    household: Household,
    account: BankAccount,
    display_name: str,
    raw_names: list[str],
    txs_per_raw: int = 1,
    currency: str = "CLP",
    review_job_id: uuid.UUID | None = None,
    llm_suggested: list | None = None,
) -> tuple[CanonicalMerchant, list[Transaction]]:
    """Create a canonical merchant, link `Merchant` rows, and seed transactions."""
    canonical = CanonicalMerchant(
        id=uuid.uuid4(),
        display_name=display_name,
        default_category="Comida",
        is_verified=False,
        review_job_id=review_job_id,
    )
    db.add(canonical)
    await db.flush()

    txs: list[Transaction] = []
    for raw_name in raw_names:
        merchant = Merchant(
            id=uuid.uuid4(),
            raw_name=raw_name,
            normalized_name=raw_name.lower(),
            llm_suggested_categories=llm_suggested or ["Comida", "Restaurantes"],
            canonical_merchant_id=canonical.id,
        )
        db.add(merchant)
        await db.flush()

        base_when = datetime.now(timezone.utc) - timedelta(days=2)
        for i in range(txs_per_raw):
            tx = Transaction(
                id=uuid.uuid4(),
                user_id=user.id,
                household_id=household.id,
                bank_account_id=account.id,
                raw_merchant_name=raw_name,
                amount=Decimal("-1234.56"),
                currency=currency,
                transaction_date=base_when - timedelta(hours=i),
                source="gmail",
                source_type="email",
                status="settled",
                transaction_type="expense",
            )
            db.add(tx)
            txs.append(tx)
    await db.flush()
    return canonical, txs


async def _seed_review_job(
    db, *, user: User, transaction_ids: list[uuid.UUID]
) -> MerchantReviewJob:
    job = MerchantReviewJob(
        id=uuid.uuid4(),
        user_id=user.id,
        status="processing",
        total_merchants=len(transaction_ids),
        reviewed_count=0,
        transaction_ids=[str(tid) for tid in transaction_ids],
    )
    db.add(job)
    await db.flush()
    return job


# ---------------------------------------------------------------- shape test


@pytest.mark.asyncio
async def test_get_review_cards_returns_expected_shape(db):
    user, hh, acc = await _seed_user_and_account(db, currency="CLP")

    all_tx_ids: list[uuid.UUID] = []
    suffix = uuid.uuid4().hex[:6]
    canonicals_data = [
        (f"Lider {suffix}", [f"LIDER PROVIDENCIA {suffix}", f"LIDER LAS CONDES {suffix}"], 2),
        (f"Netflix {suffix}", [f"NETFLIX.COM {suffix}"], 1),
        (f"Uber {suffix}", [f"UBER TRIP {suffix}", f"UBER EATS {suffix}"], 3),
    ]
    for display_name, raw_names, n in canonicals_data:
        _, txs = await _seed_canonical_with_txs(
            db,
            user=user,
            household=hh,
            account=acc,
            display_name=display_name,
            raw_names=raw_names,
            txs_per_raw=n,
            currency="CLP",
        )
        all_tx_ids.extend(t.id for t in txs)

    job = await _seed_review_job(db, user=user, transaction_ids=all_tx_ids)

    cards = await get_review_cards(db, job.id, user.id)

    assert len(cards) == 3
    expected_keys = {
        "canonical_merchant_id",
        "display_name",
        "default_category",
        "llm_suggested_categories",
        "transactions",
        "transaction_count",
        "total_amount",
        "currency",
        "is_verified",
    }
    valid_currencies = {"CLP", "USD", "COP", "MXN", "PEN", "BRL"}
    for c in cards:
        assert expected_keys <= c.keys()
        assert c["currency"] in valid_currencies
        assert c["is_verified"] is False
        assert isinstance(c["transactions"], list)

    # Totals match sum of transactions when count fits within the cap (25).
    for c in cards:
        if c["transaction_count"] == len(c["transactions"]):
            assert c["total_amount"] == pytest.approx(sum(t["amount"] for t in c["transactions"]))

    # Deterministic spot check by display_name.
    by_name = {c["display_name"]: c for c in cards}
    assert set(by_name.keys()) == {
        f"Lider {suffix}",
        f"Netflix {suffix}",
        f"Uber {suffix}",
    }
    assert by_name[f"Netflix {suffix}"]["transaction_count"] == 1
    assert by_name[f"Lider {suffix}"]["transaction_count"] == 4  # 2 raw × 2 txs
    assert by_name[f"Uber {suffix}"]["transaction_count"] == 6  # 2 raw × 3 txs


# ---------------------------------------------------------------- query-count test


@pytest.mark.asyncio
async def test_get_review_cards_uses_at_most_4_queries(db):
    user, hh, acc = await _seed_user_and_account(db, currency="CLP")

    all_tx_ids: list[uuid.UUID] = []
    for i in range(10):
        _, txs = await _seed_canonical_with_txs(
            db,
            user=user,
            household=hh,
            account=acc,
            display_name=f"Merchant {i:02d} {uuid.uuid4().hex[:6]}",
            raw_names=[f"RAW {i:02d} {uuid.uuid4().hex[:6]}"],
            txs_per_raw=1,
            currency="CLP",
        )
        all_tx_ids.extend(t.id for t in txs)

    job = await _seed_review_job(db, user=user, transaction_ids=all_tx_ids)

    bind = db.get_bind()
    # AsyncSession.get_bind() returns the underlying sync Connection (the
    # AsyncConnection wraps it). Attach the listener directly to that target.
    sync_target = (
        getattr(bind, "sync_connection", None) or getattr(bind, "sync_engine", None) or bind
    )

    queries: list[str] = []

    def collect(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(sync_target, "before_cursor_execute", collect)
    try:
        cards = await get_review_cards(db, job.id, user.id)
    finally:
        event.remove(sync_target, "before_cursor_execute", collect)

    assert len(cards) == 10
    assert len(queries) <= 4, f"Expected <=4 queries, got {len(queries)}:\n" + "\n---\n".join(
        queries
    )
