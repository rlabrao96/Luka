import hashlib
import hmac
import json
import logging
from fastapi import APIRouter, HTTPException, Request
from core.config import settings
from core.database import AsyncSessionLocal
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.get("/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    """Meta webhook verification challenge."""
    params = request.query_params
    if params.get("hub.verify_token") == settings.whatsapp_app_secret:
        return int(params.get("hub.challenge", 0))
    raise HTTPException(403)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        raise HTTPException(403)

    data = json.loads(body)
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                phone = message["from"]
                msg_type = message.get("type")

                if msg_type == "interactive":
                    interactive = message["interactive"]
                    itype = interactive["type"]

                    redis_client = await aioredis.from_url(settings.redis_url)
                    try:
                        async with AsyncSessionLocal() as db:
                            if itype == "button_reply":
                                btn_id = interactive["button_reply"]["id"]
                                print(
                                    f"[WA_WEBHOOK] button_reply from={phone} id={btn_id}",
                                    flush=True,
                                )
                                from modules.whatsapp.handler import handle_button_click

                                context_msg_id = message.get("context", {}).get("id", "")
                                await handle_button_click(
                                    phone=phone,
                                    button_id=btn_id,
                                    context_msg_id=context_msg_id,
                                    db=db,
                                    redis=redis_client,
                                )
                            elif itype == "list_reply":
                                list_id = interactive["list_reply"]["id"]
                                list_title = interactive["list_reply"]["title"]
                                print(
                                    f"[WA_WEBHOOK] list_reply from={phone} id={list_id} title={list_title}",
                                    flush=True,
                                )
                                from modules.whatsapp.handler import handle_list_selection

                                context_msg_id = message.get("context", {}).get("id", "")
                                await handle_list_selection(
                                    phone=phone,
                                    list_item_id=list_id,
                                    list_item_title=list_title,
                                    context_msg_id=context_msg_id,
                                    db=db,
                                    redis=redis_client,
                                )
                    except Exception as e:
                        logger.error("WhatsApp webhook handler error: %s", e, exc_info=True)
                    finally:
                        await redis_client.aclose()

                elif msg_type == "text":
                    text_body = message.get("text", {}).get("body", "")
                    redis_client = await aioredis.from_url(settings.redis_url)
                    try:
                        async with AsyncSessionLocal() as db:
                            from modules.whatsapp.handler import handle_text_message
                            await handle_text_message(
                                phone=phone,
                                text=text_body,
                                db=db,
                                redis=redis_client,
                            )
                    except Exception as e:
                        logger.error("WhatsApp text handler error: %s", e, exc_info=True)
                    finally:
                        await redis_client.aclose()

    return {"status": "ok"}
