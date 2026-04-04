"""Plaid transaction sync: fetches transactions via cursor, creates accounts, maps and deduplicates."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_token
from modules.plaid.models import PlaidItem
from modules.plaid.mapper import map_plaid_transaction, map_account_kind, is_plaid_transfer
from modules.plaid.service import sync_transactions
from modules.households.models import BankAccount
from modules.transactions.models import Transaction
from modules.reconciliation.dedup import find_email_match, apply_match_and_delete_emails


async def run_plaid_sync(
    session: AsyncSession, plaid_item_id: uuid.UUID, initial: bool = False
) -> dict:
    """Run a full sync for a Plaid item. Returns stats dict."""
    result = await session.execute(select(PlaidItem).where(PlaidItem.id == plaid_item_id))
    item = result.scalar_one_or_none()
    if not item:
        return {"error": "PlaidItem not found"}

    if item.error_code:
        return {"error": f"Item has error: {item.error_code}"}

    access_token = decrypt_token(item.access_token_enc)
    cursor = item.cursor
    all_added = []
    all_modified = []
    all_removed = []
    accounts_data = []

    try:
        # Paginate through all updates
        has_more = True
        while has_more:
            kwargs = {"access_token": access_token, "cursor": cursor}
            if initial and not cursor:
                kwargs["count"] = 500
            response = sync_transactions(**kwargs)

            all_added.extend(response.added)
            all_modified.extend(response.modified)
            all_removed.extend(response.removed)
            if response.accounts:
                accounts_data = response.accounts

            has_more = response.has_more
            cursor = response.next_cursor

    except Exception as e:
        error_str = str(e)
        # Check for ITEM_LOGIN_REQUIRED
        if "ITEM_LOGIN_REQUIRED" in error_str:
            item.error_code = "ITEM_LOGIN_REQUIRED"
            item.last_sync_status = "failed"
            await session.commit()
            return {"error": "ITEM_LOGIN_REQUIRED"}

        item.last_sync_status = "failed"
        await session.commit()
        raise

    # Ensure accounts exist
    account_map = await ensure_plaid_accounts(session, item, accounts_data)

    stats = {"added": 0, "modified": 0, "removed": 0, "deduped": 0, "new_tx_ids": []}

    # Process added transactions
    for plaid_tx in all_added:
        plaid_account_id = plaid_tx.account_id
        bank_account_id = account_map.get(plaid_account_id)
        if not bank_account_id:
            continue

        # Check for existing (dedup by plaid_transaction_id)
        existing = await session.execute(
            select(Transaction.id).where(
                Transaction.plaid_transaction_id == plaid_tx.transaction_id
            )
        )
        if existing.scalar_one_or_none():
            continue

        tx_data = map_plaid_transaction(
            plaid_tx, str(bank_account_id), str(item.user_id), str(item.household_id)
        )

        # Check if Plaid flags this as a transfer
        if is_plaid_transfer(plaid_tx):
            tx_data["transaction_type"] = "transfer"

        # Try to match against email transactions
        match = await find_email_match(
            session,
            item.user_id,
            tx_data["raw_merchant_name"],
            tx_data["amount"],
            tx_data["transaction_date"],
        )

        new_tx = Transaction(**tx_data)
        session.add(new_tx)
        await session.flush()

        if match:
            await apply_match_and_delete_emails(
                session, new_tx.id, match["email_tx_ids"], match["enrichment"]
            )
            stats["deduped"] += 1

        stats["added"] += 1
        stats["new_tx_ids"].append(str(new_tx.id))

    # Process modified transactions (tip adjustments, pending → settled)
    for plaid_tx in all_modified:
        existing = await session.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == plaid_tx.transaction_id)
        )
        tx = existing.scalar_one_or_none()
        if not tx:
            continue

        plaid_amount = float(plaid_tx.amount)
        tx.amount = plaid_amount * -1
        tx.status = "pending" if plaid_tx.pending else "confirmed"
        tx.raw_merchant_name = plaid_tx.merchant_name or plaid_tx.name or tx.raw_merchant_name
        stats["modified"] += 1

    # Process removed transactions
    for plaid_tx in all_removed:
        await session.execute(
            delete(Transaction).where(Transaction.plaid_transaction_id == plaid_tx.transaction_id)
        )
        stats["removed"] += 1

    # Update item state
    item.cursor = cursor
    item.last_sync_at = datetime.now(timezone.utc)
    item.last_sync_status = "success"
    item.error_code = None

    await session.commit()

    return stats


async def ensure_plaid_accounts(
    session: AsyncSession,
    item: PlaidItem,
    plaid_accounts: list,
) -> dict[str, uuid.UUID]:
    """Create/update bank_accounts from Plaid accounts. Returns {plaid_account_id: bank_account_id}."""
    account_map: dict[str, uuid.UUID] = {}

    for pa in plaid_accounts:
        plaid_account_id = pa.account_id

        # Check if account already exists
        result = await session.execute(
            select(BankAccount).where(
                BankAccount.plaid_account_id == plaid_account_id,
                BankAccount.plaid_item_id == item.id,
            )
        )
        ba = result.scalar_one_or_none()

        account_kind = map_account_kind(pa.type, pa.subtype)
        account_name = pa.official_name or pa.name or "Unknown Account"
        mask = pa.mask

        if ba:
            # Update balances
            ba.balance_current = (
                int(pa.balances.current * 100) if pa.balances.current is not None else None
            )
            ba.balance_limit = (
                int(pa.balances.limit * 100) if pa.balances.limit is not None else None
            )
            ba.last_synced_at = datetime.now(timezone.utc)
        else:
            # Create new bank account
            ba = BankAccount(
                household_id=item.household_id,
                user_id=item.user_id,
                bank_name=item.institution_name,
                account_type="personal",  # default, user can change
                account_kind=account_kind,
                account_name=account_name,
                account_number=mask,
                currency=pa.balances.iso_currency_code or "USD",
                balance_current=int(pa.balances.current * 100)
                if pa.balances.current is not None
                else None,
                balance_limit=int(pa.balances.limit * 100)
                if pa.balances.limit is not None
                else None,
                last_synced_at=datetime.now(timezone.utc),
                is_active=True,
                provider="plaid",
                country="US",
                plaid_item_id=item.id,
                plaid_account_id=plaid_account_id,
            )
            session.add(ba)
            await session.flush()

        account_map[plaid_account_id] = ba.id

    return account_map
