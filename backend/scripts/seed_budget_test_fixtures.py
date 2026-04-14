"""Seed idempotent budget-v2 test fixtures.

Creates 4 test households scoped to @luka.test emails:
- HOGAR FULL       — both members contribution_mode='full'
- HOGAR FIXED      — partner 'fixed' at 800k CLP, plus USD txns for mixed-currency
- HOGAR REIMB      — partner 'reimbursement'
- HOGAR SOLO       — single-user household

Each household gets 3 months of CLP transactions across several categories.
HOGAR FULL also gets an active cuota_purchase (12×50k, started 2 months ago).

Re-runnable — all inserts are gated by existence checks.

Usage (from repo root):
    python backend/scripts/seed_budget_test_fixtures.py
"""

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.database import AsyncSessionLocal

# Register all dependent tables in Base.metadata so FK resolution succeeds.
import modules.auth.models  # noqa: F401
import modules.households.models  # noqa: F401
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
import modules.budgets.cuota_models  # noqa: F401
import modules.budgets.user_budget_settings_models  # noqa: F401

from modules.auth.models import User
from modules.budgets.cuota_models import CuotaPurchase
from modules.households.models import BankAccount, Household, HouseholdMember
from modules.transactions.models import Transaction

CLP_CATEGORIES = [
    ("Restaurantes", 18_500),
    ("Supermercado", 42_300),
    ("Transporte", 12_000),
    ("Vivienda", 350_000),
    ("Servicios", 28_700),
    ("Streaming", 9_900),
    ("Inversión", 80_000),
]
USD_CATEGORIES = [
    ("Streaming", Decimal("12.99")),
    ("Restaurantes", Decimal("34.50")),
]


async def _get_or_create_user(db, email: str, full_name: str) -> User:
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if user:
        return user
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=full_name,
        email_provider="gmail",
        whatsapp_verified=False,
        preferred_currency="CLP",
    )
    db.add(user)
    await db.flush()
    return user


async def _get_or_create_household(db, name: str, htype: str) -> Household:
    res = await db.execute(select(Household).where(Household.name == name))
    h = res.scalar_one_or_none()
    if h:
        return h
    h = Household(id=uuid.uuid4(), name=name, type=htype)
    db.add(h)
    await db.flush()
    return h


async def _ensure_member(
    db,
    household: Household,
    user: User,
    role: str,
    mode: str = "full",
    fixed_amount: Decimal | None = None,
    fixed_currency: str | None = None,
) -> HouseholdMember:
    res = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household.id,
            HouseholdMember.user_id == user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        # Ensure contribution_mode fields reflect desired state (idempotent update).
        existing.contribution_mode = mode
        existing.fixed_contribution_amount = fixed_amount
        existing.fixed_contribution_currency = fixed_currency
        return existing
    member = HouseholdMember(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        role=role,
        contribution_mode=mode,
        fixed_contribution_amount=fixed_amount,
        fixed_contribution_currency=fixed_currency,
    )
    db.add(member)
    await db.flush()
    return member


async def _ensure_bank_account(
    db, household: Household, user: User, bank_name: str, currency: str = "CLP"
) -> BankAccount:
    res = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household.id,
            BankAccount.user_id == user.id,
            BankAccount.bank_name == bank_name,
            BankAccount.currency == currency,
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    acct = BankAccount(
        id=uuid.uuid4(),
        household_id=household.id,
        user_id=user.id,
        bank_name=bank_name,
        account_type="personal",
        account_kind="checking_account",
        currency=currency,
        provider="luka_connect",
        country="CL",
        is_active=True,
    )
    db.add(acct)
    await db.flush()
    return acct


async def _seed_transactions(
    db,
    user: User,
    household: Household,
    bank_account: BankAccount,
    categories,
    months_back: int = 3,
    currency: str = "CLP",
) -> int:
    """Seed N months of transactions for the given user/household. Idempotent by
    (user_id, household_id, raw_merchant_name, transaction_date, amount, currency)."""
    created = 0
    today = datetime.now(timezone.utc)
    for m in range(months_back):
        txn_date = (today - timedelta(days=30 * m)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        for merchant, amount in categories:
            amt = Decimal(str(amount))
            res = await db.execute(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.household_id == household.id,
                    Transaction.raw_merchant_name == merchant,
                    Transaction.transaction_date == txn_date,
                    Transaction.amount == amt,
                    Transaction.currency == currency,
                )
            )
            if res.scalar_one_or_none():
                continue
            db.add(
                Transaction(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    household_id=household.id,
                    bank_account_id=bank_account.id,
                    raw_merchant_name=merchant,
                    amount=amt,
                    currency=currency,
                    transaction_date=txn_date,
                    category=merchant,
                    source="manual",
                    source_type="manual",
                    status="settled",
                    transaction_type="expense",
                )
            )
            created += 1
    await db.flush()
    return created


async def _ensure_cuota(
    db, user: User, household: Household, merchant: str, monthly: Decimal, total_installments: int
) -> CuotaPurchase:
    res = await db.execute(
        select(CuotaPurchase).where(
            CuotaPurchase.user_id == user.id,
            CuotaPurchase.household_id == household.id,
            CuotaPurchase.merchant_name == merchant,
        )
    )
    existing = res.scalar_one_or_none()
    if existing:
        return existing
    # Spec: first_cuota_date = today - 2 calendar months, snapped to day=1.
    today_day1 = date.today().replace(day=1)
    # Subtract exactly 2 calendar months.
    year = today_day1.year
    month = today_day1.month - 2
    if month <= 0:
        month += 12
        year -= 1
    first = today_day1.replace(year=year, month=month)
    last = first
    for _ in range(total_installments - 1):
        y = last.year + (1 if last.month == 12 else 0)
        m = 1 if last.month == 12 else last.month + 1
        # day=1 is explicit so future callers that change `first` to a non-day-1
        # date don't blow up on Jan 31 → Feb 31 style transitions.
        last = last.replace(year=y, month=m, day=1)
    cuota = CuotaPurchase(
        id=uuid.uuid4(),
        user_id=user.id,
        household_id=household.id,
        merchant_name=merchant,
        total_amount=monthly * total_installments,
        currency="CLP",
        installments_total=total_installments,
        installments_paid=2,
        monthly_amount=monthly,
        first_cuota_date=first,
        last_cuota_date=last,
        status="active",
        split_type="shared",
    )
    db.add(cuota)
    await db.flush()
    return cuota


async def seed_all() -> None:
    async with AsyncSessionLocal() as db:
        # HOGAR FULL
        rafa_full = await _get_or_create_user(db, "rafa-full@luka.test", "Rafa Full")
        partner_full = await _get_or_create_user(db, "partner-full@luka.test", "Partner Full")
        h_full = await _get_or_create_household(db, "HOGAR FULL", "group")
        await _ensure_member(db, h_full, rafa_full, "owner", mode="full")
        await _ensure_member(db, h_full, partner_full, "member", mode="full")
        acct_full = await _ensure_bank_account(db, h_full, rafa_full, "BancoChile Full")
        acct_full_partner = await _ensure_bank_account(db, h_full, partner_full, "BancoEstado Full")
        await _seed_transactions(db, rafa_full, h_full, acct_full, CLP_CATEGORIES)
        await _seed_transactions(db, partner_full, h_full, acct_full_partner, CLP_CATEGORIES)
        await _ensure_cuota(db, rafa_full, h_full, "Falabella Notebook", Decimal("50000"), 12)

        # HOGAR FIXED (partner fixed at 800k, mixed currencies)
        rafa_fixed = await _get_or_create_user(db, "rafa-fixed@luka.test", "Rafa Fixed")
        partner_fixed = await _get_or_create_user(db, "partner-fixed@luka.test", "Partner Fixed")
        h_fixed = await _get_or_create_household(db, "HOGAR FIXED", "group")
        await _ensure_member(db, h_fixed, rafa_fixed, "owner", mode="full")
        await _ensure_member(
            db,
            h_fixed,
            partner_fixed,
            "member",
            mode="fixed",
            fixed_amount=Decimal("800000"),
            fixed_currency="CLP",
        )
        acct_fixed = await _ensure_bank_account(db, h_fixed, rafa_fixed, "BancoChile Fixed")
        acct_fixed_usd = await _ensure_bank_account(
            db, h_fixed, rafa_fixed, "BofA USD Fixed", currency="USD"
        )
        acct_fixed_partner = await _ensure_bank_account(
            db, h_fixed, partner_fixed, "BancoEstado Fixed"
        )
        await _seed_transactions(db, rafa_fixed, h_fixed, acct_fixed, CLP_CATEGORIES)
        await _seed_transactions(db, partner_fixed, h_fixed, acct_fixed_partner, CLP_CATEGORIES)
        await _seed_transactions(
            db, rafa_fixed, h_fixed, acct_fixed_usd, USD_CATEGORIES, months_back=1, currency="USD"
        )

        # HOGAR REIMB
        rafa_reimb = await _get_or_create_user(db, "rafa-reimb@luka.test", "Rafa Reimb")
        partner_reimb = await _get_or_create_user(db, "partner-reimb@luka.test", "Partner Reimb")
        h_reimb = await _get_or_create_household(db, "HOGAR REIMB", "group")
        await _ensure_member(db, h_reimb, rafa_reimb, "owner", mode="full")
        await _ensure_member(db, h_reimb, partner_reimb, "member", mode="reimbursement")
        acct_reimb = await _ensure_bank_account(db, h_reimb, rafa_reimb, "BancoChile Reimb")
        acct_reimb_partner = await _ensure_bank_account(
            db, h_reimb, partner_reimb, "BancoEstado Reimb"
        )
        await _seed_transactions(db, rafa_reimb, h_reimb, acct_reimb, CLP_CATEGORIES)
        await _seed_transactions(db, partner_reimb, h_reimb, acct_reimb_partner, CLP_CATEGORIES)

        # HOGAR SOLO
        rafa_solo = await _get_or_create_user(db, "rafa-solo@luka.test", "Rafa Solo")
        h_solo = await _get_or_create_household(db, "HOGAR SOLO", "individual")
        await _ensure_member(db, h_solo, rafa_solo, "owner", mode="full")
        acct_solo = await _ensure_bank_account(db, h_solo, rafa_solo, "BancoChile Solo")
        await _seed_transactions(db, rafa_solo, h_solo, acct_solo, CLP_CATEGORIES)

        await db.commit()
        print("✅ Seeded budget test fixtures")


if __name__ == "__main__":
    asyncio.run(seed_all())
