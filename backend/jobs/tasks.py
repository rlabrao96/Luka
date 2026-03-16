import redis.asyncio as aioredis
from core.config import settings
from core.database import AsyncSessionLocal
from modules.email.parser import parse_bank_email
from modules.merchants.service import lookup_merchant
from modules.whatsapp.sender import send_expense_alert
from modules.whatsapp.session import WhatsAppSession, save_session
from modules.transactions.models import Transaction, TransactionSplit, ProcessedWebhook, FailedJob
from modules.auth.models import User
from modules.households.models import BankAccount
from sqlalchemy import select, and_, delete, update
from datetime import datetime, timedelta, timezone


async def process_email(
    ctx: dict,
    provider: str,
    email_address: str = "",
    history_id: str = "",
    message_id: str = "",
    subscription_id: str = "",
) -> None:
    """
    Core pipeline job: fetch email → parse → lookup merchant → send WhatsApp alert.
    Enqueued by Gmail/Outlook webhook endpoints.
    """
    _redis_owned = False
    redis_client = ctx.get("redis")
    if redis_client is None:
        redis_client = await aioredis.from_url(settings.redis_url)
        _redis_owned = True

    async with AsyncSessionLocal() as db:
        # Find user by email (Gmail) or subscription ID (Outlook)
        if email_address:
            result = await db.execute(select(User).where(User.email == email_address))
        else:
            result = await db.execute(
                select(User).where(User.mail_watch_subscription_id == subscription_id)
            )
        user = result.scalar_one_or_none()
        if not user or not user.whatsapp_verified:
            return  # can't send WhatsApp without verified number

        # Fetch email from provider
        from modules.email.factory import get_email_provider

        # Access token retrieved from Supabase Vault in production
        # For now, use a placeholder — Vault integration added in Plan 3
        provider_instance = get_email_provider(user, access_token="", refresh_token="")
        emails = await provider_instance.fetch_new_emails(
            str(user.id), history_id=history_id, message_id=message_id
        )

        for raw_email in emails:
            try:
                # Check bank account email_sender_pattern
                bank_result = await db.execute(
                    select(BankAccount).where(
                        and_(
                            BankAccount.user_id == user.id,
                            BankAccount.is_active,
                        )
                    )
                )
                bank_account = bank_result.scalars().first()
                if not bank_account:
                    continue  # no registered bank account yet, skip

                # Parse email
                parsed = parse_bank_email(raw_email.body)
                if not parsed:
                    continue

                # Lookup merchant categories (to provide options via WhatsApp)
                categories = await lookup_merchant(parsed.raw_merchant, db=db, redis=redis_client)

                # Create pending transaction
                txn = Transaction(
                    user_id=user.id,
                    household_id=bank_account.household_id,
                    bank_account_id=bank_account.id,
                    raw_merchant_name=parsed.raw_merchant,
                    amount=parsed.amount,
                    transaction_date=parsed.transaction_date,
                    source=provider,
                    status="pending",
                    raw_email_text=raw_email.body,
                )

                db.add(txn)
                await db.commit()
                await db.refresh(txn)

                # Add transaction split AFTER commit so txn.id exists
                is_joint = bank_account.account_type == "joint"
                if is_joint:
                    # Auto-classify as shared, just ask for category
                    split = TransactionSplit(
                        transaction_id=txn.id,
                        split_type="shared",
                    )
                    db.add(split)
                    await db.commit()

                # Build WhatsApp session
                # Retrieve phone from Supabase Vault (placeholder)
                phone = "+56900000000"  # TODO: retrieve from Vault in Plan 3
                session = WhatsAppSession(
                    transaction_id=str(txn.id),
                    step="awaiting_category" if is_joint else "awaiting_split",
                    raw_merchant=parsed.raw_merchant,
                )
                await save_session(phone, session, redis_client)

                # Send WhatsApp message
                await send_expense_alert(
                    to=phone,
                    amount=parsed.amount,
                    merchant=parsed.raw_merchant,
                    partner_name="tu pareja",
                    is_joint=is_joint,
                    categories=categories,
                )
            except Exception as e:
                await _record_failed_job(
                    "process_email", {"email_address": email_address}, str(e), db
                )
                continue

    if _redis_owned:
        await redis_client.aclose()


async def renew_mail_watches(ctx: dict) -> None:
    """Daily job: renew Gmail (7d) and Outlook (~3d) subscriptions."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
        result = await db.execute(
            select(User).where(
                and_(User.mail_watch_expiry.isnot(None), User.mail_watch_expiry <= cutoff)
            )
        )
        users = result.scalars().all()
        for user in users:
            try:
                from modules.email.factory import get_email_provider

                provider = get_email_provider(user, access_token="")
                await provider.renew_watch(str(user.id))
            except Exception as e:
                await _record_failed_job(
                    "renew_mail_watches", {"user_id": str(user.id)}, str(e), db
                )


async def purge_raw_emails(ctx: dict) -> None:
    """Hourly job: clear raw_email_text after 24h."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        await db.execute(
            update(Transaction)
            .where(
                and_(
                    Transaction.raw_email_text.isnot(None),
                    Transaction.created_at < cutoff,
                )
            )
            .values(raw_email_text=None)
        )
        await db.commit()


async def cleanup_processed_webhooks(ctx: dict) -> None:
    """Daily job: delete idempotency records older than 7 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await db.execute(delete(ProcessedWebhook).where(ProcessedWebhook.processed_at < cutoff))
        await db.commit()


async def run_fintoc_sync(ctx: dict) -> None:
    """Nightly job: fetch settled Fintoc transactions and reconcile with pending."""
    from datetime import date, timedelta
    from modules.fintoc.client import FintocClient
    from modules.fintoc.reconciler import reconcile_transactions
    from modules.households.models import BankAccount
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BankAccount).where(BankAccount.is_active))
        accounts = result.scalars().all()

        for account in accounts:
            if not account.fintoc_link_id:
                continue
            try:
                client = FintocClient(link_token=account.fintoc_link_id)
                transactions = await client.fetch_transactions(
                    account_id=str(account.id),
                    since=date.today() - timedelta(days=7),
                    until=date.today(),
                )
                await reconcile_transactions(
                    transactions, db, user_id=account.user_id, household_id=account.household_id
                )
            except Exception as e:
                await _record_failed_job(
                    "run_fintoc_sync", {"account_id": str(account.id)}, str(e), db
                )


async def _record_failed_job(job_name: str, payload: dict, error: str, db) -> None:
    """Helper to log failed job to database."""
    db.add(FailedJob(job_name=job_name, payload=payload, error_message=error))
    await db.commit()
