"""One-shot backfill: consolidate duplicate pending transactions.

Today the "Pendientes" UI shows pairs of rows for the same purchase — one
`source_type='email'` + one `source_type='plaid'`, both `status='pending'` —
because the auto-reconciler never ran for them (the existing
`find_plaid_match_for_email` in `modules/reconciliation/dedup.py` requires
`status == 'settled'`). This script retroactively merges those duplicates.

Branch independence:
    A parallel branch (Branch A) is broadening dedup.find_plaid_match_for_email
    to accept pending Plaid rows. This script does NOT depend on that change.
    It carries its own pending-aware matcher locally (`_find_pending_plaid_match`)
    and reuses the safe enrichment-and-delete primitive
    `apply_match_and_delete_emails` from dedup.py (which is status-agnostic).
    Once Branch A merges, this script will keep working unchanged.

Algorithm (per household):
    1. Fetch all transactions where:
         status='pending' AND source_type IN ('email','plaid')
         AND transfer_pair_id IS NULL AND refund_pair_id IS NULL
    2. For every email row, find at most one Plaid candidate with:
         - same currency
         - same SIGNED amount (sign convention: expenses negative, income positive)
         - transaction_date within ±3 days
         - bank_account_id equal OR one side NULL (email may be unresolved)
         - if both sides have non-NULL source_bank_name, they must match
         - merchant: ILIKE substring in either direction OR conservative
           normalized equality (lowercase, strip TLDs, collapse spaces).
           Skip the merchant test entirely for transfers (CC-payment strings
           diverge from Plaid labels — same as dedup.py does).
    3. If exactly one candidate matches, consolidate:
         apply_match_and_delete_emails copies enrichment from email onto Plaid
         and deletes the email row. Joint-account invariant: if the Plaid
         row's bank_account is `joint`, force split_type='shared' afterwards.
    4. If 2+ candidates → "ambiguous, skipped".

Safety:
    --dry-run prints the plan and rolls back.
    Non-dry mode prints the plan first, then commits per-pair (small txns).
    Idempotent: a second run finds zero pairs (email rows are gone).

CLI:
    python -m scripts.backfill_pending_consolidation [--household-id UUID]
                                                     [--dry-run]
                                                     [--limit N]

Defaults: all households, commit ON.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal

# Register every ORM model so Base.metadata can resolve cross-table FKs
import modules.merchants.models  # noqa: F401
import modules.plaid.models  # noqa: F401
import modules.transactions.models  # noqa: F401
from modules.households.models import BankAccount, Household
from modules.reconciliation.dedup import (
    _extract_enrichment,
    apply_match_and_delete_emails,
)
from modules.transactions.models import Transaction, TransactionSplit


# ---------------------------------------------------------------- matching


_TLD_RE = re.compile(r"\.(com|cl|mx|pe|co|br|ar|us|net|org)\b", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _normalize_merchant(name: str | None) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = _TLD_RE.sub("", n)
    n = _WS_RE.sub(" ", n)
    return n.strip()


def _merchant_compatible(email_name: str | None, plaid_name: str | None) -> bool:
    """Conservative two-way merchant compatibility test.

    Either side ILIKE-substrings the other, OR their normalized forms are
    equal. Returns True if at least one of those holds. If either side is
    blank, returns False (conservative: no match without evidence).
    """
    if not email_name or not plaid_name:
        return False
    e = email_name.lower().strip()
    p = plaid_name.lower().strip()
    if e in p or p in e:
        return True
    return _normalize_merchant(email_name) == _normalize_merchant(plaid_name)


@dataclass
class PendingPair:
    email_tx: Transaction
    plaid_tx: Transaction


def _candidate_compatible(
    email_tx: Transaction,
    plaid_tx: Transaction,
    *,
    plaid_account: BankAccount | None,
) -> bool:
    """Decide whether a (email, plaid) pending pair represents the same event."""
    if email_tx.currency != plaid_tx.currency:
        return False
    if email_tx.amount != plaid_tx.amount:  # signed equality
        return False
    delta = abs((email_tx.transaction_date - plaid_tx.transaction_date).total_seconds())
    if delta > 3 * 86400:
        return False

    # bank_account_id parity: equal, or one side NULL
    if (
        email_tx.bank_account_id is not None
        and plaid_tx.bank_account_id is not None
        and email_tx.bank_account_id != plaid_tx.bank_account_id
    ):
        return False

    # Cross-bank guard. If the email carries a source_bank_name and the
    # plaid account has a bank_name, they must match (case-insensitive).
    if email_tx.source_bank_name and plaid_account and plaid_account.bank_name:
        if email_tx.source_bank_name.strip().lower() != plaid_account.bank_name.strip().lower():
            return False
    # If the plaid row also carries source_bank_name, prefer that too.
    if email_tx.source_bank_name and plaid_tx.source_bank_name:
        if email_tx.source_bank_name.strip().lower() != plaid_tx.source_bank_name.strip().lower():
            return False

    # Merchant match — skipped for transfers (divergent strings, same as dedup.py).
    is_transfer = email_tx.transaction_type == "transfer" or plaid_tx.transaction_type == "transfer"
    if not is_transfer:
        if not _merchant_compatible(email_tx.raw_merchant_name, plaid_tx.raw_merchant_name):
            return False

    return True


async def _find_pending_plaid_matches(
    db: AsyncSession,
    email_tx: Transaction,
    plaid_pool: list[Transaction],
    accounts_by_id: dict[uuid.UUID, BankAccount],
) -> list[Transaction]:
    """Local pending-aware variant — does not require Plaid status='settled'."""
    matches: list[Transaction] = []
    for p in plaid_pool:
        plaid_account = accounts_by_id.get(p.bank_account_id) if p.bank_account_id else None
        if _candidate_compatible(email_tx, p, plaid_account=plaid_account):
            matches.append(p)
    return matches


# ---------------------------------------------------------------- core flow


async def _household_ids(db: AsyncSession, only: uuid.UUID | None) -> list[uuid.UUID]:
    if only is not None:
        return [only]
    res = await db.execute(select(Household.id))
    return list(res.scalars().all())


async def _load_pending_for_household(
    db: AsyncSession, household_id: uuid.UUID
) -> tuple[list[Transaction], list[Transaction]]:
    """Return (email_pending, plaid_pending) for the household."""
    base = and_(
        Transaction.household_id == household_id,
        Transaction.status == "pending",
        Transaction.transfer_pair_id.is_(None),
        Transaction.refund_pair_id.is_(None),
    )
    email_rows = (
        (
            await db.execute(
                select(Transaction).where(and_(base, Transaction.source_type == "email"))
            )
        )
        .scalars()
        .all()
    )
    plaid_rows = (
        (
            await db.execute(
                select(Transaction).where(and_(base, Transaction.source_type == "plaid"))
            )
        )
        .scalars()
        .all()
    )
    return list(email_rows), list(plaid_rows)


async def _accounts_by_id(
    db: AsyncSession, household_id: uuid.UUID
) -> dict[uuid.UUID, BankAccount]:
    rows = (
        (await db.execute(select(BankAccount).where(BankAccount.household_id == household_id)))
        .scalars()
        .all()
    )
    return {a.id: a for a in rows}


async def _enforce_joint_split(
    db: AsyncSession, plaid_tx_id: uuid.UUID, account: BankAccount | None
) -> None:
    """If the Plaid row sits on a joint account, force its split to 'shared'."""
    if account is None or account.account_type != "joint":
        return
    existing = await db.execute(
        select(TransactionSplit.id).where(TransactionSplit.transaction_id == plaid_tx_id).limit(1)
    )
    split_id = existing.scalar_one_or_none()
    if split_id:
        await db.execute(
            update(TransactionSplit)
            .where(TransactionSplit.id == split_id)
            .values(split_type="shared")
        )
    else:
        db.add(
            TransactionSplit(
                id=uuid.uuid4(),
                transaction_id=plaid_tx_id,
                split_type="shared",
            )
        )


async def _backfill_household(
    db: AsyncSession,
    household_id: uuid.UUID,
    *,
    dry_run: bool,
    limit: int | None,
    commit_per_pair: bool = True,
) -> dict[str, int]:
    emails, plaids = await _load_pending_for_household(db, household_id)
    accounts = await _accounts_by_id(db, household_id)

    merged = 0
    ambiguous = 0
    plan: list[tuple[Transaction, Transaction]] = []
    consumed_plaid_ids: set[uuid.UUID] = set()

    for email_tx in emails:
        if limit is not None and merged + ambiguous >= limit:
            break

        # Exclude already-consumed Plaid candidates so two emails don't both
        # claim the same Plaid row in a single pass.
        pool = [p for p in plaids if p.id not in consumed_plaid_ids]
        candidates = await _find_pending_plaid_matches(db, email_tx, pool, accounts)
        if len(candidates) == 0:
            continue
        if len(candidates) > 1:
            print(
                f"  [hh={household_id}] ambiguous: email {email_tx.id} "
                f"matched {len(candidates)} plaid rows — skipped"
            )
            ambiguous += 1
            continue

        plaid_tx = candidates[0]
        plan.append((email_tx, plaid_tx))
        consumed_plaid_ids.add(plaid_tx.id)

    # Print the plan first.
    for email_tx, plaid_tx in plan:
        print(
            f"  [hh={household_id}] MERGE email={email_tx.id} "
            f"-> plaid={plaid_tx.id} amount={email_tx.amount} {email_tx.currency} "
            f"date={email_tx.transaction_date.isoformat()} merchant={email_tx.raw_merchant_name!r}"
        )

    if dry_run:
        return {"merged": 0, "ambiguous": ambiguous, "planned": len(plan)}

    # Apply per-pair so a partial failure leaves a consistent state.
    for email_tx, plaid_tx in plan:
        try:
            enrichment = await _extract_enrichment(db, email_tx.id)
            await apply_match_and_delete_emails(
                db,
                bank_tx_id=plaid_tx.id,
                email_tx_ids=[email_tx.id],
                enrichment=enrichment,
                user_id=email_tx.user_id,
            )
            await _enforce_joint_split(
                db,
                plaid_tx.id,
                accounts.get(plaid_tx.bank_account_id) if plaid_tx.bank_account_id else None,
            )
            if commit_per_pair:
                await db.commit()
            else:
                await db.flush()
            merged += 1
        except Exception as exc:  # pragma: no cover — log and continue
            if commit_per_pair:
                await db.rollback()
            print(
                f"  [hh={household_id}] FAILED email={email_tx.id} plaid={plaid_tx.id}: {exc}",
                file=sys.stderr,
            )

    return {"merged": merged, "ambiguous": ambiguous, "planned": len(plan)}


async def main(
    *,
    household_id: uuid.UUID | None,
    dry_run: bool,
    limit: int | None,
) -> int:
    async with AsyncSessionLocal() as db:
        ids = await _household_ids(db, household_id)
        print(f"[backfill] households={len(ids)} dry_run={dry_run} limit={limit}")

        totals = {"merged": 0, "ambiguous": 0, "planned": 0}
        for hid in ids:
            r = await _backfill_household(db, hid, dry_run=dry_run, limit=limit)
            for k in totals:
                totals[k] += r[k]

        if dry_run:
            await db.rollback()
            print(
                f"[backfill] DRY-RUN — rolled back. "
                f"Would-merge: {totals['planned']} pairs. "
                f"Ambiguous: {totals['ambiguous']}. Households scanned: {len(ids)}."
            )
        else:
            print(
                f"[backfill] DONE. "
                f"{totals['merged']} pairs merged, "
                f"{totals['ambiguous']} ambiguous skipped, "
                f"{len(ids)} households scanned."
            )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--household-id", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    hh = uuid.UUID(args.household_id) if args.household_id else None
    sys.exit(asyncio.run(main(household_id=hh, dry_run=args.dry_run, limit=args.limit)))
