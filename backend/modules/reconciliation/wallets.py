"""Wallet funding-pair detection.

Wallets (Venmo, PayPal, CashApp) are pass-through user-owned accounts.
When a wallet payment is funded by a linked bank account, Luka receives
two same-sign transactions for the same economic event:

  BofA   "Venmo"           -$30.90    (funding leg)
  Venmo  "Nicolas Celasco"  -$30.90    (real expense, with counterparty)

This module detects such pairs and marks the bank leg as a `transfer`,
leaving the wallet leg as the canonical expense/income. Handles both
directions (funding and cash-out) within a ±5-day window.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import BankAccount
from modules.transactions.models import Transaction

_WALLET_BANK_NAMES = ("venmo", "paypal", "cash app", "cashapp")
_PAIR_WINDOW_DAYS = 5


def is_wallet_account(account: BankAccount) -> bool:
    """True if `account` is a connected wallet (Venmo / PayPal / CashApp).

    Detected via `account_kind == 'wallet'` (set by the Plaid mapper when
    subtype is 'paypal'), or by the account's `bank_name` containing a
    known wallet token (safety net for manually-added accounts).
    """
    if account.account_kind == "wallet":
        return True
    if account.bank_name is None:
        return False
    name = account.bank_name.lower()
    return any(token in name for token in _WALLET_BANK_NAMES)


async def detect_wallet_pairs(
    session: AsyncSession,
    household_id: uuid.UUID,
    lookback_days: int = 30,
) -> int:
    """Pair wallet-funding transactions with their canonical wallet leg.

    Rules:
      * Same household, same user, same currency, same abs(amount) (cents-exact).
      * At least one leg is on a wallet account (Venmo / PayPal / CashApp).
      * The bank-side row's merchant name references the wallet's bank_name
        (ILIKE substring) — e.g. a BofA row named 'VENMO *PAYMENT'.
      * Sign is NOT constrained: same-sign (funding) and opposite-sign (cash-out)
        are both accepted. This is the difference vs. detect_transfers.
      * Dates within ±5 days.
      * Neither leg already paired (transfer_pair_id or refund_pair_id set).

    On match: share a fresh transfer_pair_id; re-type the NON-wallet leg to
    'transfer'. The wallet leg keeps its expense/income type.

    Returns number of pairs created.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    rows = (
        await session.execute(
            select(Transaction, BankAccount)
            .join(BankAccount, Transaction.bank_account_id == BankAccount.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transaction_date >= cutoff,
                Transaction.transfer_pair_id.is_(None),
                Transaction.refund_pair_id.is_(None),
                Transaction.bank_account_id.is_not(None),
            )
            .order_by(Transaction.transaction_date)
        )
    ).all()

    wallet_rows: list[tuple[Transaction, BankAccount]] = []
    bank_rows: list[tuple[Transaction, BankAccount]] = []
    for tx, acct in rows:
        (wallet_rows if is_wallet_account(acct) else bank_rows).append((tx, acct))

    if not wallet_rows or not bank_rows:
        return 0

    def _cents(amount) -> int:
        return round(abs(float(amount)) * 100)

    wallet_index: dict[tuple, list[tuple[Transaction, BankAccount]]] = defaultdict(list)
    for tx, acct in wallet_rows:
        wallet_index[(tx.user_id, tx.currency, _cents(tx.amount))].append((tx, acct))

    matched_ids: set[uuid.UUID] = set()
    pairs_found = 0

    for bank_tx, _bank_acct in bank_rows:
        if bank_tx.id in matched_ids:
            continue
        if bank_tx.raw_merchant_name is None:
            continue
        bank_merchant = bank_tx.raw_merchant_name.lower()

        key = (bank_tx.user_id, bank_tx.currency, _cents(bank_tx.amount))
        for wallet_tx, wallet_acct in wallet_index.get(key, ()):
            if wallet_tx.id in matched_ids:
                continue
            if wallet_acct.bank_name is None:
                continue
            if wallet_acct.bank_name.lower() not in bank_merchant:
                continue
            day_diff = abs((bank_tx.transaction_date - wallet_tx.transaction_date).days)
            if day_diff > _PAIR_WINDOW_DAYS:
                continue

            pair_id = uuid.uuid4()
            await session.execute(
                update(Transaction)
                .where(Transaction.id.in_([bank_tx.id, wallet_tx.id]))
                .values(transfer_pair_id=pair_id)
            )
            await session.execute(
                update(Transaction)
                .where(Transaction.id == bank_tx.id)
                .values(transaction_type="transfer")
            )
            matched_ids.add(bank_tx.id)
            matched_ids.add(wallet_tx.id)
            pairs_found += 1
            break

    return pairs_found
