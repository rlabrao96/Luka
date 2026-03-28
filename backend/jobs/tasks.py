import logging
import redis.asyncio as aioredis
from core.config import settings
from core.encryption import decrypt_token, encrypt_token
from core.database import AsyncSessionLocal
from modules.email.parser import parse_bank_email
from modules.email.filter import is_financial_email, is_bank_sender
from modules.merchants.service import lookup_merchant
from modules.whatsapp.sender import send_expense_alert
from modules.whatsapp.session import WhatsAppSession, save_session
from modules.transactions.models import Transaction, TransactionSplit, ProcessedWebhook, FailedJob
from modules.auth.models import User
from modules.households.models import BankAccount
from modules.email.factory import get_email_provider
from modules.transactions.service import is_duplicate_transaction
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
    base_url = settings.frontend_url

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

    subject = f"¡{inviter_name} te invitó a unirte a Luka!"

    # Prefer Resend HTTP API (works on Railway where SMTP is blocked)
    if settings.resend_api_key:
        import httpx

        resend_from = "Luka <onboarding@resend.dev>"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": resend_from,
                    "to": [email_to],
                    "subject": subject,
                    "html": html_content,
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Resend API error {resp.status_code}: {resp.text}")
                raise Exception(f"Resend API error: {resp.text}")
            logger.info(f"Invite email sent via Resend to {email_to}")
        return

    # Fallback: SMTP (for local dev)
    if not settings.smtp_host or not settings.smtp_user:
        logger.warning(f"No email provider configured. Would have sent invite to {email_to}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = email_to
    msg.attach(MIMEText("Has sido invitado a Luka.", "plain"))
    msg.attach(MIMEText(html_content, "html"))

    def _send():
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        logger.info(f"Invite email sent via SMTP to {email_to}")
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
        if not user.google_access_token_enc:
            logger.warning("process_email: user %s has no Google tokens stored", user.email)
            return

        try:
            access_token = decrypt_token(user.google_access_token_enc)
            refresh_token = (
                decrypt_token(user.google_refresh_token_enc)
                if user.google_refresh_token_enc
                else ""
            )
        except Exception as e:
            logger.error("process_email: failed to decrypt tokens for %s: %s", user.email, e)
            return

        provider_instance = get_email_provider(
            user, access_token=access_token, refresh_token=refresh_token
        )
        try:
            print(
                f"[PROCESS_EMAIL] fetching emails for {user.email}, history_id={history_id}",
                flush=True,
            )
            emails = await provider_instance.fetch_new_emails(
                str(user.id), history_id=history_id, message_id=message_id
            )
            print(f"[PROCESS_EMAIL] fetched {len(emails)} emails for {user.email}", flush=True)
            for e in emails:
                print(f"[PROCESS_EMAIL] email from={e.sender} subject={e.subject}", flush=True)
        except Exception as e:
            print(f"[PROCESS_EMAIL] fetch_new_emails FAILED: {e}", flush=True)
            if "RefreshError" in type(e).__name__ or "invalid_grant" in str(e).lower():
                logger.warning(
                    "process_email: Google token revoked for %s, clearing tokens", user.email
                )
                user.google_access_token_enc = None
                user.google_refresh_token_enc = None
                await db.commit()
                return
            raise

        # Persist refreshed token if the SDK auto-refreshed
        new_token = provider_instance.get_current_token()
        if new_token and new_token != access_token:
            user.google_access_token_enc = encrypt_token(new_token)
            await db.commit()

        for raw_email in emails:
            try:
                # Deduplicate: skip if we already processed this email
                dedup_key = f"txn_processed:{raw_email.message_id}"
                if await redis_client.get(dedup_key):
                    print(
                        f"[PROCESS_EMAIL] skipping duplicate email {raw_email.message_id}",
                        flush=True,
                    )
                    continue
                await redis_client.set(dedup_key, "1", ex=86400)  # 24h TTL

                # Pre-filter: only process emails from known bank domains
                if not is_bank_sender(raw_email.sender):
                    print(
                        f"[PROCESS_EMAIL] skipping non-bank sender: {raw_email.sender}",
                        flush=True,
                    )
                    continue

                # Pre-filter: skip non-financial emails
                if not is_financial_email(raw_email.subject, raw_email.sender, raw_email.body):
                    continue

                # Parse email
                parsed = parse_bank_email(raw_email.body)
                if not parsed:
                    continue

                # Bank account is optional (not required for email-only users)
                bank_result = await db.execute(
                    select(BankAccount).where(
                        and_(
                            BankAccount.user_id == user.id,
                            BankAccount.is_active,
                        )
                    )
                )
                bank_account = bank_result.scalars().first()

                # Get household — from bank account or user's membership
                household_id = None
                if bank_account:
                    household_id = bank_account.household_id
                else:
                    from modules.households.models import HouseholdMember

                    hm_result = await db.execute(
                        select(HouseholdMember.household_id).where(
                            HouseholdMember.user_id == user.id
                        )
                    )
                    household_id = hm_result.scalar_one_or_none()

                if not household_id:
                    logger.warning("process_email: user %s has no household, skipping", user.email)
                    continue

                # Lookup merchant categories (to provide options via WhatsApp)
                categories = await lookup_merchant(parsed.raw_merchant, db=db, redis=redis_client)

                # Cross-sender dedup: skip if same amount was created in last 5 min
                if await is_duplicate_transaction(db, user.id, parsed.amount):
                    print(
                        f"[PROCESS_EMAIL] skipping duplicate transaction ${parsed.amount} for {user.email}",
                        flush=True,
                    )
                    continue

                txn_status = "settled"

                # Create pending transaction
                txn = Transaction(
                    user_id=user.id,
                    household_id=household_id,
                    bank_account_id=bank_account.id if bank_account else None,
                    raw_merchant_name=parsed.raw_merchant,
                    amount=parsed.amount,
                    transaction_date=parsed.transaction_date,
                    source=provider,
                    status=txn_status,
                    raw_email_text=raw_email.body,
                )

                db.add(txn)
                await db.commit()
                await db.refresh(txn)

                # Add transaction split AFTER commit so txn.id exists
                is_joint = bank_account and bank_account.account_type == "joint"
                if is_joint:
                    # Auto-classify as shared, just ask for category
                    split = TransactionSplit(
                        transaction_id=txn.id,
                        split_type="shared",
                    )
                    db.add(split)
                    await db.commit()

                # Build WhatsApp session
                phone = user.phone_whatsapp
                if not phone:
                    logger.info(
                        "process_email: user %s has no phone, skipping WhatsApp", user.email
                    )
                    continue
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
                    transaction_type=parsed.transaction_type,
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
            if not user.google_access_token_enc:
                logger.warning("renew_mail_watches: user %s has no tokens, skipping", user.email)
                continue
            try:
                from modules.email.factory import get_email_provider

                access_token = decrypt_token(user.google_access_token_enc)
                refresh_token = (
                    decrypt_token(user.google_refresh_token_enc)
                    if user.google_refresh_token_enc
                    else ""
                )
                provider = get_email_provider(
                    user, access_token=access_token, refresh_token=refresh_token
                )
                watch_result = await provider.renew_watch(str(user.id))

                # Persist updated expiry from renewed watch
                user.mail_watch_subscription_id = watch_result.get("subscription_id")
                expiry_ms = watch_result.get("expiry")
                if expiry_ms:
                    user.mail_watch_expiry = datetime.fromtimestamp(
                        int(expiry_ms) / 1000, tz=timezone.utc
                    )

                # Persist refreshed token if changed
                new_token = provider.get_current_token()
                if new_token and new_token != access_token:
                    user.google_access_token_enc = encrypt_token(new_token)

                await db.commit()
            except Exception as e:
                if "RefreshError" in type(e).__name__ or "invalid_grant" in str(e).lower():
                    logger.warning("renew_mail_watches: Google token revoked for %s", user.email)
                    user.google_access_token_enc = None
                    user.google_refresh_token_enc = None
                    await db.commit()
                    continue
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


async def schedule_connect_syncs(ctx: dict) -> None:
    """Hourly cron: find users due for sync, enqueue run_connect_sync for each."""
    async with AsyncSessionLocal() as db:
        from modules.bank_connect.scheduler import get_due_syncs

        due = await get_due_syncs(db)
        redis = ctx["redis"]  # ArqRedis pool from worker startup
        for cred in due:
            await redis.enqueue_job(
                "run_connect_sync",
                str(cred.id),
            )
        if due:
            print(f"[SCHEDULE_CONNECT_SYNCS] Enqueued {len(due)} syncs", flush=True)


async def run_connect_sync(ctx: dict, credential_id: str) -> None:
    """Run a single bank sync: decrypt creds, send WhatsApp 2FA nudge, call Luka Connect."""
    from modules.bank_connect.models import BankCredential
    from modules.bank_connect.service import trigger_sync
    from modules.whatsapp.sender import send_text
    from modules.auth.models import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BankCredential).where(BankCredential.id == credential_id))
        cred = result.scalar_one_or_none()
        if not cred:
            return

        # Banks that require 2FA approval during scrape
        BANKS_WITH_2FA = {
            "bestado",
            "bci",
            "santander",
            "itau",
            "scotiabank",
            "bice",
            "falabella",
            "edwards",
        }

        # Send WhatsApp 2FA nudge only for banks that require it
        if cred.bank_code in BANKS_WITH_2FA:
            user_result = await db.execute(select(User).where(User.id == cred.user_id))
            user = user_result.scalar_one_or_none()
            if user and user.phone_whatsapp:
                await send_text(
                    to=user.phone_whatsapp,
                    body=(
                        "Luka está sincronizando tu banco. "
                        "Aprueba la Clave Dinámica en tu app del banco."
                    ),
                )

        # Trigger async scrape with callback
        callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
        await trigger_sync(db=db, cred=cred, mode="recent", callback_url=callback_url)


async def _record_failed_job(job_name: str, payload: dict, error: str, db) -> None:
    """Helper to log failed job to database."""
    db.add(FailedJob(job_name=job_name, payload=payload, error_message=error))
    await db.commit()


async def refresh_subscriptions_cache(ctx: dict) -> None:
    """Daily cron: recompute subscription detection for all active users."""
    from modules.subscriptions.service import _compute_and_cache

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User.id))
        user_ids = [row[0] for row in result.all()]
        logger.info("Refreshing subscriptions cache for %d users", len(user_ids))
        for uid in user_ids:
            try:
                await _compute_and_cache(db, uid)
            except Exception:
                logger.warning("Failed to refresh subscriptions for user %s", uid, exc_info=True)
