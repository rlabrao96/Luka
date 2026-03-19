import logging
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
from modules.fintoc.client import FintocClient
from sqlalchemy import select, and_, delete, update
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio

logger = logging.getLogger(__name__)


async def send_invite_email(
    ctx: dict,
    email_to: str,
    token: str,
    inviter_name: str,
    household_name: str,
) -> None:
    # Ensure Vercel URL is used for testing if running locally
    base_url = settings.frontend_url
    if "localhost" in base_url or "127.0.0.1" in base_url:
        base_url = "https://luka-lovat.vercel.app"

    invite_url = f"{base_url}/invite/{token}"
    bg_image_url = f"{base_url}/background.jpg"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
            <tr>
                <td style="padding: 0; height: 180px; position: relative;">
                    <!-- Use max-width 100% to fill exactly the 500px width -->
                    <img src="{bg_image_url}" alt="Luka Background" width="100%" style="display: block; width: 100%; height: 180px; object-fit: cover;" />
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px; text-align: center;">
                    <h1 style="color: #111827; margin-top: 0; font-size: 26px; font-weight: 800;">¡Hola! Tienes una invitación 🎉</h1>
                    
                    <p style="color: #4b5563; font-size: 16px; line-height: 1.6; text-align: left; margin-top: 24px;">
                        <strong>{inviter_name}</strong> te ha invitado a unirte al hogar <b>"{household_name}"</b> en <strong>Luka</strong>.
                    </p>
                    
                    <div style="background-color: #f9fafb; border-left: 4px solid #4f46e5; padding: 16px; margin: 24px 0; border-radius: 0 8px 8px 0; text-align: left;">
                        <h3 style="color: #374151; font-size: 14px; margin-top: 0; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em;">¿Qué es Luka?</h3>
                        <p style="color: #6b7280; font-size: 14px; margin: 0; line-height: 1.5;">
                            Luka es la plataforma inteligente para gestionar las finanzas de tu hogar. 
                            Con Luka podrán conectar sus cuentas bancarias, categorizar gastos automáticamente, 
                            y dividirlos de forma justa directamente desde WhatsApp. ¡Dile adiós al Excel!
                        </p>
                    </div>

                    <div style="margin: 40px 0 20px 0;">
                        <a href="{invite_url}" style="background-color: #111827; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block;">
                            Aceptar Invitación y Unirme
                        </a>
                    </div>
                    
                    <p style="color: #9ca3af; font-size: 13px; text-align: center; margin-top: 30px;">
                        ¿El botón no responde? Copia este enlace en tu navegador:<br>
                        <a href="{invite_url}" style="color: #4f46e5; text-decoration: underline;">{invite_url}</a>
                    </p>
                </td>
            </tr>
            <tr>
                <td style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="color: #9ca3af; font-size: 12px; margin: 0;">© 2026 Luka App. Todos los derechos reservados.</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"¡{inviter_name} te invitó a unirte a Luka!"
    msg["From"] = settings.smtp_user or "noreply@luka.app"
    msg["To"] = email_to

    msg.attach(
        MIMEText(
            "Has sido invitado a Luka. Revisa este correo en un cliente que soporte HTML.", "plain"
        )
    )
    msg.attach(MIMEText(html_content, "html"))

    if not settings.smtp_host or not settings.smtp_user:
        logger.warning(f"SMTP not configured. Would have sent invite to {email_to}")
        return

    def _send():
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        logger.info(f"Invite email sent successfully to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send invite email to {email_to}: {e}")
        raise e


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
            if not account.fintoc_link_id or not account.fintoc_account_id:
                continue
            try:
                client = FintocClient(link_token=account.fintoc_link_id)
                transactions = await client.fetch_transactions(
                    account_id=account.fintoc_account_id,
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


async def import_fintoc_history(ctx: dict, bank_account_id: str) -> None:
    """
    One-shot job: import 90 days of Fintoc transactions for a bank account.
    Triggered when a user connects a bank account via Fintoc Link.
    Idempotent: skips any transaction whose fintoc_id already exists in the DB.
    """
    from datetime import date

    split_map = {
        "personal": "personal",
        "partner": "partner",
        "joint": "shared",
    }

    async with AsyncSessionLocal() as db:
        account = await db.get(BankAccount, bank_account_id)
        if not account or not account.fintoc_link_id or not account.fintoc_account_id:
            return

        account.import_status = "importing"
        await db.commit()
        await db.refresh(account)

        try:
            client = FintocClient(link_token=account.fintoc_link_id)
            fintoc_txns = await client.fetch_transactions(
                account_id=account.fintoc_account_id,
                since=date.today() - timedelta(days=90),
                until=date.today(),
            )

            imported = 0
            skipped = 0

            for ftxn in fintoc_txns:
                existing = await db.scalar(
                    select(Transaction).where(Transaction.fintoc_id == ftxn.id)
                )
                if existing:
                    skipped += 1
                    continue

                try:
                    txn = Transaction(
                        user_id=account.user_id,
                        household_id=account.household_id,
                        bank_account_id=account.id,
                        raw_merchant_name=ftxn.description,
                        amount=ftxn.amount,
                        currency="CLP",
                        transaction_date=ftxn.transaction_date,
                        source="fintoc",
                        status="settled",
                        fintoc_id=ftxn.id,
                    )
                    db.add(txn)
                    await db.flush()

                    split = TransactionSplit(
                        transaction_id=txn.id,
                        split_type=split_map.get(account.account_type, "personal"),
                        decided_by_user_id=account.user_id,
                        decided_at=datetime.now(timezone.utc),
                    )
                    db.add(split)
                    await db.commit()
                    imported += 1
                except Exception as loop_err:
                    await db.rollback()
                    logger.warning(
                        "import_fintoc_history: skipping txn fintoc_id=%s due to error: %s",
                        ftxn.id,
                        loop_err,
                    )
                    skipped += 1

            logger.info(
                "import_fintoc_history: bank_account_id=%s imported=%d skipped=%d",
                bank_account_id,
                imported,
                skipped,
            )

            account.import_status = "done"
            await db.commit()

        except Exception as e:
            logger.error(
                "import_fintoc_history: failed for bank_account_id=%s: %s",
                bank_account_id,
                e,
            )
            # Use a fresh session to write the status update in case current session is invalid
            async with AsyncSessionLocal() as fresh_db:
                failed_account = await fresh_db.get(BankAccount, bank_account_id)
                if failed_account:
                    failed_account.import_status = "failed"
                    await fresh_db.commit()
                await _record_failed_job(
                    "import_fintoc_history",
                    {"bank_account_id": bank_account_id},
                    str(e),
                    fresh_db,
                )
            return


async def _record_failed_job(job_name: str, payload: dict, error: str, db) -> None:
    """Helper to log failed job to database."""
    db.add(FailedJob(job_name=job_name, payload=payload, error_message=error))
    await db.commit()
