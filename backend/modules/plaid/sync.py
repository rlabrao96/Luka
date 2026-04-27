"""Plaid transaction sync: fetches transactions via cursor, creates accounts, maps and deduplicates."""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sa_func, select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_token
from modules.plaid.models import PlaidItem
from modules.plaid.mapper import (
    map_plaid_transaction,
    map_account_kind,
    is_plaid_transfer,
    luka_amount_from_plaid,
)
from modules.plaid.service import sync_transactions
from modules.households.models import BankAccount
from modules.transactions.models import Transaction, TransactionSplit
from modules.reconciliation.dedup import find_email_match, apply_match_and_delete_emails


# 4-digit token (not surrounded by other digits)
_LAST_FOUR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")

# Strong signals that a Plaid tx is a credit-card bill payment (internal transfer).
_CC_PAYMENT_NAME_TOKENS = ("pago tarjeta", "online payment", "payment thank you")


def _is_cc_payment_signal(plaid_tx) -> bool:
    """Signal whether a Plaid tx is likely a credit-card bill payment.

    True if Plaid's category list contains TRANSFER or CREDIT_CARD, or the
    raw description contains a known CC-payment phrase.
    """
    categories = getattr(plaid_tx, "category", None) or []
    for c in categories:
        up = (c or "").upper()
        if "TRANSFER" in up or "CREDIT_CARD" in up or "CREDIT CARD" in up:
            return True
    name = (plaid_tx.name or "").lower()
    return any(tok in name for tok in _CC_PAYMENT_NAME_TOKENS)


def _resolve_cc_counterpart(
    plaid_tx,
    mask_map: dict[str, uuid.UUID],
    name_list: list[tuple[str, uuid.UUID]],
    exclude_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Resolve the counterpart BankAccount for a CC bill payment.

    Tier 1: any 4-digit token in plaid_tx.name matches a BankAccount.account_number.
    Tier 2: any BankAccount.bank_name (lowercased) is a substring of plaid_tx.name.lower().
    Excludes the source account itself so a payment never points back at its own row.
    """
    name = plaid_tx.name or ""
    # Tier 1 — last-four match
    for token in _LAST_FOUR_RE.findall(name):
        acct_id = mask_map.get(token)
        if acct_id and acct_id != exclude_id:
            return acct_id
    # Tier 2 — corrected name match (bank_name substring of plaid description)
    name_lower = name.lower()
    for bank_name_lower, acct_id in name_list:
        if not bank_name_lower:
            continue
        if bank_name_lower in name_lower and acct_id != exclude_id:
            return acct_id
    return None


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

    # On the very first sync after item/public_token/exchange, Plaid is still
    # ingesting the institution's data. /transactions/sync may return an empty
    # response (no accounts, no added) for the first ~5–30s. Retry with backoff
    # so the user sees their accounts and history without a manual refresh.
    initial_retry_delays = [3, 5, 8, 13, 21] if initial else [0]

    try:
        for attempt, delay in enumerate(initial_retry_delays):
            # Reset accumulators for the retry; keep the (still-None) cursor.
            all_added = []
            all_modified = []
            all_removed = []
            accounts_data = []

            has_more = True
            page_cursor = cursor
            while has_more:
                kwargs = {"access_token": access_token, "cursor": page_cursor}
                if initial and not page_cursor:
                    kwargs["count"] = 500
                response = sync_transactions(**kwargs)

                all_added.extend(response.added)
                all_modified.extend(response.modified)
                all_removed.extend(response.removed)
                if response.accounts:
                    accounts_data = response.accounts

                has_more = response.has_more
                page_cursor = response.next_cursor

            # Persist the latest cursor whether or not data arrived this attempt.
            cursor = page_cursor

            # Done if we got data, or this isn't an initial sync, or we're out of retries.
            if accounts_data or all_added or not initial:
                break
            if attempt < len(initial_retry_delays) - 1:
                await asyncio.sleep(delay)

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

    # Load household bank accounts ONCE for CC counterpart resolution.
    # Build a {account_number: id} dict and a [(bank_name.lower(), id)] list.
    hh_accounts_result = await session.execute(
        select(
            BankAccount.id,
            BankAccount.bank_name,
            BankAccount.account_number,
            BankAccount.account_type,
        ).where(
            BankAccount.household_id == item.household_id,
            BankAccount.is_active.is_(True),
        )
    )
    mask_map: dict[str, uuid.UUID] = {}
    name_list: list[tuple[str, uuid.UUID]] = []
    account_type_map: dict[uuid.UUID, str] = {}
    for acct_id, bank_name, acct_num, acct_type in hh_accounts_result.all():
        if acct_num:
            mask_map[acct_num] = acct_id
        if bank_name:
            name_list.append((bank_name.lower(), acct_id))
        account_type_map[acct_id] = acct_type

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

        # CC bill payment → route amount into a transfer and link the counterpart account.
        # Two-tier lookup: (1) last-4 digit token in name matches an account_number,
        # (2) any household bank_name appears as substring of plaid name.
        if _is_cc_payment_signal(plaid_tx):
            counterpart_id = _resolve_cc_counterpart(
                plaid_tx, mask_map, name_list, exclude_id=bank_account_id
            )
            if counterpart_id is not None:
                tx_data["transaction_type"] = "transfer"
                tx_data["category"] = None
                tx_data["transfer_to_account_id"] = counterpart_id
        elif is_plaid_transfer(plaid_tx):
            # Legacy path for non-CC internal transfers (loan payments, account moves).
            # Keep behaviour but use the pre-built name list instead of a per-tx query.
            merchant_lower = tx_data["raw_merchant_name"].lower()
            for bn_lower, acct_id in name_list:
                if bn_lower and bn_lower in merchant_lower and acct_id != bank_account_id:
                    tx_data["transaction_type"] = "transfer"
                    tx_data["transfer_to_account_id"] = acct_id
                    break

        # Try to match against email transactions
        match = await find_email_match(
            session,
            item.user_id,
            tx_data["raw_merchant_name"],
            tx_data["amount"],
            tx_data["transaction_date"],
            currency=tx_data.get("currency"),
            incoming_transaction_type=tx_data.get("transaction_type"),
            bank_account_id=bank_account_id,
        )

        new_tx = Transaction(**tx_data)
        session.add(new_tx)
        await session.flush()

        # Default to a personal split so category-usage queries and partner edits
        # behave consistently. apply_match_and_delete_emails may re-link an
        # existing email-side split onto this txn — the helper is idempotent so
        # the default is only used when no match attaches one.
        from modules.transactions.service import ensure_default_split

        is_joint = account_type_map.get(bank_account_id) == "joint"
        await ensure_default_split(
            session, new_tx, default_split_type="shared" if is_joint else "personal"
        )

        if match:
            await apply_match_and_delete_emails(
                session,
                new_tx.id,
                match["email_tx_ids"],
                match["enrichment"],
                user_id=item.user_id,
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

        # Route amount/status through the mapper helper so USD (cents) and
        # zero-decimal currencies (CLP, COP, ...) stay on one canonical convention.
        tx.amount = luka_amount_from_plaid(plaid_tx)
        tx.status = "pending" if plaid_tx.pending else "settled"
        tx.raw_merchant_name = plaid_tx.merchant_name or plaid_tx.name or tx.raw_merchant_name
        stats["modified"] += 1

    # Process removed transactions — Plaid sends "removed" when a pending tx settles
    # and is replaced by a new settled one (different plaid_transaction_id).
    # Transfer enrichment (splits, category, merchant_id) from the old one to the
    # matching new tx before deleting, so the user doesn't lose their categorization.
    for plaid_tx in all_removed:
        old_tx_result = await session.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == plaid_tx.transaction_id)
        )
        old_tx = old_tx_result.scalar_one_or_none()
        if old_tx is None:
            continue

        # Find the replacement Plaid transaction: same user, same bank_account,
        # same absolute amount, transaction_date within ±3 days, different plaid_id.
        date_min = old_tx.transaction_date - timedelta(days=3)
        date_max = old_tx.transaction_date + timedelta(days=3)
        replacement_result = await session.execute(
            select(Transaction)
            .where(
                Transaction.user_id == old_tx.user_id,
                Transaction.bank_account_id == old_tx.bank_account_id,
                Transaction.source == "plaid",
                Transaction.plaid_transaction_id != plaid_tx.transaction_id,
                sa_func.abs(Transaction.amount) == abs(old_tx.amount),
                Transaction.transaction_date >= date_min,
                Transaction.transaction_date <= date_max,
            )
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        replacement = replacement_result.scalar_one_or_none()

        if replacement is not None:
            # Re-link splits to the new transaction
            await session.execute(
                update(TransactionSplit)
                .where(TransactionSplit.transaction_id == old_tx.id)
                .values(transaction_id=replacement.id)
            )
            # Copy enrichment fields if the replacement doesn't have them yet
            if old_tx.category and not replacement.category:
                replacement.category = old_tx.category
            if old_tx.merchant_id and not replacement.merchant_id:
                replacement.merchant_id = old_tx.merchant_id
        else:
            # No replacement found — just drop the splits (rare)
            await session.execute(
                delete(TransactionSplit).where(TransactionSplit.transaction_id == old_tx.id)
            )

        await session.execute(delete(Transaction).where(Transaction.id == old_tx.id))
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
