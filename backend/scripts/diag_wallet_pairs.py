"""Diagnostic: why did detect_wallet_pairs find 0 pairs?

Prints:
  1. All bank_accounts in the user's households (bank_name, account_kind).
  2. Which ones the is_wallet_account predicate classifies as wallets.
  3. Sample transactions on each wallet account (last 60 days).
  4. BofA transactions whose merchant contains 'venmo' / 'paypal' / 'cashapp'
     (last 60 days) — these are the rows that SHOULD pair against a wallet leg.

Usage:
    python -m scripts.diag_wallet_pairs --email rafaellabra96@gmail.com
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from core.database import AsyncSessionLocal

import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.auth.models import User
from modules.households.models import BankAccount, HouseholdMember
from modules.reconciliation.wallets import is_wallet_account
from modules.transactions.models import Transaction


async def main(email: str) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            print(f"No user with email {email}", file=sys.stderr)
            return 1

        hids = (
            (
                await db.execute(
                    select(HouseholdMember.household_id).where(HouseholdMember.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )

        cutoff = datetime.now(timezone.utc) - timedelta(days=60)

        for hid in hids:
            print(f"\n===== Household {hid} =====")

            accts = (
                (await db.execute(select(BankAccount).where(BankAccount.household_id == hid)))
                .scalars()
                .all()
            )

            print("\n-- bank_accounts --")
            for a in accts:
                flag = "WALLET" if is_wallet_account(a) else "      "
                print(
                    f"  [{flag}] bank_name={a.bank_name!r:30s} "
                    f"account_kind={a.account_kind!r} "
                    f"provider={a.provider!r} country={a.country!r}"
                )

            wallet_accts = [a for a in accts if is_wallet_account(a)]
            if wallet_accts:
                print("\n-- wallet tx (last 60d) --")
                for a in wallet_accts:
                    rows = (
                        (
                            await db.execute(
                                select(Transaction)
                                .where(
                                    Transaction.bank_account_id == a.id,
                                    Transaction.transaction_date >= cutoff,
                                )
                                .order_by(Transaction.transaction_date.desc())
                                .limit(10)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    print(f"  {a.bank_name}:")
                    for tx in rows:
                        print(
                            f"    {tx.transaction_date.date()} | "
                            f"{float(tx.amount):>10.2f} {tx.currency} | "
                            f"{tx.transaction_type:8s} | "
                            f"pair={str(tx.transfer_pair_id)[:8] if tx.transfer_pair_id else '--':8s} | "
                            f"{tx.raw_merchant_name!r}"
                        )

            print("\n-- BofA-side tx matching venmo/paypal/cashapp (last 60d) --")
            # Non-wallet account transactions with matching merchant
            non_wallet_ids = [a.id for a in accts if not is_wallet_account(a)]
            if non_wallet_ids:
                rows = (
                    await db.execute(
                        select(Transaction, BankAccount)
                        .join(
                            BankAccount,
                            Transaction.bank_account_id == BankAccount.id,
                        )
                        .where(
                            Transaction.bank_account_id.in_(non_wallet_ids),
                            Transaction.transaction_date >= cutoff,
                            or_(
                                Transaction.raw_merchant_name.ilike("%venmo%"),
                                Transaction.raw_merchant_name.ilike("%paypal%"),
                                Transaction.raw_merchant_name.ilike("%cashapp%"),
                                Transaction.raw_merchant_name.ilike("%cash app%"),
                            ),
                        )
                        .order_by(Transaction.transaction_date.desc())
                        .limit(30)
                    )
                ).all()
                for tx, acct in rows:
                    print(
                        f"    {tx.transaction_date.date()} | "
                        f"{float(tx.amount):>10.2f} {tx.currency} | "
                        f"{acct.bank_name!r:20s} | "
                        f"pair={str(tx.transfer_pair_id)[:8] if tx.transfer_pair_id else '--':8s} | "
                        f"{tx.raw_merchant_name!r}"
                    )

        return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--email", default="rafaellabra96@gmail.com")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.email)))
