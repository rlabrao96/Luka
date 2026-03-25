from dataclasses import dataclass
from datetime import datetime
from rapidfuzz import fuzz
from modules.fintoc.client import FintocTransaction
from modules.merchants.normalizer import normalize_merchant

_DATE_WINDOW_DAYS = 3
_FUZZY_THRESHOLD = 70.0


@dataclass
class ReconcileResult:
    transaction_id: str
    fintoc_id: str
    confidence: float


def find_match(
    fintoc_txn: FintocTransaction,
    pending_transactions: list[dict],
) -> ReconcileResult | None:
    """
    Attempt to match a settled Fintoc transaction against pending DB transactions.
    Matching criteria:
      - Exact amount match
      - Date within ±3 days
      - Fuzzy merchant name similarity > 70
    """
    fintoc_normalized = normalize_merchant(fintoc_txn.description)

    for pending in pending_transactions:
        # 1. Amount must match exactly (fintoc amounts are signed; pending are positive)
        if int(pending["amount"]) != abs(fintoc_txn.amount):
            continue

        # 2. Date within ±3 days
        pending_date = pending["transaction_date"]
        if isinstance(pending_date, str):
            pending_date = datetime.fromisoformat(pending_date)

        delta = abs((fintoc_txn.transaction_date - pending_date).days)
        if delta > _DATE_WINDOW_DAYS:
            continue

        # 3. Fuzzy merchant similarity
        pending_normalized = normalize_merchant(pending["raw_merchant_name"])
        score = fuzz.partial_ratio(fintoc_normalized, pending_normalized)
        if score >= _FUZZY_THRESHOLD:
            return ReconcileResult(
                transaction_id=str(pending["id"]),
                fintoc_id=fintoc_txn.id,
                confidence=score / 100.0,
            )

    return None


async def reconcile_transactions(
    fintoc_transactions: list[FintocTransaction],
    db,
    user_id,
    household_id,
    transaction_types: dict[str, str] | None = None,
) -> dict:
    """
    Run reconciliation for a list of Fintoc settled transactions.
    Returns counts of matched and unmatched.
    """
    from sqlalchemy import select, update
    from modules.transactions.models import Transaction

    result = await db.execute(
        select(Transaction).where(
            Transaction.status == "pending",
            Transaction.user_id == user_id,
            Transaction.household_id == household_id,
        )
    )
    pending = [
        {
            "id": str(t.id),
            "amount": int(t.amount),
            "raw_merchant_name": t.raw_merchant_name,
            "transaction_date": t.transaction_date,
        }
        for t in result.scalars().all()
    ]

    matched = 0
    unmatched = 0

    for ftc_txn in fintoc_transactions:
        match = find_match(ftc_txn, pending)
        if match:
            # Find the bank account for this Fintoc sync
            from modules.households.models import BankAccount as BA

            ba_result = await db.execute(
                select(BA.id)
                .where(
                    BA.user_id == user_id,
                    BA.is_active.is_(True),
                )
                .limit(1)
            )
            ba_id = ba_result.scalar_one_or_none()

            await db.execute(
                update(Transaction)
                .where(Transaction.id == match.transaction_id)
                .values(
                    status="reconciled",
                    fintoc_id=ftc_txn.id,
                    bank_account_id=ba_id,
                )
            )
            matched += 1
            # Remove matched pending to prevent duplicate matching
            pending = [p for p in pending if str(p["id"]) != match.transaction_id]
        else:
            # Insert as new settled transaction from Fintoc
            txn_type = (transaction_types or {}).get(ftc_txn.id, "expense")
            new_txn = Transaction(
                user_id=user_id,
                household_id=household_id,
                raw_merchant_name=ftc_txn.description,
                amount=abs(ftc_txn.amount),
                transaction_date=ftc_txn.transaction_date,
                source="fintoc",
                status="settled",
                fintoc_id=ftc_txn.id,
                transaction_type=txn_type,
            )
            db.add(new_txn)
            unmatched += 1

    await db.commit()
    return {"matched": matched, "unmatched": unmatched}
