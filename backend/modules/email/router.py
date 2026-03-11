import base64
import json
import re
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from core.config import settings
from core.database import AsyncSessionLocal
from jobs.queue import enqueue_job

router = APIRouter(tags=["webhooks"])


def verify_google_oidc_token(token: str) -> bool:
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.pubsub_audience
        )
        return True
    except Exception:
        return False


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(403)
    token = auth_header.removeprefix("Bearer ")
    if not verify_google_oidc_token(token):
        raise HTTPException(403)

    body = await request.json()
    message = body.get("message", {})
    message_id = message.get("messageId", "")

    if message_id:
        try:
            from modules.transactions.models import ProcessedWebhook
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                existing = await db.execute(
                    select(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id)
                )
                if existing.scalar_one_or_none():
                    return {"status": "duplicate"}
                db.add(ProcessedWebhook(message_id=message_id))
                await db.commit()
        except Exception:
            pass  # DB unavailable — still ACK the webhook

    data = json.loads(base64.b64decode(message.get("data", "e30=")).decode())
    history_id = data.get("historyId", "")
    email_address = data.get("emailAddress", "")

    await enqueue_job(
        "process_email", provider="gmail", email_address=email_address, history_id=history_id
    )
    return {"status": "ok"}


@router.post("/webhooks/outlook")
async def outlook_webhook(request: Request, validationToken: str = None):
    # Validation handshake: Microsoft sends a POST with validationToken query param
    if validationToken:
        if not re.match(r"^[a-zA-Z0-9\-_]{1,256}$", validationToken):
            raise HTTPException(400)
        return PlainTextResponse(validationToken)

    body = await request.json()
    for notification in body.get("value", []):
        if notification.get("clientState") != settings.outlook_client_state:
            raise HTTPException(403)

        message_id = notification.get("resourceData", {}).get("id", "")
        if message_id:
            try:
                from modules.transactions.models import ProcessedWebhook
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    existing = await db.execute(
                        select(ProcessedWebhook).where(ProcessedWebhook.message_id == message_id)
                    )
                    if existing.scalar_one_or_none():
                        continue
                    db.add(ProcessedWebhook(message_id=message_id))
                    await db.commit()
            except Exception:
                pass  # DB unavailable — still ACK the webhook

        await enqueue_job("process_email", provider="outlook", message_id=message_id)

    return {"status": "ok"}
