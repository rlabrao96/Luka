"""Reconciliation tick: periodic orchestrator that glues every reconciliation
pass together for one household (or all households).

Four passes, in order:
  1. Email-after-Plaid rematch — pending email rows older than 5 min that now
     have a settled Plaid counterpart in the DB get collapsed onto the Plaid
     row (enrichment copied, email row deleted).
  2. Transfer detection — pairs same-owner cross-account moves.
  3. Refund detection — pairs same-account charge/refund reversals.
  4. Aging — email pendings older than 14 days become `orphan` when at least
     one of the owner's Plaid items has synced after the row was created.
     If no Plaid item has synced since (bank outage), we leave them pending.

Return shape: {'rematched', 'transfers', 'refunds', 'orphaned'}.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import Household
from modules.plaid.models import PlaidItem
from modules.reconciliation.dedup import (
    _extract_enrichment,
    apply_match_and_delete_emails,
    find_plaid_match_for_email,
)
import logging

from modules.reconciliation.credit_suggestions import (
    emit_credit_suggestions_for_household,
)
from modules.reconciliation.refunds import detect_refunds
from modules.reconciliation.transfers import detect_transfers
from modules.reconciliation.wallets import detect_wallet_pairs
from modules.transactions.models import Transaction

_log = logging.getLogger(__name__)


async def reconciliation_tick_for_household(
    session: AsyncSession, household_id: uuid.UUID
) -> dict[str, int]:
    now = datetime.now(timezone.utc)

    # ---------- 1. Rematch aging email pendings against settled Plaid rows.
    rematch_cutoff = now - timedelta(minutes=5)
    email_pendings = (
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.household_id == household_id,
                    Transaction.source_type == "email",
                    Transaction.status == "pending",
                    Transaction.created_at < rematch_cutoff,
                )
            )
        )
        .scalars()
        .all()
    )

    rematched = 0
    for email_tx in email_pendings:
        bank_tx = await find_plaid_match_for_email(session, email_tx)
        if bank_tx is None:
            continue
        enrichment = await _extract_enrichment(session, email_tx.id)
        await apply_match_and_delete_emails(
            session,
            bank_tx_id=bank_tx.id,
            email_tx_ids=[email_tx.id],
            enrichment=enrichment,
            user_id=email_tx.user_id,
        )
        rematched += 1

    # ---------- 2. Transfer pass (opposite-sign, ±2 days, own-account).
    transfers = await detect_transfers(session, household_id, lookback_days=7)

    # ---------- 3. Wallet-pair pass (same- or opposite-sign, ±5 days, wallet-gated).
    wallet_pairs = await detect_wallet_pairs(session, household_id, lookback_days=30)

    # ---------- 4. Refund pass.
    refunds = await detect_refunds(session, household_id, lookback_days=90)

    # ---------- 4. Aging pass.
    aging_cutoff = now - timedelta(days=14)
    aging_rows = (
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.household_id == household_id,
                    Transaction.source_type == "email",
                    Transaction.status == "pending",
                    Transaction.created_at < aging_cutoff,
                )
            )
        )
        .scalars()
        .all()
    )

    # One query for the whole batch: latest Plaid sync per owner (M25) —
    # the old per-row PlaidItem lookup turned a 200-email backlog into 200
    # sequential point queries.
    orphaned = 0
    if aging_rows:
        owner_ids = {tx.user_id for tx in aging_rows}
        sync_rows = await session.execute(
            select(PlaidItem.user_id, func.max(PlaidItem.last_sync_at))
            .where(PlaidItem.user_id.in_(owner_ids))
            .group_by(PlaidItem.user_id)
        )
        last_sync_by_user = {uid: ts for uid, ts in sync_rows.all() if ts is not None}
        for tx in aging_rows:
            last_sync = last_sync_by_user.get(tx.user_id)
            if last_sync is not None and last_sync > tx.created_at:
                tx.status = "orphan"
                tx.orphaned_at = now
                orphaned += 1
    await session.flush()

    # ---------- 5. Credit-suggestion pass.
    # Independent of the auto-pairing logic — never pairs without user
    # confirmation. Failures here must not poison the whole tick.
    credit_suggestions_created = 0
    credit_suggestions_auto_resolved = 0
    try:
        cs = await emit_credit_suggestions_for_household(session, household_id)
        credit_suggestions_created = cs["created"]
        credit_suggestions_auto_resolved = cs["auto_resolved"]
    except Exception:  # pragma: no cover — defensive
        _log.exception("credit_suggestions step failed for household %s", household_id)

    return {
        "rematched": rematched,
        "transfers": transfers,
        "wallet_pairs": wallet_pairs,
        "refunds": refunds,
        "orphaned": orphaned,
        "credit_suggestions": credit_suggestions_created,
        "credit_suggestions_auto_resolved": credit_suggestions_auto_resolved,
    }


async def reconciliation_tick_all_households(session: AsyncSession) -> dict[str, int]:
    """Run the tick for every household. Commits between households so a
    failure on one doesn't roll back the others' work."""
    household_ids = (await session.execute(select(Household.id))).scalars().all()

    totals = {
        "rematched": 0,
        "transfers": 0,
        "wallet_pairs": 0,
        "refunds": 0,
        "orphaned": 0,
        "credit_suggestions": 0,
        "credit_suggestions_auto_resolved": 0,
    }
    for hid in household_ids:
        result = await reconciliation_tick_for_household(session, hid)
        for k in totals:
            totals[k] += result.get(k, 0)
        await session.commit()
    return totals
