import uuid
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households.auth import require_membership
from modules.transactions import service
from modules.transactions.schemas import (
    TransactionResponse,
    CategoryUpdateRequest,
    SplitTypeUpdateRequest,
    MerchantNameUpdateRequest,
    PendingTransactionsResponse,
    MatchCandidate,
    LinkRequest,
    BulkActionRequest,
    BulkActionResponse,
    TransactionDateUpdateRequest,
    LinkTransferRequest,
    LinkReimbursementRequest,
)


_SERVICE_ERROR_STATUS = {
    "not_found": 404,
    "forbidden": 403,
    "conflict": 409,
    "too_many": 422,
    "invalid_action": 422,
}


def _raise_from_service_error(err: service.ServiceError) -> None:
    raise HTTPException(_SERVICE_ERROR_STATUS.get(err.code, 400), str(err))


router = APIRouter(prefix="/transactions", tags=["transactions"])


def _default_since() -> date:
    return date.today() - relativedelta(months=6)


@router.get("/mine", response_model=list[TransactionResponse])
async def my_transactions(
    since: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(db, current_user.id, since=since or _default_since())


@router.get("/monthly-summary")
async def monthly_summary(
    household_id: uuid.UUID,
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_monthly_summary(db, household_id, current_user.id, currency=currency)


@router.get("/shared", response_model=list[TransactionResponse])
async def shared_transactions(
    household_id: uuid.UUID,
    since: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    return await service.get_shared_transactions(db, household_id, since=since or _default_since())


@router.get("/pending", response_model=PendingTransactionsResponse)
async def pending_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_pending_transactions(db, current_user.id)


@router.patch("/{transaction_id}/category")
async def update_category(
    transaction_id: uuid.UUID,
    body: CategoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_category(db, transaction_id, current_user.id, body.category)
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


@router.patch("/{transaction_id}/split-type")
async def update_split_type(
    transaction_id: uuid.UUID,
    body: SplitTypeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_split_type(db, transaction_id, current_user.id, body.split_type)
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


@router.patch("/{transaction_id}/transaction-date")
async def update_transaction_date(
    transaction_id: uuid.UUID,
    body: TransactionDateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_transaction_date(
        db, transaction_id, current_user.id, body.transaction_date
    )
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


@router.post("/{transaction_id}/link-transfer")
async def link_manual_transfer_endpoint(
    transaction_id: uuid.UUID,
    body: LinkTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.link_manual_transfer(
            db, transaction_id, body.counterpart_id, current_user.id
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)


@router.patch("/{transaction_id}/merchant-name")
async def update_merchant_name(
    transaction_id: uuid.UUID,
    body: MerchantNameUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    found = await service.update_merchant_name(
        db,
        transaction_id,
        current_user.id,
        raw_merchant_name=body.raw_merchant_name,
        merchant_id=body.merchant_id,
    )
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_action_endpoint(
    body: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        processed = await service.bulk_action(
            db, current_user.id, body.transaction_ids, body.action
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)
    return {"processed": processed}


@router.get("/{pending_id}/match-candidates", response_model=list[MatchCandidate])
async def match_candidates(
    pending_id: uuid.UUID,
    window_days: int = Query(default=7, ge=1, le=365),
    intent: str = Query(default="consolidate", pattern="^(consolidate|transfer|reimbursement)$"),
    q: str | None = Query(default=None, max_length=80),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.get_match_candidates(
            db,
            current_user.id,
            pending_id,
            window_days=window_days,
            intent=intent,
            q=q,
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)


@router.post("/{transaction_id}/link-reimbursement")
async def link_reimbursement_endpoint(
    transaction_id: uuid.UUID,
    body: LinkReimbursementRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.link_reimbursement_group(
            db, transaction_id, body.counterpart_ids, current_user.id
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)


@router.delete("/reimbursement-group/{group_id}")
async def unlink_reimbursement_endpoint(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.unlink_reimbursement_group(db, group_id, current_user.id)
    except service.ServiceError as err:
        _raise_from_service_error(err)


@router.post("/{pending_id}/link")
async def link_transaction(
    pending_id: uuid.UUID,
    body: LinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await service.link_email_to_bank(
            db, current_user.id, pending_id, body.bank_transaction_id
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)


@router.post("/{transaction_id}/dismiss")
async def dismiss_transaction_endpoint(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await service.dismiss_transaction(db, current_user.id, transaction_id)
    except service.ServiceError as err:
        _raise_from_service_error(err)
    return {"ok": True}


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await service.delete_transaction(db, transaction_id, current_user.id)
    if result == "not_found":
        raise HTTPException(404, "Transaction not found")
    if result == "invalid":
        raise HTTPException(400, "Only pending email transactions can be deleted")
