import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, text, delete as sql_delete, update as sql_update
from modules.transactions.models import Transaction, TransactionSplit
from modules.households.models import BankAccount, HouseholdMember
from modules.merchants.models import Merchant
from modules.merchant_review.models import CanonicalMerchant
from modules.merchants.service import record_category_selection
from core.cache import _get_redis


# Fields a user can touch via web/whatsapp UI. Keep this list in lockstep with the
# `user_edited_fields` JSONB map on `transactions` (see migration 042).
USER_EDITABLE_FIELDS = frozenset(
    {
        "merchant_name",
        "category",
        "split_type",
        "transaction_type",
        "transfer_to_account_id",
        "transaction_date",
    }
)


def mark_user_edited(txn: Transaction, *fields: str) -> None:
    """Set ``user_edited_fields[field] = True`` for each user-edited field on ``txn``.

    Centralized so every PATCH/update site goes through one path — drift here
    silently breaks the user-edit-wins invariant in the merge pipeline.
    """
    current = dict(txn.user_edited_fields or {})
    for field in fields:
        if field not in USER_EDITABLE_FIELDS:
            raise ValueError(f"Unknown user-editable field: {field}")
        current[field] = True
    txn.user_edited_fields = current


async def ensure_default_split(
    db: AsyncSession,
    txn: Transaction,
    default_split_type: str | None = None,
) -> None:
    """Create a TransactionSplit row for `txn` if none exists yet. Idempotent.

    Transfers don't carry a personal/shared classification — skipped. When the
    caller passes `default_split_type` explicitly (e.g. Plaid + bank_connect
    ingestion pre-look-up the account type), that value is used directly — no
    extra DB query. When omitted, this function defends against new ingestion
    paths that forget the kwarg by auto-detecting from the transaction's
    `BankAccount.account_type`: joint accounts default to "shared", everything
    else falls back to "personal".
    """
    if txn.transaction_type == "transfer":
        return
    existing = await db.execute(
        select(TransactionSplit.id).where(TransactionSplit.transaction_id == txn.id)
    )
    if existing.scalar_one_or_none() is not None:
        return

    if default_split_type is None:
        # Auto-detect from the account so any future call site is safe.
        account_type = await db.scalar(
            select(BankAccount.account_type).where(BankAccount.id == txn.bank_account_id)
        )
        default_split_type = "shared" if account_type == "joint" else "personal"

    db.add(TransactionSplit(transaction_id=txn.id, split_type=default_split_type))


async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, since: date) -> list[dict]:
    result = await db.execute(
        select(
            Transaction,
            TransactionSplit,
            BankAccount.bank_name,
            BankAccount.account_kind,
            CanonicalMerchant.display_name.label("display_name"),
        )
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= since,
            Transaction.status.notin_(["pending", "orphan"]),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type if split else None,
            "bank_name": bank_name or txn.source_bank_name,
            "account_kind": account_kind,
            "display_name": display_name,
        }
        for txn, split, bank_name, account_kind, display_name in rows
    ]


async def get_monthly_summary(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    currency: str | None = None,
) -> list[dict]:
    MONTH_ABBR = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]
    # Currency filter: summing CLP and USD together produces nonsense.
    # When `currency` is provided (via the CLP/USD toggle), restrict both
    # aggregates to transactions in that currency.
    currency_clause = "AND t.currency = :currency" if currency else ""
    params: dict = {"household_id": str(household_id), "user_id": str(user_id)}
    if currency:
        params["currency"] = currency
    result = await db.execute(
        text(f"""
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', NOW()) - INTERVAL '5 months',
                DATE_TRUNC('month', NOW()),
                INTERVAL '1 month'
            ) AS month_start
        ),
        personal_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS personal
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.user_id = :user_id
              AND t.household_id = :household_id
              AND ts.split_type = 'personal'
              AND t.status NOT IN ('pending', 'orphan')
              AND t.transfer_pair_id IS NULL
              AND t.refund_pair_id IS NULL
              {currency_clause}
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        ),
        shared_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS compartido
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.household_id = :household_id
              AND ts.split_type = 'shared'
              AND t.status NOT IN ('pending', 'orphan')
              AND t.transfer_pair_id IS NULL
              AND t.refund_pair_id IS NULL
              {currency_clause}
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        )
        SELECT
            m.month_start,
            COALESCE(p.personal, 0) AS personal,
            COALESCE(s.compartido, 0) AS compartido
        FROM months m
        LEFT JOIN personal_agg p ON p.month_start = m.month_start
        LEFT JOIN shared_agg s ON s.month_start = m.month_start
        ORDER BY m.month_start ASC
        """),
        params,
    )
    rows = result.all()
    return [
        {
            "month": f"{MONTH_ABBR[row.month_start.month - 1]} {str(row.month_start.year)[2:]}",
            "personal": float(row.personal),
            "compartido": float(row.compartido),
        }
        for row in rows
    ]


async def get_shared_transactions(
    db: AsyncSession, household_id: uuid.UUID, since: date
) -> list[dict]:
    result = await db.execute(
        select(
            Transaction,
            TransactionSplit,
            BankAccount.bank_name,
            CanonicalMerchant.display_name.label("display_name"),
        )
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .outerjoin(Merchant, Transaction.raw_merchant_name == Merchant.raw_name)
        .outerjoin(CanonicalMerchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= since,
            Transaction.status.notin_(["pending", "orphan"]),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type,
            "bank_name": bank_name or txn.source_bank_name,
            "display_name": display_name,
        }
        for txn, split, bank_name, display_name in rows
    ]


async def update_category(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, category: str | None
) -> bool:
    """Update transaction category. Returns False if the transaction does not exist
    or the user is not an active member of its household — so any household member
    can recategorize a shared Plaid/email transaction, not just the owner."""
    result = await db.execute(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False
    txn.category = category
    mark_user_edited(txn, "category")
    await db.commit()
    # Train merchant data: record this user correction for future suggestions
    if category:
        try:
            await record_category_selection(
                txn.raw_merchant_name, category, db, _get_redis(), user_id=user_id
            )
        except Exception:
            pass  # never block the category save if training fails
    return True


async def update_split_type(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID, split_type: str
) -> bool:
    """Update transaction split type. Any active member of the transaction's
    household can flip personal/shared — single-owner gating broke partner edits."""
    result = await db.execute(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False

    # split_type lives on TransactionSplit, not Transaction — upsert the row
    split_result = await db.execute(
        select(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    )
    split = split_result.scalar_one_or_none()
    if split:
        split.split_type = split_type
        split.decided_by_user_id = user_id
        split.decided_at = datetime.now(timezone.utc)
    else:
        db.add(
            TransactionSplit(
                transaction_id=transaction_id,
                split_type=split_type,
                decided_by_user_id=user_id,
                decided_at=datetime.now(timezone.utc),
            )
        )
    mark_user_edited(txn, "split_type")
    await db.commit()
    return True


def _merchant_name_match_clause(anchor_raw_name: str, anchor_merchant_id: uuid.UUID | None):
    """Return the SQLAlchemy WHERE clause matching siblings for a vendor rename.

    Match rules: case-insensitive equality on `raw_merchant_name` OR (when
    the anchor has one) equality on `merchant_id`. Caller adds the household
    scope and the "exclude self" / "skip user-edited" filters.
    """
    from sqlalchemy import or_

    conds = [func.lower(Transaction.raw_merchant_name) == anchor_raw_name.lower()]
    if anchor_merchant_id is not None:
        conds.append(Transaction.merchant_id == anchor_merchant_id)
    return or_(*conds)


async def get_merchant_name_matching_count(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict | None:
    """Count sibling rows in the caller's household sharing the anchor's
    `raw_merchant_name` (case-insensitive) or `merchant_id`. Excludes the
    anchor itself and any row with `user_edited_fields["merchant_name"]` true.

    Returns None when the caller is not a member of the anchor's household
    (or the anchor doesn't exist) so the router can map to 404.
    """
    anchor = await db.scalar(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if anchor is None:
        return None

    match_clause = _merchant_name_match_clause(anchor.raw_merchant_name, anchor.merchant_id)
    count = await db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.household_id == anchor.household_id,
            Transaction.id != anchor.id,
            match_clause,
            # Skip rows the user already edited — JSONB `->>` returns text.
            func.coalesce(Transaction.user_edited_fields["merchant_name"].astext, "false")
            != "true",
        )
    )
    return {
        "count": int(count or 0),
        "raw_merchant_name": anchor.raw_merchant_name,
        "merchant_id": anchor.merchant_id,
    }


async def update_merchant_name_bulk(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    raw_merchant_name: str | None = None,
    merchant_id: uuid.UUID | None = None,
) -> int | None:
    """Rename the anchor row AND every household sibling currently matching
    the anchor's ORIGINAL `raw_merchant_name` (case-insensitive) or
    `merchant_id`, skipping rows already user-edited.

    Returns the number of rows updated (anchor included), or None when the
    caller is not a household member / the anchor doesn't exist.
    """
    if raw_merchant_name is None and merchant_id is None:
        # No-op; still validate household membership so callers get a 404
        # vs 200 distinction.
        ok = await db.scalar(
            select(Transaction.id)
            .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
            .where(
                Transaction.id == transaction_id,
                HouseholdMember.user_id == user_id,
                HouseholdMember.left_at.is_(None),
            )
        )
        return 0 if ok is not None else None

    anchor = await db.scalar(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if anchor is None:
        return None

    # Capture ORIGINAL anchor values BEFORE any mutation — these are the
    # match keys for sibling discovery. If we used post-update values, the
    # anchor itself would no longer match its own siblings.
    original_raw = anchor.raw_merchant_name
    original_merchant_id = anchor.merchant_id

    match_clause = _merchant_name_match_clause(original_raw, original_merchant_id)
    siblings_q = await db.execute(
        select(Transaction).where(
            Transaction.household_id == anchor.household_id,
            Transaction.id != anchor.id,
            match_clause,
            func.coalesce(Transaction.user_edited_fields["merchant_name"].astext, "false")
            != "true",
        )
    )
    siblings = siblings_q.scalars().all()

    targets = [anchor, *siblings]
    for txn in targets:
        if raw_merchant_name is not None:
            txn.raw_merchant_name = raw_merchant_name
        if merchant_id is not None:
            txn.merchant_id = merchant_id
        mark_user_edited(txn, "merchant_name")

    await db.commit()
    return len(targets)


async def update_merchant_name(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    raw_merchant_name: str | None = None,
    merchant_id: uuid.UUID | None = None,
) -> bool:
    """Rename a transaction's vendor (free-text label and/or global merchants
    reference). Any active member of the transaction's household may rename —
    matching the auth model used for category and split_type.

    Stamps ``user_edited_fields["merchant_name"]`` so the auto-reconciliation
    merge logic never overwrites a user-chosen name. Returns False when the
    transaction does not exist or the caller is not a household member.
    """
    if raw_merchant_name is None and merchant_id is None:
        # Nothing to do — caller passed an empty body. Treat as 404 only if
        # the txn doesn't exist; otherwise it's a no-op success.
        return (
            await db.scalar(
                select(Transaction.id)
                .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
                .where(
                    Transaction.id == transaction_id,
                    HouseholdMember.user_id == user_id,
                    HouseholdMember.left_at.is_(None),
                )
            )
            is not None
        )

    result = await db.execute(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False

    if raw_merchant_name is not None:
        txn.raw_merchant_name = raw_merchant_name
    if merchant_id is not None:
        txn.merchant_id = merchant_id
    mark_user_edited(txn, "merchant_name")
    await db.commit()
    return True


async def update_transaction_date(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    user_id: uuid.UUID,
    transaction_date: date,
) -> bool:
    """Update transaction date. Any active member of the transaction's household
    can edit. The input is a calendar date; we store it as a UTC-midnight
    datetime to match the Plaid/email ingestion convention.

    Stamps ``user_edited_fields["transaction_date"]`` so future re-merges from
    the bank source don't overwrite the user's correction.
    """
    result = await db.execute(
        select(Transaction)
        .join(HouseholdMember, HouseholdMember.household_id == Transaction.household_id)
        .where(
            Transaction.id == transaction_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return False
    txn.transaction_date = datetime.combine(transaction_date, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )
    mark_user_edited(txn, "transaction_date")
    await db.commit()
    return True


async def link_manual_transfer(
    db: AsyncSession,
    txn_id_a: uuid.UUID,
    txn_id_b: uuid.UUID,
    user_id: uuid.UUID,
) -> dict:
    """Manually pair two settled own-account bank transactions as a transfer.

    Use case: the auto-detector missed pairing two own-account legs (e.g. a CC
    bill payment outflow on BoA + the matching inflow on Amex). The user picks
    a counterpart by hand.

    Preconditions (all enforced — fail with ServiceError):
      - both rows exist
      - same household as the caller (caller is an active member)
      - both ``source_type IN ('plaid','connect')`` (bank-only)
      - different ``bank_account_id``
      - opposite signs (sum != one-side absolute value)
      - same currency
      - same user_id (own-account)
      - both have ``transfer_pair_id IS NULL`` AND ``refund_pair_id IS NULL``
      - the two ids must be different

    On success, generates a new ``transfer_pair_id``, sets
    ``transaction_type='transfer'`` on both rows, and stamps
    ``user_edited_fields["transaction_type"]`` so detect_transfers won't try
    to re-pair the legs with anyone else.
    """
    if txn_id_a == txn_id_b:
        raise ServiceError("invalid_action", "A transaction cannot be paired with itself")

    # Verify caller is a member of at least one household; we re-check
    # below that BOTH rows belong to the caller's household.
    result = await db.execute(select(Transaction).where(Transaction.id.in_([txn_id_a, txn_id_b])))
    rows = {r.id: r for r in result.scalars().all()}
    a = rows.get(txn_id_a)
    b = rows.get(txn_id_b)
    if not a or not b:
        raise ServiceError("not_found", "Transaction not found")

    # Both rows must be in a household where the caller is an active member.
    # We do this in one SQL query: both household_ids must be present in the
    # caller's active memberships.
    member_rows = await db.execute(
        select(HouseholdMember.household_id).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    member_household_ids = {row[0] for row in member_rows.all()}
    if a.household_id not in member_household_ids or b.household_id not in member_household_ids:
        raise ServiceError("not_found", "Transaction not found")
    if a.household_id != b.household_id:
        raise ServiceError("invalid_action", "Transactions belong to different households")

    # Both rows must be own-account (same user_id) — transfers represent
    # money the user moves between their own accounts.
    if a.user_id != user_id or b.user_id != user_id:
        raise ServiceError("forbidden", "Manual transfer linking only supports own-account moves")

    # Source must be a bank source on both sides.
    if a.source_type not in ("plaid", "connect") or b.source_type not in ("plaid", "connect"):
        raise ServiceError(
            "invalid_action",
            "Only bank-sourced transactions (Plaid or Connect) can be paired as transfers",
        )

    # Different accounts.
    if a.bank_account_id is None or b.bank_account_id is None:
        raise ServiceError("invalid_action", "Both transactions must have a bank account")
    if a.bank_account_id == b.bank_account_id:
        raise ServiceError("invalid_action", "Both transactions are on the same account")

    # Same currency.
    if (a.currency or "").upper() != (b.currency or "").upper():
        raise ServiceError("invalid_action", "Currency mismatch — cannot pair as transfer")

    # Opposite signs (one positive, one negative; neither zero).
    amt_a = Decimal(str(a.amount))
    amt_b = Decimal(str(b.amount))
    if amt_a == 0 or amt_b == 0:
        raise ServiceError("invalid_action", "Transfer legs cannot have zero amount")
    if (amt_a > 0) == (amt_b > 0):
        raise ServiceError("invalid_action", "Both transactions have the same sign")

    # Neither already paired.
    if a.transfer_pair_id is not None or b.transfer_pair_id is not None:
        raise ServiceError("conflict", "One or both transactions are already paired as transfers")
    if a.refund_pair_id is not None or b.refund_pair_id is not None:
        raise ServiceError("conflict", "One or both transactions are already paired as refunds")

    pair_id = uuid.uuid4()
    a.transfer_pair_id = pair_id
    b.transfer_pair_id = pair_id
    a.transaction_type = "transfer"
    b.transaction_type = "transfer"
    mark_user_edited(a, "transaction_type")
    mark_user_edited(b, "transaction_type")
    await db.commit()
    return {"transfer_pair_id": str(pair_id), "transaction_ids": [str(a.id), str(b.id)]}


async def get_pending_transactions(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """
    Return pending transactions grouped into 3 buckets:
    - awaiting_reconciliation: email/plaid txns still in 'pending' status
      (awaiting bank confirmation or Plaid settlement)
    - needs_classification: connect txns, settled, no category yet
    - unmatched_email: email txns aged out to 'orphan' (migration 039, Task 2.8)
    """
    # Pending rows awaiting bank confirmation or Plaid settlement. Exclude rows
    # already in a transfer or refund pair — the pair is conceptually resolved.
    email_pending_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source.in_(["gmail", "outlook", "plaid"]),
            Transaction.status == "pending",
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    email_pending_rows = email_pending_result.all()

    # Connect transactions needing classification (exclude paired rows — a
    # transfer leg doesn't need a category, a refund pair nets to zero).
    needs_class_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source == "connect",
            Transaction.status == "settled",
            Transaction.category.is_(None),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
        )
        .order_by(Transaction.transaction_date.desc())
    )
    needs_class_rows = needs_class_result.all()

    # Orphaned email transactions (aged out without a Plaid match)
    orphan_result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.source_type == "email",
            Transaction.status == "orphan",
        )
        .order_by(Transaction.orphaned_at.desc().nullslast())
    )
    orphan_rows = orphan_result.all()

    def _pending_to_dict(txn, split, bank_name):
        d = _txn_to_dict(txn, split)
        d["bank_name"] = bank_name or txn.source_bank_name
        return d

    awaiting = [_pending_to_dict(txn, split, bn) for txn, split, bn in email_pending_rows]
    needs_classification = [_pending_to_dict(txn, split, bn) for txn, split, bn in needs_class_rows]
    unmatched_email = [_pending_to_dict(txn, split, bn) for txn, split, bn in orphan_rows]

    return {
        "awaiting_reconciliation": awaiting,
        "needs_classification": needs_classification,
        "unmatched_email": unmatched_email,
    }


async def delete_transaction(
    db: AsyncSession, transaction_id: uuid.UUID, user_id: uuid.UUID
) -> str:
    """
    Hard delete a pending or orphan email transaction.
    Returns: 'deleted', 'not_found', or 'invalid'.
    """
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        return "not_found"
    if txn.source_type != "email" or txn.status not in ("pending", "orphan"):
        return "invalid"
    # If this row is paired (transfer or refund), null the pair_id on any
    # surviving partner rows so they are not left orphaned and can be
    # re-paired by a future detect_transfers / detect_refunds tick.
    if getattr(txn, "transfer_pair_id", None) is not None:
        await db.execute(
            sql_update(Transaction)
            .where(
                Transaction.transfer_pair_id == txn.transfer_pair_id,
                Transaction.id != transaction_id,
            )
            .values(transfer_pair_id=None)
        )
    if getattr(txn, "refund_pair_id", None) is not None:
        await db.execute(
            sql_update(Transaction)
            .where(
                Transaction.refund_pair_id == txn.refund_pair_id,
                Transaction.id != transaction_id,
            )
            .values(refund_pair_id=None)
        )
    # Delete associated splits first to avoid FK violation
    await db.execute(
        sql_delete(TransactionSplit).where(TransactionSplit.transaction_id == transaction_id)
    )
    await db.delete(txn)
    await db.commit()
    return "deleted"


async def is_duplicate_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
    bank_name: str | None = None,
    currency: str | None = None,
) -> bool:
    """
    Two-tier dedup for email transactions:
    1. Same amount + SAME currency + SAME bank within 5 min → duplicate (BChile compra+comprobante)
    2. Same amount + SAME currency + DIFFERENT bank within 24h → duplicate (BofA + PayPal for same charge)

    Tier 1 catches fast duplicates from the same sender.
    Tier 2 catches slow cross-sender duplicates (e.g. PayPal alert hours after BofA alert).
    Currency + bank scoping prevents cross-currency / cross-bank false positives
    (e.g. CLP 2000 and USD 2000 arriving seconds apart are not duplicates).
    Neither blocks legitimate repeat purchases (3 beers at $7 from the same bank).
    """
    now = datetime.now(timezone.utc)

    # Tier 1: same bank, same currency, 5-min window (BChile compra + comprobante)
    fast_cutoff = now - timedelta(minutes=5)
    fast_conds = [
        Transaction.user_id == user_id,
        func.abs(Transaction.amount) == abs(amount),
        Transaction.status == "pending",
        Transaction.created_at >= fast_cutoff,
    ]
    if currency is not None:
        fast_conds.append(Transaction.currency == currency)
    if bank_name is not None:
        fast_conds.append(Transaction.source_bank_name == bank_name)
    fast_result = await db.execute(select(Transaction).where(*fast_conds).limit(1))
    if fast_result.scalar_one_or_none():
        return True

    # Tier 2: different bank, same currency, 5min–24h window
    # (BofA alert followed by a PayPal alert hours later for the same charge).
    # We explicitly exclude the ≤5 min window so two legitimate, unrelated
    # same-amount charges from different banks at roughly the same time
    # are not silently dropped.
    if bank_name:
        slow_cutoff = now - timedelta(hours=24)
        slow_conds = [
            Transaction.user_id == user_id,
            func.abs(Transaction.amount) == abs(amount),
            Transaction.status == "pending",
            Transaction.created_at >= slow_cutoff,
            Transaction.created_at < fast_cutoff,
            Transaction.source_bank_name != bank_name,
        ]
        if currency is not None:
            slow_conds.append(Transaction.currency == currency)
        slow_result = await db.execute(select(Transaction).where(*slow_conds).limit(1))
        if slow_result.scalar_one_or_none():
            return True

    return False


def exclude_from_totals(query):
    """Apply the invariant that transfers, refund pairs, and orphans do not
    contribute to spend/income/budget totals.

    Use this helper whenever aggregating (SUM) over `transactions`. Do NOT use
    it to filter list views — paired rows should remain visible and the
    frontend groups them visually.
    """
    return query.where(
        Transaction.status != "orphan",
        Transaction.transfer_pair_id.is_(None),
        Transaction.refund_pair_id.is_(None),
    )


class ServiceError(Exception):
    """Sentinel for service-layer authorization / state errors.

    `code` maps 1:1 onto an HTTP status in the router (403/404/409/422).
    """

    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


async def get_match_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
    window_days: int = 7,
    limit: int = 20,
    intent: str = "consolidate",
) -> list[dict]:
    """Return ranked candidate bank rows that could match the source row.

    `intent` controls which preconditions apply:

    - ``"consolidate"`` (default): the source row is typically a pending
      email; candidates are bank rows (Plaid or Connect) on the same
      currency, ±2% amount tolerance, same sign, ±window_days, unpaired.
      Used by PendingBlock's "Vincular…" flow to consolidate an email row
      into the matching bank row.

    - ``"transfer"``: the source row is a settled bank tx; candidates are
      bank rows (Plaid or Connect) on a DIFFERENT account, OPPOSITE sign,
      same currency, ±window_days, unpaired, same user (own-account).
      Used by RecentTransactions' "Vincular" flow to manually pair two
      transfer legs the auto-detector missed.

    Authorization: source row must be owned by ``user_id``. Raises
    ServiceError('not_found') otherwise.
    """
    # Load & authorize the pending email row (ownership enforced in SQL).
    pending_result = await db.execute(
        select(Transaction).where(
            Transaction.id == pending_id,
            Transaction.user_id == user_id,
        )
    )
    pending = pending_result.scalar_one_or_none()
    if not pending:
        raise ServiceError("not_found", "Pending transaction not found")

    # Verify the caller is a member of the pending row's household.
    member_result = await db.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == pending.household_id,
            HouseholdMember.user_id == user_id,
            HouseholdMember.left_at.is_(None),
        )
    )
    if not member_result.scalar_one_or_none():
        raise ServiceError("not_found", "Pending transaction not found")

    pending_amount = Decimal(str(pending.amount))
    pending_abs = abs(pending_amount)
    tolerance = pending_abs * Decimal("0.02")
    date_min = pending.transaction_date - timedelta(days=window_days)
    date_max = pending.transaction_date + timedelta(days=window_days)

    if intent == "transfer":
        # Manual transfer-pair candidates: opposite sign, different account,
        # same currency, both bank-sourced, both unpaired, own-account.
        # The amount-similarity tolerance is computed against the OPPOSITE
        # sign value (we expect the counterpart leg to ~negate this row).
        target_amount = -pending_amount
        result = await db.execute(
            select(Transaction, BankAccount.bank_name, BankAccount.account_name)
            .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
            .where(
                Transaction.user_id == user_id,
                Transaction.household_id == pending.household_id,
                Transaction.currency == pending.currency,
                Transaction.source_type.in_(["plaid", "connect"]),
                Transaction.status.in_(["pending", "settled"]),
                Transaction.transfer_pair_id.is_(None),
                Transaction.refund_pair_id.is_(None),
                Transaction.bank_account_id != pending.bank_account_id,
                Transaction.id != pending.id,
                Transaction.transaction_date >= date_min,
                Transaction.transaction_date <= date_max,
                func.abs(Transaction.amount - target_amount) <= tolerance,
            )
        )
        rows = result.all()

        def _rank_transfer(row):
            txn = row[0]
            date_delta = abs((txn.transaction_date - pending.transaction_date).total_seconds())
            amount_delta = abs(Decimal(str(txn.amount)) - target_amount)
            return (date_delta, amount_delta)

        ranked = sorted(rows, key=_rank_transfer)[:limit]
        return [
            {
                "id": txn.id,
                "bank_account_id": txn.bank_account_id,
                "bank_account_name": account_name or bank_name,
                "transaction_date": txn.transaction_date,
                "amount": txn.amount,
                "currency": txn.currency,
                "raw_merchant_name": txn.raw_merchant_name,
                "category": txn.category,
                "status": txn.status,
            }
            for txn, bank_name, account_name in ranked
        ]

    result = await db.execute(
        select(Transaction, BankAccount.bank_name, BankAccount.account_name)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == pending.household_id,
            Transaction.currency == pending.currency,
            Transaction.source.in_(["plaid", "connect"]),
            Transaction.status.in_(["pending", "settled"]),
            Transaction.transfer_pair_id.is_(None),
            Transaction.refund_pair_id.is_(None),
            Transaction.transaction_date >= date_min,
            Transaction.transaction_date <= date_max,
            func.abs(Transaction.amount - pending_amount) <= tolerance,
        )
    )
    rows = result.all()

    def _rank(row):
        txn = row[0]
        date_delta = abs((txn.transaction_date - pending.transaction_date).total_seconds())
        amount_delta = abs(Decimal(str(txn.amount)) - pending_amount)
        return (date_delta, amount_delta)

    ranked = sorted(rows, key=_rank)[:limit]

    return [
        {
            "id": txn.id,
            "bank_account_id": txn.bank_account_id,
            "bank_account_name": account_name or bank_name,
            "transaction_date": txn.transaction_date,
            "amount": txn.amount,
            "currency": txn.currency,
            "raw_merchant_name": txn.raw_merchant_name,
            "category": txn.category,
            "status": txn.status,
        }
        for txn, bank_name, account_name in ranked
    ]


async def link_email_to_bank(
    db: AsyncSession,
    user_id: uuid.UUID,
    pending_id: uuid.UUID,
    bank_tx_id: uuid.UUID,
) -> dict:
    """Manually link a pending email row to a bank row (pending or settled).

    Enforces user_id ownership on BOTH rows in SQL. Returns the enriched bank
    transaction as a dict. Raises ServiceError with code:
      - 'not_found'     — either row is missing
      - 'forbidden'     — either row is owned by a different user
      - 'conflict'      — bank row already paired (transfer_pair_id or refund_pair_id)
    """
    from modules.reconciliation.dedup import apply_match_and_delete_emails, _extract_enrichment

    # Atomically load both rows and check ownership in the same SQL call.
    result = await db.execute(
        select(Transaction).where(Transaction.id.in_([pending_id, bank_tx_id]))
    )
    rows = {r.id: r for r in result.scalars().all()}
    pending = rows.get(pending_id)
    bank = rows.get(bank_tx_id)
    if not pending or not bank:
        raise ServiceError("not_found", "Transaction not found")
    if pending.user_id != user_id or bank.user_id != user_id:
        raise ServiceError("forbidden", "Not owner of transaction")
    if bank.transfer_pair_id is not None or bank.refund_pair_id is not None:
        raise ServiceError("conflict", "Bank transaction already paired")

    # User explicitly chose to link this email to this bank row — that's a user
    # decision on every populated field. Stamp markers on the email row so the
    # merge pipeline carries them onto the bank row (and any future re-merge of
    # the bank row respects them).
    edited_fields: list[str] = []
    if pending.category:
        edited_fields.append("category")
    if pending.transaction_type and pending.transaction_type != "expense":
        edited_fields.append("transaction_type")
    if pending.transfer_to_account_id:
        edited_fields.append("transfer_to_account_id")
    if edited_fields:
        mark_user_edited(pending, *edited_fields)
        await db.flush()

    enrichment = await _extract_enrichment(db, pending.id)
    await apply_match_and_delete_emails(
        db,
        bank_tx_id=bank.id,
        email_tx_ids=[pending.id],
        enrichment=enrichment,
        user_id=user_id,
    )

    # When the user vincula a transfer-typed pending, try to auto-pair the
    # newly-typed bank tx with its twin on another account (e.g., AmEx payment
    # email linked to BofA's outgoing leg should ALSO rope in the AmEx card's
    # incoming leg). Targeted to this one tx to avoid re-pairing unrelated rows.
    if enrichment.get("transaction_type") == "transfer":
        from modules.reconciliation.transfers import pair_transfer_twin

        await pair_transfer_twin(db, bank.id)

    await db.commit()

    # Reload the bank tx with enrichment applied.
    refreshed = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(Transaction.id == bank.id)
    )
    row = refreshed.one_or_none()
    if not row:
        raise ServiceError("not_found", "Bank transaction vanished after link")
    txn, split, bank_name = row
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": bank_name or txn.source_bank_name,
        "account_kind": None,
        "display_name": None,
    }


async def dismiss_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> None:
    """Mark a pending transaction as orphan (user-dismissed).

    Enforces user_id ownership in SQL. Raises ServiceError with code:
      - 'not_found' — row missing
      - 'forbidden' — row owned by another user
      - 'conflict'  — row is already orphan or not in 'pending' status
    """
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    txn = result.scalar_one_or_none()
    if not txn:
        raise ServiceError("not_found", "Transaction not found")
    if txn.user_id != user_id:
        raise ServiceError("forbidden", "Not owner of transaction")
    if txn.status == "orphan":
        raise ServiceError("conflict", "Transaction already dismissed")
    if txn.status != "pending":
        raise ServiceError("conflict", "Only pending transactions can be dismissed")

    await db.execute(
        sql_update(Transaction)
        .where(Transaction.id == transaction_id, Transaction.user_id == user_id)
        .values(
            status="orphan",
            orphaned_at=datetime.now(timezone.utc),
            dismissed_by_user=True,
        )
    )
    await db.commit()


async def bulk_action(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_ids: list[uuid.UUID],
    action: str,
) -> int:
    """Bulk 'dismiss' or 'delete' a set of caller-owned transactions.

    All-or-nothing: if ANY id is missing or owned by a different user, raises
    ServiceError('forbidden') and performs NO side effects. Caps at 100 ids —
    raises ServiceError('too_many') above that.
    """
    if action not in ("dismiss", "delete"):
        raise ServiceError("invalid_action", "action must be 'dismiss' or 'delete'")
    if len(transaction_ids) == 0:
        return 0
    if len(transaction_ids) > 100:
        raise ServiceError("too_many", "Maximum 100 ids per bulk action")

    # Ownership check in a single SQL call.
    owned_result = await db.execute(
        select(Transaction.id).where(
            Transaction.id.in_(transaction_ids),
            Transaction.user_id == user_id,
        )
    )
    owned_ids = {row[0] for row in owned_result.all()}
    if len(owned_ids) != len(set(transaction_ids)):
        raise ServiceError("forbidden", "One or more transactions not owned by caller")

    if action == "dismiss":
        await db.execute(
            sql_update(Transaction)
            .where(
                Transaction.id.in_(transaction_ids),
                Transaction.user_id == user_id,
            )
            .values(
                status="orphan",
                orphaned_at=datetime.now(timezone.utc),
                dismissed_by_user=True,
            )
        )
    else:  # delete
        # Null pair_ids on surviving partner rows BEFORE deletion so they
        # don't end up orphaned and can be re-paired later. Scope each UPDATE
        # to rows that share a pair_id with one of the to-be-deleted ids,
        # excluding the to-be-deleted ids themselves.
        for pair_col in (Transaction.transfer_pair_id, Transaction.refund_pair_id):
            pair_ids_subq = (
                select(pair_col)
                .where(
                    Transaction.id.in_(transaction_ids),
                    pair_col.is_not(None),
                )
                .scalar_subquery()
            )
            await db.execute(
                sql_update(Transaction)
                .where(
                    pair_col.in_(pair_ids_subq),
                    Transaction.id.not_in(transaction_ids),
                )
                .values({pair_col: None})
            )
        # Clear child splits first to respect FK.
        await db.execute(
            sql_delete(TransactionSplit).where(TransactionSplit.transaction_id.in_(transaction_ids))
        )
        await db.execute(
            sql_delete(Transaction).where(
                Transaction.id.in_(transaction_ids),
                Transaction.user_id == user_id,
            )
        )
    await db.commit()
    return len(transaction_ids)


def _txn_to_dict(txn: Transaction, split: TransactionSplit | None) -> dict:
    """Convert Transaction + optional Split to response dict."""
    return {
        **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
        "split_type": split.split_type if split else None,
        "bank_name": txn.source_bank_name,
        "account_kind": None,
        "display_name": None,
    }
