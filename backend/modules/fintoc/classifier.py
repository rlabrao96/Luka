# backend/modules/fintoc/classifier.py
from dataclasses import dataclass
from enum import Enum
from modules.fintoc.client import FintocTransaction

_TRANSFER_KEYWORDS = {"TRANSFERENCIA", "TRASPASO"}
_DATE_WINDOW_DAYS = 1


class MovementClassification(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    INBOUND_TRANSFER_SKIP = "inbound_transfer_skip"  # inbound leg — skip, don't record


@dataclass
class ClassificationResult:
    classification: MovementClassification
    matched_fintoc_account_id: str | None = None  # set when a household sibling matched


def classify_movement(
    movement: FintocTransaction,
    household_fintoc_ids: list[str],
    all_movements: list[FintocTransaction],
) -> ClassificationResult:
    """
    Classify a Fintoc movement. Returns ClassificationResult with:
    - classification: the movement type
    - matched_fintoc_account_id: the sibling Fintoc account ID if a transfer was detected
      (callers use this to resolve bank_accounts.id via DB lookup)
    """
    is_inflow = movement.amount > 0

    # --- Path 1: structured counterparty ID ---
    if (
        movement.counterparty_account_id
        and movement.counterparty_account_id in household_fintoc_ids
    ):
        cls = (
            MovementClassification.INBOUND_TRANSFER_SKIP
            if is_inflow
            else MovementClassification.TRANSFER
        )
        return ClassificationResult(
            classification=cls, matched_fintoc_account_id=movement.counterparty_account_id
        )

    # --- Path 2: keyword + amount symmetry ---
    description_words = set(movement.description.split())
    has_transfer_keyword = bool(description_words & _TRANSFER_KEYWORDS)

    if has_transfer_keyword:
        mirror_amount = -movement.amount  # opposite sign
        for other in all_movements:
            if other.id == movement.id:
                continue
            if other.account_id == movement.account_id:
                continue  # same account — not a sibling
            if other.amount != mirror_amount:
                continue
            date_delta = abs((movement.transaction_date - other.transaction_date).days)
            if date_delta <= _DATE_WINDOW_DAYS:
                cls = (
                    MovementClassification.INBOUND_TRANSFER_SKIP
                    if is_inflow
                    else MovementClassification.TRANSFER
                )
                return ClassificationResult(
                    classification=cls, matched_fintoc_account_id=other.account_id
                )

    # --- Default ---
    cls = MovementClassification.INCOME if is_inflow else MovementClassification.EXPENSE
    return ClassificationResult(classification=cls)
