"""Plaid transaction sync: fetches transactions via cursor, creates accounts, maps and deduplicates."""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func as sa_func, select, delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import decrypt_token
from modules.plaid.models import PlaidItem
from modules.plaid.mapper import (
    map_plaid_transaction,
    map_account_kind,
    is_plaid_transfer,
    luka_amount_from_plaid,
    resolve_raw_name,
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

    # Initial-sync cutoff: the user can bound how far back a newly-connected
    # bank backfills. Cursor sync pulls all history the institution exposes, so
    # we skip anything dated before the cutoff at ingestion. NULL = no cutoff.
    from modules.auth.models import User

    since_cutoff = await session.scalar(
        select(User.transactions_since).where(User.id == item.user_id)
    )

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
                # The Plaid SDK is synchronous — run it off the event loop so
                # one slow institution doesn't stall every other slow-worker job.
                response = await asyncio.to_thread(sync_transactions, **kwargs)

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

    # Pre-load already-ingested plaid ids in ONE query — the per-row SELECT
    # made an initial 1,000-tx sync issue 1,000 sequential round trips.
    existing_plaid_ids: set[str] = set()
    if all_added:
        added_ids = [t.transaction_id for t in all_added]
        for i in range(0, len(added_ids), 1000):
            chunk = added_ids[i : i + 1000]
            res = await session.execute(
                select(Transaction.plaid_transaction_id).where(
                    Transaction.plaid_transaction_id.in_(chunk)
                )
            )
            existing_plaid_ids.update(r[0] for r in res)

    # Process added transactions
    for plaid_tx in all_added:
        # Respect the user's initial-sync cutoff. plaid_tx.date is a date.
        if since_cutoff and plaid_tx.date < since_cutoff:
            continue
        plaid_account_id = plaid_tx.account_id
        bank_account_id = account_map.get(plaid_account_id)
        if not bank_account_id:
            continue

        # Dedup by plaid_transaction_id (pre-loaded above)
        if plaid_tx.transaction_id in existing_plaid_ids:
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

        # Default the split from the account type: joint→shared, partner→partner
        # (an authorized-user / additional card that belongs to the partner, kept
        # out of the owner's totals), else personal. apply_match_and_delete_emails
        # may re-link an existing email-side split onto this txn — the helper is
        # idempotent so the default is only used when no match attaches one.
        from modules.transactions.service import ensure_default_split, split_type_for_account

        await ensure_default_split(
            session,
            new_tx,
            default_split_type=split_type_for_account(account_type_map.get(bank_account_id)),
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

        # Phase 6: trip settlement auto-detect. Wrapped in try/except so a
        # failure here NEVER blocks Plaid sync (spec §4.7, plan Task 6.2).
        try:
            from modules.trips.auto_detect import try_match_settlement

            await try_match_settlement(session, new_tx)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception(
                "trip auto-detect failed for plaid txn %s; ignoring", new_tx.id
            )

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
        # User edits win: a tip adjustment must not revert a manual rename, and
        # the name goes through the same Zelle/CC extraction as the added path.
        if not (tx.user_edited_fields or {}).get("merchant_name"):
            tx.raw_merchant_name = resolve_raw_name(plaid_tx)
        # Re-derive expense/income if the sign flipped — but never clobber a
        # transfer classification (CC-payment routing) with a sign-based guess.
        if tx.transaction_type != "transfer":
            tx.transaction_type = "expense" if tx.amount <= 0 else "income"
        stats["modified"] += 1

    # Process removed transactions — Plaid sends "removed" when a pending tx settles
    # and is replaced by a new settled one (different plaid_transaction_id).
    # Transfer enrichment (splits, category, merchant_id) from the old one to the
    # matching new tx before deleting, so the user doesn't lose their categorization.
    #
    # Plaid's posted replacement carries pending_transaction_id — the deterministic
    # link for a pending→settled rotation. Prefer it over amount heuristics.
    pending_replacement_map = {
        getattr(a, "pending_transaction_id", None): a.transaction_id
        for a in all_added
        if getattr(a, "pending_transaction_id", None)
    }
    for plaid_tx in all_removed:
        old_tx_result = await session.execute(
            select(Transaction).where(Transaction.plaid_transaction_id == plaid_tx.transaction_id)
        )
        old_tx = old_tx_result.scalar_one_or_none()
        if old_tx is None:
            continue

        replacement = None
        replacement_plaid_id = pending_replacement_map.get(plaid_tx.transaction_id)
        if replacement_plaid_id:
            replacement_result = await session.execute(
                select(Transaction).where(Transaction.plaid_transaction_id == replacement_plaid_id)
            )
            replacement = replacement_result.scalar_one_or_none()

        # Heuristic fallback: same user, same bank_account, transaction_date
        # within ±3 days, different plaid_id. Exact absolute amount first, then
        # a ±20% window (tip adjustments / FX settles change the amount).
        date_min = old_tx.transaction_date - timedelta(days=3)
        date_max = old_tx.transaction_date + timedelta(days=3)
        base_filters = [
            Transaction.user_id == old_tx.user_id,
            Transaction.bank_account_id == old_tx.bank_account_id,
            Transaction.source == "plaid",
            Transaction.plaid_transaction_id != plaid_tx.transaction_id,
            Transaction.transaction_date >= date_min,
            Transaction.transaction_date <= date_max,
            (Transaction.amount <= 0) if old_tx.amount <= 0 else (Transaction.amount > 0),
        ]
        if replacement is None:
            replacement_result = await session.execute(
                select(Transaction)
                .where(*base_filters, sa_func.abs(Transaction.amount) == abs(old_tx.amount))
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
            replacement = replacement_result.scalar_one_or_none()
        if replacement is None:
            lo = abs(old_tx.amount) * Decimal("0.8")
            hi = abs(old_tx.amount) * Decimal("1.2")
            replacement_result = await session.execute(
                select(Transaction)
                .where(*base_filters, sa_func.abs(Transaction.amount).between(lo, hi))
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
            replacement = replacement_result.scalar_one_or_none()

        if replacement is not None:
            # The replacement already received a default split in the added path.
            # Drop it BEFORE re-linking the old split — a transaction with two
            # split rows is double-counted by every JOIN-based aggregate.
            await session.execute(
                delete(TransactionSplit).where(TransactionSplit.transaction_id == replacement.id)
            )
            await session.execute(
                update(TransactionSplit)
                .where(TransactionSplit.transaction_id == old_tx.id)
                .values(transaction_id=replacement.id)
            )
            # Re-link any trip-side references too, so a user's trip expenses
            # / settlements / dismissals follow the pending → settled rotation
            # rather than getting orphaned. The trip_expenses partial unique
            # index excludes deleted_at-stamped rows, so the update is safe.
            await session.execute(
                text(
                    "UPDATE trip_expenses SET transaction_id = :new_id "
                    "WHERE transaction_id = :old_id"
                ),
                {"new_id": str(replacement.id), "old_id": str(old_tx.id)},
            )
            await session.execute(
                text(
                    "UPDATE trip_settlements SET transaction_id = :new_id "
                    "WHERE transaction_id = :old_id"
                ),
                {"new_id": str(replacement.id), "old_id": str(old_tx.id)},
            )
            await session.execute(
                text(
                    "UPDATE trip_suggestion_dismissals SET transaction_id = :new_id "
                    "WHERE transaction_id = :old_id"
                ),
                {"new_id": str(replacement.id), "old_id": str(old_tx.id)},
            )
            await session.execute(
                text(
                    "UPDATE trip_settlement_dismissals SET transaction_id = :new_id "
                    "WHERE transaction_id = :old_id"
                ),
                {"new_id": str(replacement.id), "old_id": str(old_tx.id)},
            )
            # Copy enrichment fields if the replacement doesn't have them yet
            if old_tx.category and not replacement.category:
                replacement.category = old_tx.category
            if old_tx.merchant_id and not replacement.merchant_id:
                replacement.merchant_id = old_tx.merchant_id
            # Carry pair links so the surviving partner rows aren't orphaned
            # (an orphaned pair id silently excludes the partner from totals).
            if old_tx.transfer_pair_id and replacement.transfer_pair_id is None:
                replacement.transfer_pair_id = old_tx.transfer_pair_id
            if old_tx.refund_pair_id and replacement.refund_pair_id is None:
                replacement.refund_pair_id = old_tx.refund_pair_id
            if old_tx.reimbursement_group_id and replacement.reimbursement_group_id is None:
                replacement.reimbursement_group_id = old_tx.reimbursement_group_id
        else:
            # No replacement found — just drop the splits (rare). Trip-side
            # rows are handled by the FK cascade (migration 050): dismissals
            # CASCADE; trip_expenses / trip_settlements get SET NULL.
            await session.execute(
                delete(TransactionSplit).where(TransactionSplit.transaction_id == old_tx.id)
            )
            # Null pair ids on surviving partners (mirrors delete_transaction)
            # so they can be re-paired by a future reconciliation tick instead
            # of being silently excluded from totals forever.
            for pair_col in ("transfer_pair_id", "refund_pair_id", "reimbursement_group_id"):
                pair_val = getattr(old_tx, pair_col, None)
                if pair_val is not None:
                    await session.execute(
                        update(Transaction)
                        .where(
                            getattr(Transaction, pair_col) == pair_val,
                            Transaction.id != old_tx.id,
                        )
                        .values(**{pair_col: None})
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
    """Create/update bank_accounts from Plaid accounts. Returns {plaid_account_id: bank_account_id}.

    When a NEW account appears on an item that already had accounts (i.e. a card
    added AFTER the initial connection — e.g. a spouse's authorized-user Amex),
    raise a notification so its spending isn't silently attributed to the owner.
    The initial connection (item had zero accounts) is not notified — that's
    expected setup, not a surprise new card.
    """
    from modules.notifications.models import Notification

    account_map: dict[str, uuid.UUID] = {}

    # Snapshot BEFORE creating any account this run: >0 means this item was
    # already set up, so anything new below is a genuinely new account.
    had_accounts = (
        await session.execute(
            select(sa_func.count())
            .select_from(BankAccount)
            .where(BankAccount.plaid_item_id == item.id)
        )
    ).scalar_one() > 0

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
            # Update balances (round, not truncate — int() drops a cent half the time)
            ba.balance_current = (
                round(pa.balances.current * 100) if pa.balances.current is not None else None
            )
            ba.balance_limit = (
                round(pa.balances.limit * 100) if pa.balances.limit is not None else None
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
                balance_current=round(pa.balances.current * 100)
                if pa.balances.current is not None
                else None,
                balance_limit=round(pa.balances.limit * 100)
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

            if had_accounts:
                # New account on an already-connected item — surface it so the
                # user can mark it "De mi pareja" before its spending counts as
                # theirs. Added to the session; the sync's commit persists it.
                is_card = account_kind == "credit_card"
                noun = "tarjeta" if is_card else "cuenta"
                label = f"{account_name}" + (f" ••{mask}" if mask else "")
                session.add(
                    Notification(
                        user_id=item.user_id,
                        type="new_account_detected",
                        title=f"Detectamos una nueva {noun} en {item.institution_name}",
                        payload={
                            "account_id": str(ba.id),
                            "household_id": str(item.household_id),
                            "bank_name": item.institution_name,
                            "account_kind": account_kind,
                            "account_label": label,
                            "mask": mask,
                        },
                    )
                )

        account_map[plaid_account_id] = ba.id

    return account_map
