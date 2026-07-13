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
    CategoryUpdateResponse,
    CategoryMatchingCountResponse,
    SplitTypeUpdateRequest,
    AttributeRequest,
    MerchantNameUpdateRequest,
    MerchantNameUpdateResponse,
    MerchantNameMatchingCountResponse,
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
    month: str | None = Query(default=None, description="YYYY-MM; overrides since"),
    limit: int | None = Query(default=None, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_my_transactions(
        db, current_user.id, since=since or _default_since(), month=month, limit=limit
    )


@router.get("/unclassified-count")
async def unclassified_count(
    since: date = Query(...),
    until: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await service.count_unclassified(db, current_user.id, since=since, until=until)
    return {"count": count}


@router.post("/reclassify")
async def reclassify(
    since: date = Query(...),
    until: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the automatic classifier over the caller's uncategorized
    transactions in a date range; a merchant_review notification arrives for
    approval when it finishes."""
    return await service.reclassify_unclassified(db, current_user.id, since=since, until=until)


@router.get("/dashboard-summary")
async def dashboard_summary(
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved = currency or current_user.preferred_currency or "CLP"
    return await service.get_dashboard_summary(db, current_user.id, month=month, currency=resolved)


@router.get("/search", response_model=list[TransactionResponse])
async def search_transactions(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=30, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Global search over the caller's transactions (merchant, category, amount).

    Merchant matching uses ILIKE (backed by the pg_trgm index from migration
    039). A numeric query also matches the absolute amount, interpreted both
    as stored minor units and as major units (so "45.00" finds a USD 45.00
    charge stored as 4500).
    """
    return await service.search_transactions(db, current_user.id, q=q, limit=limit)


@router.get("/export")
async def export_transactions_csv(
    month: str | None = Query(default=None, description="YYYY-MM; omit for all history"),
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the caller's transactions as CSV (major units, Excel-friendly)."""
    import csv
    import io

    from fastapi.responses import StreamingResponse
    from sqlalchemy import select

    from modules.currencies.units import to_major_units
    from modules.transactions.models import Transaction, TransactionSplit

    conds = [Transaction.user_id == current_user.id, Transaction.status != "orphan"]
    if month:
        try:
            year, mon = (int(x) for x in month.split("-"))
            start = date(year, mon, 1)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="month must be YYYY-MM")
        end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
        conds += [Transaction.transaction_date >= start, Transaction.transaction_date < end]
    if currency:
        conds.append(Transaction.currency == currency.upper())

    rows = (
        await db.execute(
            select(Transaction, TransactionSplit.split_type)
            .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
            .where(*conds)
            .order_by(Transaction.transaction_date.desc())
        )
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "fecha",
            "comercio",
            "categoria",
            "tipo",
            "split",
            "monto",
            "moneda",
            "estado",
            "fuente",
        ]
    )
    for txn, split_type in rows:
        writer.writerow(
            [
                txn.transaction_date.date().isoformat()
                if hasattr(txn.transaction_date, "date")
                else txn.transaction_date,
                txn.raw_merchant_name,
                txn.category or "",
                txn.transaction_type or "",
                split_type or "",
                str(to_major_units(txn.amount, txn.currency)),
                txn.currency,
                txn.status,
                txn.source_type or "",
            ]
        )

    filename = f"luka-transacciones{('-' + month) if month else ''}.csv"
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly-summary")
async def monthly_summary(
    household_id: uuid.UUID,
    currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    # Never sum across currencies: default to the caller's primary currency.
    resolved = currency or current_user.preferred_currency or "CLP"
    return await service.get_monthly_summary(db, household_id, current_user.id, currency=resolved)


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


@router.get("/por-clasificar")
async def por_clasificar(
    household_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_membership(household_id, current_user.id, db)
    from modules.transactions.classification import list_pending_for_household

    rows = await list_pending_for_household(db, household_id)
    return [
        {
            "id": str(t.id),
            "raw_merchant_name": t.raw_merchant_name,
            "display_name": None,
            "amount": t.amount if isinstance(t.amount, int) else str(t.amount),
            "currency": t.currency,
            "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
            "bank_account_id": str(t.bank_account_id) if t.bank_account_id else None,
        }
        for t in rows
    ]


@router.get(
    "/{transaction_id}/category/matching-count",
    response_model=CategoryMatchingCountResponse,
)
async def category_matching_count(
    transaction_id: uuid.UUID,
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await service.get_category_matching_count(
        db, transaction_id, current_user.id, category
    )
    if result is None:
        raise HTTPException(404, "Transaction not found")
    return result


@router.patch("/{transaction_id}/category", response_model=CategoryUpdateResponse)
async def update_category(
    transaction_id: uuid.UUID,
    body: CategoryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.apply_to_all_matching:
        updated = await service.update_category_bulk(
            db, transaction_id, current_user.id, body.category
        )
        if updated is None:
            raise HTTPException(404, "Transaction not found")
        return {"ok": True, "updated_count": updated}

    found = await service.update_category(db, transaction_id, current_user.id, body.category)
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True, "updated_count": 1}


@router.patch("/{transaction_id}/split-type")
async def update_split_type(
    transaction_id: uuid.UUID,
    body: SplitTypeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        found = await service.update_split_type(
            db, transaction_id, current_user.id, body.split_type
        )
    except service.TransactionAttributedError:
        raise HTTPException(409, "transaction_attributed_use_attribute_endpoints")
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True}


# --------------------------------------------------------------- attribution
# Partner-card charge attribution: hand a charge off to a household partner so
# it counts for THEM (split=partner + a TransactionAttribution row). Literal
# `/attributions/...` routes are declared before the `/{transaction_id}/...`
# param routes so a param can never swallow the `attributions` segment.


@router.post("/attributions/{attribution_id}/reject")
async def reject_attribution(
    attribution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recipient declines a charge handed to them; it reverts to the sender."""
    from modules.transactions import attribution as attr_ops

    try:
        await attr_ops.reject(db, attribution_id, by_user_id=current_user.id)
    except attr_ops.AttributionNotFound:
        raise HTTPException(404, "Attribution not found")
    except attr_ops.AttributionForbidden:
        raise HTTPException(403, "Not the recipient of this attribution")
    await db.commit()
    return {"ok": True}


@router.post("/attributions/{attribution_id}/acknowledge")
async def acknowledge_attribution(
    attribution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recipient confirms a charge handed to them (marks it acknowledged)."""
    from modules.transactions import attribution as attr_ops

    try:
        await attr_ops.acknowledge(db, attribution_id, by_user_id=current_user.id)
    except attr_ops.AttributionNotFound:
        raise HTTPException(404, "Attribution not found")
    except attr_ops.AttributionForbidden:
        raise HTTPException(403, "Not the recipient of this attribution")
    await db.commit()
    return {"ok": True}


@router.post("/{transaction_id}/attribute")
async def attribute_transaction(
    transaction_id: uuid.UUID,
    body: AttributeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hand this charge off to a household partner. With no ``recipient_id`` the
    server resolves the sole other active member (409 ambiguous / 422 none)."""
    from fastapi.responses import JSONResponse
    from sqlalchemy import select

    from modules.households.models import HouseholdMember
    from modules.transactions import attribution as attr_ops
    from modules.transactions.models import Transaction

    txn = (
        await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    ).scalar_one_or_none()
    if txn is None:
        raise HTTPException(404, "Transaction not found")

    # Only the card owner (the charge's owner) may hand it off. Confirm the
    # owner is also still an active household member (defense in depth).
    if txn.household_id is None:
        raise HTTPException(403, "Transaction has no household")
    if txn.user_id != current_user.id:
        raise HTTPException(403, "Only the card owner can attribute this charge")
    await require_membership(txn.household_id, current_user.id, db)

    if body.recipient_id is not None:
        if body.recipient_id == current_user.id:
            raise HTTPException(422, "recipient_not_in_household")
        member = (
            await db.execute(
                select(HouseholdMember.user_id).where(
                    HouseholdMember.household_id == txn.household_id,
                    HouseholdMember.user_id == body.recipient_id,
                    HouseholdMember.left_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if member is None:
            raise HTTPException(422, "recipient_not_in_household")
        recipient = body.recipient_id
    else:
        try:
            recipient = await attr_ops.resolve_recipient(db, txn.household_id, current_user.id)
        except attr_ops.AmbiguousRecipient as err:
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "ambiguous_recipient",
                    "candidates": [str(c) for c in err.candidate_ids],
                },
            )
        if recipient is None:
            raise HTTPException(422, "no_partner_in_household")

    await attr_ops.hand_off(db, txn, sender_id=current_user.id, recipient_id=recipient)
    await db.commit()
    return {"ok": True, "recipient_id": str(recipient)}


@router.delete("/{transaction_id}/attribute")
async def un_attribute_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sender removes a hand-off they created; the charge reverts to them."""
    from modules.transactions import attribution as attr_ops

    try:
        await attr_ops.un_tag(db, transaction_id, by_user_id=current_user.id)
    except attr_ops.AttributionNotFound:
        raise HTTPException(404, "Attribution not found")
    except attr_ops.AttributionForbidden:
        raise HTTPException(403, "Not the sender of this attribution")
    await db.commit()
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


@router.get(
    "/{transaction_id}/merchant-name/matching-count",
    response_model=MerchantNameMatchingCountResponse,
)
async def merchant_name_matching_count(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await service.get_merchant_name_matching_count(db, transaction_id, current_user.id)
    if result is None:
        raise HTTPException(404, "Transaction not found")
    return result


@router.patch("/{transaction_id}/merchant-name", response_model=MerchantNameUpdateResponse)
async def update_merchant_name(
    transaction_id: uuid.UUID,
    body: MerchantNameUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.apply_to_all_matching:
        updated = await service.update_merchant_name_bulk(
            db,
            transaction_id,
            current_user.id,
            raw_merchant_name=body.raw_merchant_name,
            merchant_id=body.merchant_id,
        )
        if updated is None:
            raise HTTPException(404, "Transaction not found")
        return {"ok": True, "updated_count": updated}

    found = await service.update_merchant_name(
        db,
        transaction_id,
        current_user.id,
        raw_merchant_name=body.raw_merchant_name,
        merchant_id=body.merchant_id,
    )
    if not found:
        raise HTTPException(404, "Transaction not found")
    return {"ok": True, "updated_count": 1}


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


# --------------------------------------------------------------- credit-suggestions
# Auto-detected reimbursement candidates from card-issuer credit programs.
# Stored as Notification rows of type "credit_suggestion".


def _credit_suggestion_dto(notif) -> dict:
    p = notif.payload or {}
    return {
        "id": str(notif.id),
        "status": notif.status,
        "title": notif.title,
        "credit_txn_id": p.get("credit_txn_id"),
        "counterpart_txn_id": p.get("counterpart_txn_id"),
        "amount": p.get("amount"),
        "currency": p.get("currency"),
        "merchant_credit_name": p.get("merchant_credit_name"),
        "merchant_counterpart_name": p.get("merchant_counterpart_name"),
        "credit_date": p.get("credit_date"),
        "counterpart_date": p.get("counterpart_date"),
        "bank_account_id": p.get("bank_account_id"),
        "created_at": notif.created_at.isoformat() if notif.created_at else None,
    }


@router.get("/credit-suggestions")
async def list_credit_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    from modules.notifications.models import Notification
    from modules.reconciliation.credit_suggestions import NOTIFICATION_TYPE

    res = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.type == NOTIFICATION_TYPE,
            Notification.status.in_(("unread", "read")),
        )
        .order_by(Notification.created_at.desc())
    )
    return [_credit_suggestion_dto(n) for n in res.scalars().all()]


@router.post("/credit-suggestions/{notification_id}/confirm")
async def confirm_credit_suggestion(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from modules.notifications.models import Notification
    from modules.reconciliation.credit_suggestions import NOTIFICATION_TYPE

    res = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    notif = res.scalar_one_or_none()
    if notif is None:
        raise HTTPException(404, "Suggestion not found")
    if notif.status in ("actioned", "dismissed"):
        raise HTTPException(409, "Suggestion already resolved")

    payload = notif.payload or {}
    credit_id = payload.get("credit_txn_id")
    cp_id = payload.get("counterpart_txn_id")
    if not credit_id or not cp_id:
        raise HTTPException(400, "Suggestion payload is malformed")

    try:
        result = await service.link_reimbursement_group(
            db,
            uuid.UUID(credit_id),
            [uuid.UUID(cp_id)],
            current_user.id,
        )
    except service.ServiceError as err:
        _raise_from_service_error(err)

    notif.status = "actioned"
    notif.read_at = datetime.now(timezone.utc)
    notif.updated_at = datetime.now(timezone.utc)
    payload["confirmed_at"] = notif.read_at.isoformat()
    notif.payload = payload
    await db.commit()
    return result


@router.post("/credit-suggestions/{notification_id}/dismiss")
async def dismiss_credit_suggestion(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime, timezone
    from sqlalchemy import select
    from modules.notifications.models import Notification
    from modules.reconciliation.credit_suggestions import NOTIFICATION_TYPE

    res = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
            Notification.type == NOTIFICATION_TYPE,
        )
    )
    notif = res.scalar_one_or_none()
    if notif is None:
        raise HTTPException(404, "Suggestion not found")

    notif.status = "dismissed"
    notif.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
