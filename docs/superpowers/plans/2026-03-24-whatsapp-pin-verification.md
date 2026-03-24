# WhatsApp PIN Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the onboarding WhatsApp verification step with real PIN send/verify via WhatsApp Cloud API, replacing the fully mocked UI.

**Architecture:** Backend generates 6-digit PIN, stores in Redis (5-min TTL with attempt counter), sends via existing WhatsApp Cloud API sender. Two new auth endpoints (`send-whatsapp-pin`, `verify-whatsapp-pin`). Frontend wires existing UI to real API calls with error/loading states.

**Tech Stack:** FastAPI, Redis, WhatsApp Cloud API (httpx), Next.js 14

**Spec:** `docs/superpowers/specs/2026-03-24-whatsapp-pin-verification-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `backend/modules/auth/schemas.py` | Add `SendWhatsAppPinRequest` |
| `backend/modules/auth/router.py` | Add `send-whatsapp-pin` and `verify-whatsapp-pin` endpoints, remove `phone_whatsapp` from PATCH /me |
| `backend/modules/whatsapp/sender.py` | Add `send_verification_pin()` text message function |
| `frontend/app/lib/api.ts` | Add `sendWhatsAppPin()`, `verifyWhatsAppPin()` methods |
| `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx` | Wire real API calls, add error/loading/cooldown states |
| `backend/tests/test_whatsapp_pin.py` | **New** — tests for both endpoints |

---

### Task 1: Add `send_verification_pin()` to WhatsApp Sender

**Files:**
- Modify: `backend/modules/whatsapp/sender.py`

- [ ] **Step 1: Add the function**

Add at the end of `backend/modules/whatsapp/sender.py`:

```python
async def send_verification_pin(to: str, pin: str) -> None:
    """Send a text message with a verification PIN. Raises on failure."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": (
                f"\U0001f510 Tu código de verificación Luka es: {pin}\n\n"
                "No compartas este código con nadie. Expira en 5 minutos."
            )
        },
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(_url(), headers=_headers(), json=payload)
        if resp.status_code != 200:
            data = resp.json()
            raise Exception(f"WhatsApp API Error: {data}")
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python3 -c "from modules.whatsapp.sender import send_verification_pin; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/whatsapp/sender.py
git commit -m "feat: add send_verification_pin to WhatsApp sender"
```

---

### Task 2: Schema + Endpoints + Tests

**Files:**
- Modify: `backend/modules/auth/schemas.py`
- Modify: `backend/modules/auth/router.py`
- Create: `backend/tests/test_whatsapp_pin.py`

- [ ] **Step 1: Add schema**

In `backend/modules/auth/schemas.py`, add after `StoreProviderTokensRequest`:

```python
class SendWhatsAppPinRequest(BaseModel):
    phone: str
```

- [ ] **Step 2: Write tests**

Create `backend/tests/test_whatsapp_pin.py`:

```python
import json
import re
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_user_for_pin():
    from modules.auth.models import User
    import uuid

    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=False,
        phone_whatsapp=None,
    )


@pytest.fixture
def setup_pin_app(app, mock_user_for_pin):
    """Override auth and DB for all PIN tests."""
    from core.security import get_current_user
    from core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: mock_user_for_pin

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one = MagicMock(return_value=mock_user_for_pin)
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def _mock_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_db
    yield mock_db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_pin_stores_in_redis_and_sends(app, mock_user_for_pin, setup_pin_app):
    with (
        patch("modules.auth.router.cache_set", new_callable=AsyncMock) as mock_cache_set,
        patch(
            "modules.auth.router.send_verification_pin", new_callable=AsyncMock
        ) as mock_send,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/send-whatsapp-pin", json={"phone": "+56912345678"}
            )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_cache_set.assert_called_once()
    call_args = mock_cache_set.call_args
    assert call_args[0][0] == "whatsapp_pin:+56912345678"
    stored = call_args[0][1]
    assert len(stored["pin"]) == 6
    assert stored["user_id"] == str(mock_user_for_pin.id)
    assert stored["attempts"] == 0
    assert call_args[1]["ttl_seconds"] == 300
    mock_send.assert_called_once_with("+56912345678", stored["pin"])


@pytest.mark.asyncio
async def test_send_pin_validates_phone_format(app, setup_pin_app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.post("/auth/send-whatsapp-pin", json={"phone": "not-a-phone"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_pin_success(app, mock_user_for_pin, setup_pin_app):
    pin_data = {
        "pin": "123456",
        "user_id": str(mock_user_for_pin.id),
        "attempts": 0,
    }
    with (
        patch(
            "modules.auth.router.cache_get",
            new_callable=AsyncMock,
            return_value=pin_data,
        ),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock) as mock_del,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin",
                json={"phone": "+56912345678", "pin": "123456"},
            )

    assert response.status_code == 200
    assert mock_user_for_pin.phone_whatsapp == "+56912345678"
    assert mock_user_for_pin.whatsapp_verified is True
    # Should delete both the PIN key and the user cache key
    assert mock_del.call_count == 2


@pytest.mark.asyncio
async def test_verify_pin_wrong_pin(app, mock_user_for_pin, setup_pin_app):
    pin_data = {
        "pin": "123456",
        "user_id": str(mock_user_for_pin.id),
        "attempts": 0,
    }
    with (
        patch(
            "modules.auth.router.cache_get",
            new_callable=AsyncMock,
            return_value=pin_data,
        ),
        patch("modules.auth.router.cache_set", new_callable=AsyncMock) as mock_set,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin",
                json={"phone": "+56912345678", "pin": "999999"},
            )

    assert response.status_code == 400
    assert "incorrecto" in response.json()["detail"]
    # Should increment attempts
    mock_set.assert_called_once()
    stored = mock_set.call_args[0][1]
    assert stored["attempts"] == 1


@pytest.mark.asyncio
async def test_verify_pin_expired(app, setup_pin_app):
    with patch(
        "modules.auth.router.cache_get",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin",
                json={"phone": "+56912345678", "pin": "123456"},
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_pin_wrong_user(app, setup_pin_app):
    pin_data = {
        "pin": "123456",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "attempts": 0,
    }
    with patch(
        "modules.auth.router.cache_get",
        new_callable=AsyncMock,
        return_value=pin_data,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin",
                json={"phone": "+56912345678", "pin": "123456"},
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_pin_lockout_after_5_attempts(app, mock_user_for_pin, setup_pin_app):
    pin_data = {
        "pin": "123456",
        "user_id": str(mock_user_for_pin.id),
        "attempts": 4,
    }
    with (
        patch(
            "modules.auth.router.cache_get",
            new_callable=AsyncMock,
            return_value=pin_data,
        ),
        patch("modules.auth.router.cache_delete", new_callable=AsyncMock) as mock_del,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            response = await c.post(
                "/auth/verify-whatsapp-pin",
                json={"phone": "+56912345678", "pin": "999999"},
            )

    assert response.status_code == 400
    # Should delete the PIN key (lockout)
    mock_del.assert_called_once_with("whatsapp_pin:+56912345678")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_whatsapp_pin.py -v`
Expected: FAIL — 404/405

- [ ] **Step 4: Implement the endpoints**

In `backend/modules/auth/router.py`, add these imports (merge with existing):

```python
import re
import random
from core.cache import cache_delete, cache_get, cache_set
from modules.auth.schemas import (
    SendWhatsAppPinRequest,
    StoreProviderTokensRequest,
    UpdateProfileRequest,
    UserResponse,
    WhatsAppVerifyRequest,
)
from modules.whatsapp.sender import send_verification_pin
```

Remove the old single-line import of schemas and `cache_delete` (they're now in the merged imports above).

Add these two endpoints after `setup_email_watch`:

```python
@router.post("/send-whatsapp-pin")
async def send_whatsapp_pin(
    body: SendWhatsAppPinRequest,
    current_user: User = Depends(get_current_user),
):
    if not re.fullmatch(r"\+\d{7,15}", body.phone):
        raise HTTPException(status_code=422, detail="Número inválido")

    pin = str(random.randint(100000, 999999))
    await cache_set(
        f"whatsapp_pin:{body.phone}",
        {"pin": pin, "user_id": str(current_user.id), "attempts": 0},
        ttl_seconds=300,
    )

    try:
        await send_verification_pin(body.phone, pin)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo enviar el PIN. Intenta de nuevo.",
        )

    return {"status": "ok"}


@router.post("/verify-whatsapp-pin")
async def verify_whatsapp_pin(
    body: WhatsAppVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = f"whatsapp_pin:{body.phone}"
    data = await cache_get(key)

    if not data:
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    if data["user_id"] != str(current_user.id):
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    if data["pin"] != body.pin:
        data["attempts"] = data.get("attempts", 0) + 1
        if data["attempts"] >= 5:
            await cache_delete(key)
        else:
            await cache_set(key, data, ttl_seconds=300)
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado")

    # Success — save phone and mark verified
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    user.phone_whatsapp = body.phone
    user.whatsapp_verified = True
    await db.commit()
    await db.refresh(user)
    await cache_delete(f"user:{user.email}")
    await cache_delete(key)

    return {"status": "ok"}
```

- [ ] **Step 5: Remove `phone_whatsapp` from PATCH /me**

In `backend/modules/auth/router.py`, remove lines 53-54 from the `update_profile` endpoint:

```python
    if body.phone_whatsapp is not None:
        user.phone_whatsapp = body.phone_whatsapp or None  # empty string → NULL
```

Also remove `phone_whatsapp` from `UpdateProfileRequest` in `backend/modules/auth/schemas.py`:

```python
class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python3 -m pytest tests/test_whatsapp_pin.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add backend/modules/auth/schemas.py backend/modules/auth/router.py backend/tests/test_whatsapp_pin.py
git commit -m "feat: WhatsApp PIN send/verify endpoints with brute-force protection"
```

---

### Task 3: Frontend — API Client Methods

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add API methods**

Add to the `api` object in `frontend/app/lib/api.ts`:

```typescript
  sendWhatsAppPin: (phone: string) =>
    apiFetch<{ status: string }>("/auth/send-whatsapp-pin", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  verifyWhatsAppPin: (phone: string, pin: string) =>
    apiFetch<{ status: string }>("/auth/verify-whatsapp-pin", {
      method: "POST",
      body: JSON.stringify({ phone, pin }),
    }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat: add WhatsApp PIN API client methods"
```

---

### Task 4: Frontend — Wire Onboarding Page

**Files:**
- Modify: `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx`

- [ ] **Step 1: Replace the entire page**

Replace `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx` with:

```tsx
"use client";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export default function VerifyWhatsAppPage() {
  const router = useRouter();
  const { onboardingDraft, setHousehold } = useLukaStore();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [pinSent, setPinSent] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const finalizeOnboarding = async () => {
    try {
      if (onboardingDraft?.type) {
        const household = await api.createHousehold("Mi Hogar", onboardingDraft.type);
        if (household.id) {
          setHousehold(household.id);
          if (onboardingDraft.type === "couple" && onboardingDraft.partnerEmail) {
            try {
              await api.invitePartner(household.id, onboardingDraft.partnerEmail);
            } catch (inviteError) {
              console.error("Partner invite failed, continuing...", inviteError);
            }
          }
        }
      }
      router.push("/onboarding/connect-bank");
    } catch (e) {
      console.error("Failed to setup household:", e);
    }
  };

  const sendPin = async () => {
    setError(null);
    setIsSending(true);
    try {
      await api.sendWhatsAppPin(phone);
      setPinSent(true);
      setCooldown(60);
    } catch (e: any) {
      setError(e.message || "Error al enviar el PIN");
    } finally {
      setIsSending(false);
    }
  };

  const verifyPin = async () => {
    setError(null);
    setIsVerifying(true);
    try {
      await api.verifyWhatsAppPin(phone, pin);
      await finalizeOnboarding();
    } catch (e: any) {
      setError(e.message || "PIN incorrecto o expirado");
      setIsVerifying(false);
    }
  };

  const skip = async () => {
    setIsVerifying(true);
    await finalizeOnboarding();
  };

  return (
    <Card>
      <CardHeader><CardTitle>Verifica tu WhatsApp</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-luka-muted text-sm">
          Luka te enviará alertas de gastos por WhatsApp. Necesitamos verificar tu número.
        </p>
        <Input
          placeholder="+56 9 1234 5678"
          value={phone}
          onChange={e => { setPhone(e.target.value); setError(null); }}
          disabled={isSending || isVerifying}
          className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        />

        {error && (
          <p className="text-sm text-red-500 font-medium">{error}</p>
        )}

        <div className="space-y-2">
          {!pinSent ? (
            <Button
              className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              onClick={sendPin}
              disabled={isSending || !phone.trim()}
            >
              {isSending ? "Enviando..." : "Enviar PIN por WhatsApp"}
            </Button>
          ) : (
            <>
              <Input
                placeholder="Código de 6 dígitos"
                value={pin}
                onChange={e => { setPin(e.target.value); setError(null); }}
                disabled={isVerifying}
                className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <Button
                className="w-full bg-luka-primary rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                onClick={verifyPin}
                disabled={isVerifying || !pin.trim()}
              >
                {isVerifying ? "Verificando..." : "Verificar →"}
              </Button>
              <button
                onClick={sendPin}
                disabled={cooldown > 0 || isSending}
                className="w-full text-sm text-luka-primary hover:text-blue-700 text-center py-1 disabled:text-luka-muted disabled:cursor-not-allowed"
              >
                {cooldown > 0 ? `Reenviar en ${cooldown}s` : "Reenviar PIN"}
              </button>
            </>
          )}

          <button
            onClick={skip}
            disabled={isSending || isVerifying}
            className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-2 disabled:opacity-50"
          >
            {isVerifying ? "Cargando..." : "Saltar por ahora"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx
git commit -m "feat: wire WhatsApp PIN verification in onboarding UI"
```

---

### Task 5: Run Full Test Suite

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python3 -m pytest tests/ -v`
Expected: All new tests pass, no regressions

- [ ] **Step 2: Ruff format**

Run: `cd backend && python3 -m ruff check --fix . && python3 -m ruff format .`
If files changed: `git add -u && git commit -m "style: auto-format with ruff"`
