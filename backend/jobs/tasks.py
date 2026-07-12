import logging
import redis.asyncio as aioredis
from core.config import settings
from core.encryption import decrypt_token, encrypt_token
from core.database import AsyncSessionLocal
from jobs.queue import enqueue_job
from modules.email.parser import parse_bank_email, _strip_html
from modules.email.bank_registry_service import (
    is_bank_sender as is_bank_sender_async,
    get_bank_metadata,
    is_financial_email as is_financial_email_async,
)
from modules.email.models import ParsedEmailLog
from modules.merchants.service import lookup_merchant
from modules.merchants.normalizer import normalize_merchant
from modules.whatsapp.sender import send_expense_alert, send_transfer_alert
from modules.whatsapp.session import WhatsAppSession, save_session, save_msgid
from modules.transactions.models import Transaction, ProcessedWebhook, FailedJob
from modules.auth.models import User
from modules.households.models import BankAccount
from modules.email.factory import get_email_provider
from modules.transactions.service import is_duplicate_transaction
from modules.merchant_review.llm_grouping import group_raw_merchants
from modules.merchant_review.service import create_canonicals_from_groups
from modules.merchant_review.models import CanonicalMerchant, MerchantReviewJob
from modules.notifications.models import Notification
from sqlalchemy import select, and_, delete, update, text, func
from datetime import datetime, timedelta, timezone
import uuid
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio

logger = logging.getLogger(__name__)


async def _resolve_transfer_to_account_id(db, household_id, card_last_four: str | None):
    """Resolve a card last-4 to a household BankAccount.id, or None if no match.

    Used at email ingest time to eagerly link CC-payment transfers to their
    destination card so reconciliation can match email-sourced rows against
    Plaid-settled rows by card identity. If no BankAccount has
    account_number == card_last_four, the reconciliation tick retries later.
    """
    if not card_last_four or not household_id:
        return None
    result = await db.execute(
        select(BankAccount.id).where(
            and_(
                BankAccount.household_id == household_id,
                BankAccount.account_number == card_last_four,
            )
        )
    )
    return result.scalar_one_or_none()


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
                if not await is_bank_sender_async(raw_email.sender, redis=redis_client, db=db):
                    print(
                        f"[PROCESS_EMAIL] skipping non-bank sender: {raw_email.sender}",
                        flush=True,
                    )
                    continue

                # Pre-filter: skip non-financial emails
                if not is_financial_email_async(
                    raw_email.subject, raw_email.sender, raw_email.body
                ):
                    continue

                # Get bank metadata for LLM context
                bank_meta = await get_bank_metadata(raw_email.sender, redis=redis_client, db=db)

                # Parse email (three-layer: template → LLM → regex)
                stripped = _strip_html(raw_email.body)
                if not stripped.strip():
                    logger.warning(
                        "process_email: empty email body for %s, skipping", raw_email.message_id
                    )
                    continue

                parsed, parser_used, depth, model_used = await parse_bank_email(
                    raw_email.body,
                    stripped,
                    bank_metadata=bank_meta,
                    db=db,
                )
                if not parsed:
                    continue

                # Infer bank name from metadata
                inferred_bank = bank_meta["bank_name"] if bank_meta else "Unknown"

                # Match bank account by inferred name (don't fall back to wrong bank)
                bank_account = None
                if inferred_bank:
                    bank_result = await db.execute(
                        select(BankAccount).where(
                            and_(
                                BankAccount.user_id == user.id,
                                BankAccount.is_active,
                                BankAccount.bank_name == inferred_bank,
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

                # Cross-sender dedup: same bank 5min OR (different bank 24h +
                # similar merchant — round CLP amounts collide constantly).
                if await is_duplicate_transaction(
                    db,
                    user.id,
                    parsed.amount,
                    inferred_bank,
                    currency=parsed.currency,
                    merchant_name=parsed.raw_merchant,
                ):
                    print(
                        f"[PROCESS_EMAIL] skipping duplicate transaction ${parsed.amount} for {user.email}",
                        flush=True,
                    )
                    continue

                txn_status = "pending"
                tx_type = getattr(parsed, "transaction_type", None) or "expense"

                # Store expenses/transfers as negative, income as positive (matches Plaid/Connect convention)
                stored_amount = abs(parsed.amount) if tx_type == "income" else -abs(parsed.amount)

                # Eagerly resolve transfer_to_account_id via card last-4. If no
                # match, leave null — the reconciliation tick will retry later.
                card_last_four = getattr(parsed, "card_last_four", None)
                transfer_to_account_id = await _resolve_transfer_to_account_id(
                    db, household_id, card_last_four
                )

                # Reverse match: did a Plaid pending/settled counterpart land
                # before us? If so, skip the email INSERT and enrich the
                # existing Plaid row in place. Falls back to the original
                # insert path on any lookup failure so ingest never breaks.
                plaid_counterpart = None
                try:
                    from modules.reconciliation.dedup import (
                        consolidate_email_values_into_plaid,
                        find_plaid_match_for_email_values,
                    )

                    plaid_counterpart = await find_plaid_match_for_email_values(
                        db,
                        user_id=user.id,
                        raw_merchant_name=parsed.raw_merchant,
                        amount=stored_amount,
                        currency=parsed.currency,
                        transaction_date=parsed.transaction_date,
                        transaction_type=tx_type,
                        bank_account_id=bank_account.id if bank_account else None,
                        transfer_to_account_id=transfer_to_account_id,
                    )
                except Exception:
                    logger.warning(
                        "process_email: reverse-match lookup failed, falling back to insert",
                        exc_info=True,
                    )
                    plaid_counterpart = None

                if plaid_counterpart is not None:
                    try:
                        await consolidate_email_values_into_plaid(
                            db,
                            plaid_counterpart,
                            transaction_type=tx_type,
                            transfer_to_account_id=transfer_to_account_id,
                        )
                        await db.commit()
                    except Exception:
                        logger.warning(
                            "process_email: consolidate into Plaid failed, falling back to insert",
                            exc_info=True,
                        )
                        plaid_counterpart = None

                if plaid_counterpart is not None:
                    # Enqueue a per-household tick so transfer/refund/wallet
                    # passes pick up the freshly enriched row.
                    try:
                        await enqueue_job(
                            "run_reconciliation_tick_for_household", str(household_id)
                        )
                    except Exception:
                        logger.warning(
                            "process_email: failed to enqueue reconciliation tick",
                            exc_info=True,
                        )
                    continue

                # Create pending transaction
                txn = Transaction(
                    user_id=user.id,
                    household_id=household_id,
                    bank_account_id=bank_account.id if bank_account else None,
                    raw_merchant_name=parsed.raw_merchant,
                    amount=stored_amount,
                    currency=parsed.currency,
                    transaction_date=parsed.transaction_date,
                    source=provider,
                    source_bank_name=inferred_bank,
                    status=txn_status,
                    transaction_type=tx_type,
                    raw_email_text=raw_email.body,
                    card_last_four=card_last_four,
                    transfer_to_account_id=transfer_to_account_id,
                )

                db.add(txn)
                await db.commit()
                await db.refresh(txn)

                # Event-driven tick: nudge reconciliation for this household
                # so any matching Plaid row syncs up promptly without waiting
                # for the daily cron.
                try:
                    await enqueue_job("run_reconciliation_tick_for_household", str(household_id))
                except Exception:
                    logger.warning(
                        "process_email: failed to enqueue reconciliation tick",
                        exc_info=True,
                    )

                # Log parsing result for template training
                log_entry = ParsedEmailLog(
                    user_id=user.id,
                    bank_domain=bank_meta["bank_domain"] if bank_meta else "unknown",
                    country=bank_meta.get("country") if bank_meta else None,
                    raw_email_html=raw_email.body,
                    llm_extraction={
                        "merchant": parsed.raw_merchant,
                        "amount": parsed.amount,
                        "currency": parsed.currency,
                        "date": str(parsed.transaction_date),
                        "type": parsed.transaction_type,
                        "confidence": parsed.confidence,
                    }
                    if parser_used == "llm"
                    else None,
                    template_extraction={
                        "merchant": parsed.raw_merchant,
                        "amount": parsed.amount,
                    }
                    if parser_used == "template"
                    else None,
                    parser_used=parser_used,
                    llm_model_used=model_used,
                    waterfall_depth=depth,
                )
                db.add(log_entry)
                await db.commit()

                # Add transaction split AFTER commit so txn.id exists. Joint accounts
                # auto-classify as shared; everything else defaults to personal.
                from modules.transactions.service import ensure_default_split

                is_joint = bank_account and bank_account.account_type == "joint"
                await ensure_default_split(
                    db, txn, default_split_type="shared" if is_joint else "personal"
                )
                await db.commit()

                # Build WhatsApp session
                phone = user.phone_whatsapp
                if not phone:
                    logger.info(
                        "process_email: user %s has no phone, skipping WhatsApp", user.email
                    )
                    continue

                # Transfers (inter-account, CC payments) get informational message only
                if tx_type == "transfer":
                    msg_id = await send_transfer_alert(
                        to=phone,
                        amount=parsed.amount,
                        merchant=parsed.raw_merchant,
                        currency=parsed.currency,
                    )
                    await save_msgid(msg_id, str(txn.id), redis_client)
                    continue

                session = WhatsAppSession(
                    transaction_id=str(txn.id),
                    step="awaiting_category" if is_joint else "awaiting_split",
                    raw_merchant=parsed.raw_merchant,
                )
                await save_session(phone, session, redis_client)

                # Send WhatsApp message
                msg_id = await send_expense_alert(
                    to=phone,
                    amount=parsed.amount,
                    merchant=parsed.raw_merchant,
                    partner_name="otro miembro",
                    is_joint=is_joint,
                    categories=categories,
                    transaction_type=parsed.transaction_type,
                    currency=parsed.currency,
                )
                await save_msgid(msg_id, str(txn.id), redis_client)
            except Exception as e:
                # Release the dedup marker so a redelivery can retry this email —
                # leaving it set turns any transient failure into a permanently
                # dropped transaction (the marker is written before parsing).
                try:
                    await redis_client.delete(f"txn_processed:{raw_email.message_id}")
                except Exception:
                    logger.warning("process_email: failed to release dedup marker", exc_info=True)
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


async def purge_email_logs(ctx: dict) -> None:
    """Purge raw_email_html from parsed_email_log entries older than 7 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(days=7)
        stmt = (
            update(ParsedEmailLog)
            .where(ParsedEmailLog.created_at < cutoff)
            .where(ParsedEmailLog.raw_email_html.isnot(None))
            .values(raw_email_html=None)
        )
        result = await db.execute(stmt)
        await db.commit()
        logger.info("Purged raw HTML from %d email log entries", result.rowcount)


async def cleanup_processed_webhooks(ctx: dict) -> None:
    """Daily job: delete idempotency records older than 7 days."""
    async with AsyncSessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        await db.execute(delete(ProcessedWebhook).where(ProcessedWebhook.processed_at < cutoff))
        await db.commit()


async def schedule_connect_syncs(ctx: dict) -> None:
    """Every 6h cron: find users due for daily sync, enqueue run_connect_sync for each."""
    async with AsyncSessionLocal() as db:
        from modules.bank_connect.scheduler import get_due_syncs

        due = await get_due_syncs(db)
        for cred in due:
            await enqueue_job("run_connect_sync", str(cred.id))
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

        # Trigger async scrape with callback (only last 4 days for cron syncs)
        callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
        await trigger_sync(db=db, cred=cred, days_back=4, callback_url=callback_url)


async def _record_failed_job(job_name: str, payload: dict, error: str, db) -> None:
    """Helper to log failed job to database."""
    db.add(FailedJob(job_name=job_name, payload=payload, error_message=error))
    await db.commit()


async def subscription_precharge_alerts(ctx: dict) -> None:
    """Daily cron: fan out pre-charge heads-ups for users with detections."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT user_id FROM detected_subscriptions_cache"))
        user_ids = [str(r[0]) for r in result.all()]
    for uid in user_ids:
        await enqueue_job("subscription_precharge_for_user", uid)
    logger.info("subscription_precharge_alerts: enqueued %d users", len(user_ids))


async def subscription_precharge_for_user(ctx: dict, user_id: str) -> None:
    from modules.subscriptions.guardian import send_precharge_alerts_for_user

    async with AsyncSessionLocal() as db:
        try:
            await send_precharge_alerts_for_user(db, user_id)
        except Exception:
            logger.warning("precharge alerts failed for user %s", user_id, exc_info=True)


async def send_monthly_recaps(ctx: dict) -> None:
    """Cron (1st of month): fan out one recap job per user with any activity."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT DISTINCT u.id FROM users u
                JOIN transactions t ON t.user_id = u.id
                WHERE t.transaction_date >= NOW() - INTERVAL '65 days'
            """)
        )
        user_ids = [str(r[0]) for r in result.all()]
    for uid in user_ids:
        await enqueue_job("send_monthly_recap_for_user_job", uid)
    logger.info("send_monthly_recaps: enqueued %d recaps", len(user_ids))


async def send_monthly_recap_for_user_job(ctx: dict, user_id: str) -> None:
    from modules.notifications.monthly_recap import send_monthly_recap_for_user

    async with AsyncSessionLocal() as db:
        try:
            sent = await send_monthly_recap_for_user(db, user_id)
            if sent:
                logger.info("monthly recap sent for user %s", user_id)
        except Exception:
            logger.warning("monthly recap failed for user %s", user_id, exc_info=True)


async def refresh_subscriptions_cache(ctx: dict) -> None:
    """Periodic cron: fan out one per-user refresh job per active user.

    The old version recomputed every user inside this single 60s-capped
    fast-worker job — past ~300 users ARQ killed it mid-run and everyone
    after the cutoff silently kept a stale cache until the next cron
    (~10 days). Fan-out keeps each unit of work well under the timeout.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT DISTINCT u.id FROM users u
                JOIN bank_accounts ba ON ba.user_id = u.id
                WHERE ba.is_active = true
            """)
        )
        user_ids = [str(row[0]) for row in result.all()]

    for uid in user_ids:
        await enqueue_job("refresh_subscriptions_for_user", uid)
    logger.info("refresh_subscriptions_cache: enqueued %d per-user refreshes", len(user_ids))


async def refresh_subscriptions_for_user(ctx: dict, user_id: str) -> None:
    """Triggered after new bank account — recompute subscriptions for one user."""
    from modules.subscriptions.service import _compute_and_store

    async with AsyncSessionLocal() as db:
        try:
            await _compute_and_store(db, user_id)
            logger.info("Refreshed subscriptions for user %s after bank link", user_id)
        except Exception:
            logger.warning("Failed to refresh subscriptions for user %s", user_id, exc_info=True)


async def _count_unverified_for_job(
    db,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    transaction_ids: list | None,
) -> int:
    """Count unverified canonical merchants reachable from a review job.

    Mirrors the scoping logic in `get_review_cards`: prefers the explicit
    transaction_ids scope when present, otherwise falls back to the legacy
    `CanonicalMerchant.review_job_id` linkage.
    """
    from modules.merchants.models import Merchant

    base = (
        select(func.count(func.distinct(CanonicalMerchant.id)))
        .select_from(CanonicalMerchant)
        .join(Merchant, Merchant.canonical_merchant_id == CanonicalMerchant.id)
        .join(Transaction, Transaction.raw_merchant_name == Merchant.raw_name)
        .where(CanonicalMerchant.is_verified.is_(False))
    )
    if transaction_ids:
        tx_uuids = [uuid.UUID(tid) for tid in transaction_ids]
        stmt = base.where(Transaction.id.in_(tx_uuids))
    else:
        stmt = base.where(
            Transaction.user_id == user_id,
            CanonicalMerchant.review_job_id == job_id,
        )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def _find_mergeable_review_notification(
    db,
    user_id: uuid.UUID,
    exclude_job_id: uuid.UUID,
):
    """Find an unactioned merchant_review notification with an in-flight job.

    Returns (Notification, MerchantReviewJob) or None. "Unactioned" means
    status in {unread, read} (not actioned/dismissed) and the linked job has
    not been completed yet (`completed_at IS NULL`). Excludes the job we're
    currently processing so we don't merge a job into itself.
    """
    # Lock the candidate row so two near-simultaneous bank syncs can't both
    # merge into it and silently drop each other's transaction_ids.
    stmt = (
        select(Notification, MerchantReviewJob)
        .join(MerchantReviewJob, MerchantReviewJob.notification_id == Notification.id)
        .where(
            Notification.user_id == user_id,
            Notification.type == "merchant_review",
            Notification.status.in_(("unread", "read")),
            MerchantReviewJob.completed_at.is_(None),
            MerchantReviewJob.id != exclude_job_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
        .with_for_update(of=MerchantReviewJob)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def _finalize_review_notification(db, job: MerchantReviewJob) -> None:
    """Create / update / merge / suppress the merchant_review notification.

    Extracted from `process_merchant_review` so the merging logic can be
    exercised directly from tests without standing up the full ARQ pipeline.

    Rules:
    - If the user has an unactioned merchant_review notification with an
      in-flight job, merge this job into it (re-stamp canonicals, append
      transaction_ids, bump notification, delete this job).
    - Else, if this job already owns a notification (re-run path), update
      its title only when there's something to review.
    - Else, create a new notification only when there's at least one
      unverified canonical.
    """
    from modules.notifications.service import create_notification

    job_id_uuid = job.id
    job_user_id = job.user_id
    job_notification_id = job.notification_id
    job_tx_ids = job.transaction_ids

    unverified_count = await _count_unverified_for_job(db, job_id_uuid, job_user_id, job_tx_ids)

    merge_target = None
    if not job_notification_id:
        merge_target = await _find_mergeable_review_notification(
            db, job_user_id, exclude_job_id=job_id_uuid
        )

    if merge_target is not None:
        existing_notif, existing_job = merge_target
        # Re-stamp newly created canonicals onto the existing job so the
        # legacy `review_job_id` fallback in get_review_cards keeps working
        # for bank-connect-style jobs without transaction_ids.
        await db.execute(
            CanonicalMerchant.__table__.update()
            .where(CanonicalMerchant.review_job_id == job_id_uuid)
            .values(review_job_id=existing_job.id)
        )
        # Merge transaction_ids (de-duped). If either side is None
        # ("all uncategorized" legacy mode), keep None so the broad scope
        # continues to apply.
        if existing_job.transaction_ids is None or job_tx_ids is None:
            existing_job.transaction_ids = None
        else:
            merged_ids = list(dict.fromkeys([*existing_job.transaction_ids, *job_tx_ids]))
            existing_job.transaction_ids = merged_ids
        existing_job.updated_at = datetime.now(timezone.utc)

        # Only bump the notification if THIS job actually contributed new
        # unverified merchants. An empty incoming job leaves the existing
        # notification — and its timestamp/status — untouched.
        if unverified_count > 0:
            merged_unverified = await _count_unverified_for_job(
                db, existing_job.id, job_user_id, existing_job.transaction_ids
            )
            existing_notif.title = f"{merged_unverified} comercios listos para revisar"
            existing_notif.status = "unread"
            existing_notif.read_at = None
            existing_notif.created_at = datetime.now(timezone.utc)
            existing_notif.updated_at = datetime.now(timezone.utc)
            payload = dict(existing_notif.payload or {})
            payload["sync_job_id"] = str(existing_job.id)
            existing_notif.payload = payload

        await db.delete(job)
        return

    if not job_notification_id:
        if unverified_count > 0:
            notif = await create_notification(
                db,
                user_id=job_user_id,
                type="merchant_review",
                title=f"{unverified_count} comercios listos para revisar",
                payload={"sync_job_id": str(job_id_uuid)},
            )
            job.notification_id = notif.id
        # else: suppress empty notifications entirely.
        return

    notif_result = await db.execute(
        select(Notification).where(Notification.id == job_notification_id)
    )
    notif = notif_result.scalar_one_or_none()
    if notif and unverified_count > 0:
        notif.title = f"{unverified_count} comercios listos para revisar"
        notif.updated_at = datetime.now(timezone.utc)


async def process_merchant_review(ctx: dict, job_id: str) -> None:
    """
    ARQ job: Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.
    """
    from modules.merchants.models import Merchant

    async with AsyncSessionLocal() as db:
        redis = aioredis.from_url(settings.redis_url)
        try:
            # Load the review job
            result = await db.execute(
                select(MerchantReviewJob).where(MerchantReviewJob.id == uuid.UUID(job_id))
            )
            job = result.scalar_one_or_none()
            if not job:
                logger.error("Review job %s not found", job_id)
                return

            # Extract values immediately to avoid lazy-load issues in async context
            job_id_uuid = job.id
            job_user_id = job.user_id
            job_notification_id = job.notification_id
            job_tx_ids = job.transaction_ids  # list of UUID strings, or None

            # Collect unique raw merchant names — scoped to specific transactions if available
            if job_tx_ids:
                txn_result = await db.execute(
                    select(Transaction.raw_merchant_name)
                    .where(
                        Transaction.id.in_([uuid.UUID(tid) for tid in job_tx_ids]),
                        Transaction.category.is_(None),
                    )
                    .distinct()
                )
            else:
                txn_result = await db.execute(
                    select(Transaction.raw_merchant_name)
                    .where(
                        Transaction.user_id == job_user_id,
                        Transaction.source_type.in_(["connect", "plaid"]),
                        Transaction.category.is_(None),
                    )
                    .distinct()
                )
            raw_names = [r[0] for r in txn_result.all() if r[0]]

            # Split into known (has canonical) vs new merchants
            names_to_process = []
            known_count = 0
            for name in raw_names:
                mr = await db.execute(select(Merchant).where(Merchant.raw_name == name))
                merchant = mr.scalar_one_or_none()
                if merchant and merchant.canonical_merchant_id:
                    known_count += 1
                    # Backfill category for known merchants missing one
                    canon_result = await db.execute(
                        select(CanonicalMerchant).where(
                            CanonicalMerchant.id == merchant.canonical_merchant_id
                        )
                    )
                    canonical = canon_result.scalar_one_or_none()
                    if canonical and not canonical.default_category:
                        categories = await lookup_merchant(name, db, redis)
                        if categories:
                            canonical.default_category = categories[0]
                    # Pre-apply category to transactions
                    if canonical and canonical.default_category:
                        where_clauses = [
                            Transaction.user_id == job_user_id,
                            Transaction.raw_merchant_name == name,
                            Transaction.category.is_(None),
                        ]
                        if job_tx_ids:
                            where_clauses.append(
                                Transaction.id.in_([uuid.UUID(tid) for tid in job_tx_ids])
                            )
                        await db.execute(
                            Transaction.__table__.update()
                            .where(*where_clauses)
                            .values(category=canonical.default_category)
                        )
                else:
                    names_to_process.append(name)
                    if not merchant:
                        db.add(
                            Merchant(
                                raw_name=name,
                                normalized_name=normalize_merchant(name),
                            )
                        )
                        await db.flush()

            # Phase 1: LLM grouping for truly new merchants
            new_count = 0
            if names_to_process:
                groups = await group_raw_merchants(names_to_process)
                canonicals = await create_canonicals_from_groups(
                    db, groups, review_job_id=job_id_uuid
                )
                await db.commit()

                # Phase 2: Categorize each new canonical and pre-apply to transactions
                for i, group in enumerate(groups):
                    canonical_info = canonicals[i]
                    if not canonical_info.get("is_new"):
                        continue

                    first_raw = group["raw_names"][0]
                    categories = await lookup_merchant(first_raw, db, redis)

                    if categories:
                        canonical_result = await db.execute(
                            select(CanonicalMerchant).where(
                                CanonicalMerchant.id == uuid.UUID(canonical_info["id"])
                            )
                        )
                        canonical = canonical_result.scalar_one_or_none()
                        if canonical:
                            canonical.default_category = categories[0]

                        # Pre-apply category to transactions
                        for raw_name in group["raw_names"]:
                            where_clauses = [
                                Transaction.user_id == job_user_id,
                                Transaction.raw_merchant_name == raw_name,
                                Transaction.category.is_(None),
                            ]
                            if job_tx_ids:
                                where_clauses.append(
                                    Transaction.id.in_([uuid.UUID(tid) for tid in job_tx_ids])
                                )
                            await db.execute(
                                Transaction.__table__.update()
                                .where(*where_clauses)
                                .values(category=categories[0])
                            )

                    new_count += 1

            # Finalize — total_merchants = all unique merchants (known + new)
            total_count = known_count + new_count
            job.status = "ready"
            job.total_merchants = total_count
            job.updated_at = datetime.now(timezone.utc)

            await _finalize_review_notification(db, job)
            await db.commit()
            logger.info(
                "Review job %s complete: %d merchants (%d known, %d new)",
                job_id,
                total_count,
                known_count,
                new_count,
            )

        except Exception:
            logger.exception("Review job %s failed", job_id)
            # Use a fresh session — the original may be in a broken state
            async with AsyncSessionLocal() as error_db:
                result = await error_db.execute(
                    select(MerchantReviewJob).where(MerchantReviewJob.id == uuid.UUID(job_id))
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.updated_at = datetime.now(timezone.utc)
                    if job_notification_id:
                        notif_result = await error_db.execute(
                            select(Notification).where(Notification.id == job_notification_id)
                        )
                        notif = notif_result.scalar_one_or_none()
                        if notif:
                            notif.title = "No se pudieron procesar los comercios — transacciones disponibles con nombres originales"
                            notif.updated_at = datetime.now(timezone.utc)
                    await error_db.commit()
        finally:
            await redis.aclose()


async def run_plaid_sync_job(ctx: dict, plaid_item_id: str, initial: bool = False):
    """Run a Plaid transaction sync for one item."""
    from modules.plaid.sync import run_plaid_sync
    from modules.plaid.models import PlaidItem
    from modules.merchant_review.models import MerchantReviewJob

    async with AsyncSessionLocal() as db:
        stats = await run_plaid_sync(db, uuid.UUID(plaid_item_id), initial=initial)

        # Get the PlaidItem to find user/household for downstream enqueues
        item_result = await db.execute(
            select(PlaidItem).where(PlaidItem.id == uuid.UUID(plaid_item_id))
        )
        item = item_result.scalar_one_or_none()

        # Trigger merchant review if new transactions were added
        if stats.get("added", 0) > 0 and item:
            review_job = MerchantReviewJob(
                user_id=item.user_id,
                transaction_ids=stats.get("new_tx_ids"),
            )
            db.add(review_job)
            await db.commit()

            await enqueue_job("process_merchant_review", str(review_job.id))

        # Event-driven reconciliation: nudge the per-household tick now that
        # this sync added/modified rows. Replaces the old every-15-min cron.
        if item and (stats.get("added", 0) > 0 or stats.get("modified", 0) > 0):
            try:
                await enqueue_job("run_reconciliation_tick_for_household", str(item.household_id))
            except Exception:
                logger.warning(
                    "run_plaid_sync_job: failed to enqueue reconciliation tick",
                    exc_info=True,
                )

        return stats


async def schedule_plaid_syncs(ctx: dict):
    """Daily cron: enqueue sync for all active Plaid items."""
    from modules.plaid.models import PlaidItem

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PlaidItem).where(PlaidItem.error_code.is_(None)))
        items = result.scalars().all()
        for item in items:
            await enqueue_job("run_plaid_sync_job", plaid_item_id=str(item.id), initial=False)
        if items:
            print(f"[SCHEDULE_PLAID_SYNCS] Enqueued {len(items)} syncs", flush=True)


async def run_reconciliation_job(ctx: dict):
    """Daily 6am safety net: enqueue a FULL reconciliation tick per household.

    Two bugs fixed at once: the old version (a) looped every household inside
    one 600s-capped job, so late households were silently skipped at scale,
    and (b) only ran transfer detection — the full tick (rematch, transfers,
    refunds, wallets, aging) existed but was registered on no worker.
    """
    from modules.households.models import Household

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Household.id))
        household_ids = [str(h) for h in result.scalars().all()]

    for hid in household_ids:
        await enqueue_job("run_reconciliation_tick_for_household", hid)
    logger.info("run_reconciliation_job: enqueued %d household ticks", len(household_ids))
