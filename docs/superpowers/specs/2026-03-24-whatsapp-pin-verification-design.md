# WhatsApp PIN Verification — Design Spec
**Date:** 2026-03-24
**Status:** Approved
**Scope:** Wire the onboarding WhatsApp verification step with real PIN send/verify via WhatsApp Cloud API.

---

## Context

The onboarding step at `/onboarding/verify-whatsapp` exists in the UI but is fully mocked — `sendPin()` uses a `setTimeout`, `verifyPin()` skips verification entirely, and the phone number is never saved. The WhatsApp Cloud API sender is already implemented and verified in Live Mode.

---

## 1. Backend — Two New Endpoints

### 1.1 `POST /auth/send-whatsapp-pin`

Request: `{ phone: str }`

Behavior:
- Requires Supabase JWT auth
- Validates phone format (must start with `+`)
- Generates random 6-digit PIN (`random.randint(100000, 999999)`)
- Stores in Redis: key `whatsapp_pin:{phone}` → JSON `{"pin": "123456", "user_id": "<uuid>"}` with 300s TTL
- Sends WhatsApp text message via existing `httpx` pattern from `sender.py`
- Message text: `"🔐 Tu código de verificación Luka es: 123456\n\nNo compartas este código con nadie. Expira en 5 minutos."`
- Returns `200 {"status": "ok"}`
- On WhatsApp send failure: returns `500 {"detail": "No se pudo enviar el PIN. Intenta de nuevo."}`

Rate limiting: Re-sending overwrites the Redis key, so only the latest PIN is valid. No additional rate limiting needed for MVP.

### 1.2 `POST /auth/verify-whatsapp-pin`

Request: `{ phone: str, pin: str }`

Behavior:
- Requires Supabase JWT auth
- Looks up `whatsapp_pin:{phone}` in Redis
- If key not found (expired or never sent): returns `400 {"detail": "PIN incorrecto o expirado"}`
- If PIN doesn't match: returns `400 {"detail": "PIN incorrecto o expirado"}` (same message — don't reveal which failed)
- If `user_id` doesn't match current user: returns `400 {"detail": "PIN incorrecto o expirado"}` (security — prevent cross-user verification)
- On match:
  - Re-fetches user from DB session
  - Sets `user.phone_whatsapp = phone`
  - Sets `user.whatsapp_verified = True`
  - Commits
  - Invalidates Redis user cache (`user:{email}`)
  - Deletes the PIN key from Redis
  - Returns `200 {"status": "ok"}`

### 1.3 Pydantic Schemas

```python
class SendWhatsAppPinRequest(BaseModel):
    phone: str

class VerifyWhatsAppPinRequest(BaseModel):
    phone: str
    pin: str
```

---

## 2. WhatsApp Message Sending

Use the same `httpx` + Meta Graph API pattern from `modules/whatsapp/sender.py`. Add a new function `send_verification_pin()` that sends a simple text message (not interactive buttons/lists):

```python
async def send_verification_pin(to: str, pin: str) -> None:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": f"🔐 Tu código de verificación Luka es: {pin}\n\nNo compartas este código con nadie. Expira en 5 minutos."
        },
    }
    # ... same httpx pattern as existing sender functions
```

---

## 3. Frontend — Wire Existing UI

Replace mocked functions in `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx`:

### `sendPin()`
- Call `POST /auth/send-whatsapp-pin` with `{phone}`
- On success: `setPinSent(true)`
- On error: show error message to user

### `verifyPin()`
- Call `POST /auth/verify-whatsapp-pin` with `{phone, pin}`
- On success: proceed to `finalizeOnboarding()`
- On 400: show `"PIN incorrecto o expirado"` error message

### API client
Add two methods to `frontend/app/lib/api.ts`:
- `sendWhatsAppPin(phone: string)`
- `verifyWhatsAppPin(phone: string, pin: string)`

---

## 4. Files Changed

| File | Change |
|------|--------|
| `backend/modules/auth/schemas.py` | Add `SendWhatsAppPinRequest`, `VerifyWhatsAppPinRequest` |
| `backend/modules/auth/router.py` | Add `POST /auth/send-whatsapp-pin`, `POST /auth/verify-whatsapp-pin` |
| `backend/modules/whatsapp/sender.py` | Add `send_verification_pin()` function |
| `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx` | Wire real API calls, add error state |
| `frontend/app/lib/api.ts` | Add `sendWhatsAppPin()`, `verifyWhatsAppPin()` methods |
| `backend/tests/test_whatsapp_pin.py` | **New** — tests for both endpoints |

---

## 5. Testing

| Test | What it verifies |
|------|-----------------|
| `test_send_pin_stores_in_redis_and_sends` | PIN stored in Redis with TTL, WhatsApp sender called |
| `test_send_pin_validates_phone_format` | Rejects phone without `+` prefix |
| `test_verify_pin_success` | Correct PIN sets `phone_whatsapp` and `whatsapp_verified`, deletes Redis key |
| `test_verify_pin_wrong_pin` | Returns 400 with error message |
| `test_verify_pin_expired` | Returns 400 when Redis key missing |
| `test_verify_pin_wrong_user` | Returns 400 when user_id doesn't match |
