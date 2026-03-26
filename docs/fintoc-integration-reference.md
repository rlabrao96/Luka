# Fintoc Integration Reference for Luka

> Complete reference for integrating Fintoc's **Movements** product into Luka.
> Source: [Fintoc Docs](https://docs.fintoc.com/docs/welcome) — scraped 2026-03-25.

---

## 1. Overview

Fintoc is a financial data aggregation API for Chile and Mexico. For Luka, we use the **Movements** product to access users' bank transaction history (movements + balances) from Chilean banks.

**How it works:**
1. User connects their bank account via the **Fintoc Widget** (frontend)
2. Fintoc creates a **Link** (connection between the user's bank and Fintoc)
3. Backend receives the `link_token` via webhook
4. Backend polls Fintoc API for accounts and movements using the `link_token`
5. Fintoc periodically refreshes data; on-demand refresh also available

---

## 2. Supported Banks in Chile (Movements Product)

| Bank | Individual | Business | History | Account Types | Currency |
|------|-----------|----------|---------|---------------|----------|
| **Banco de Chile** | `cl_banco_de_chile` | `cl_banco_de_chile` | 24 months | Checking, Sight | CLP, USD |
| **Banco Santander** | `cl_banco_santander` | `cl_banco_santander` | 24 months | Checking, Sight (Business: + Credit Cards) | CLP (Business: + USD) |
| **Banco Itau** | `cl_banco_itau` | `cl_banco_itau` | 24 / 12 months | Checking, Sight | CLP (Business: + USD) |
| **Banco BICE** | `cl_banco_bice` | `cl_banco_bice` | 12 months | Checking, Sight | CLP (Business: + USD) |
| **Banco Scotiabank** | `cl_banco_scotiabank` | `cl_banco_scotiabank` | 12 months | Checking, Sight | CLP |
| **Banco BCI** | `cl_banco_bci` | `cl_banco_bci` / `cl_banco_bci_360` | 12 / 6 / 3 months | Checking, Sight | CLP (360: + USD) |
| **Banco Estado** | `cl_banco_estado` | `cl_banco_estado` | 12 months | Checking, Sight | CLP |
| **Banco Security** | -- | `cl_banco_security` | 12 months | Checking, Sight | CLP |

---

## 3. Account Types

| Type | Description |
|------|-------------|
| `checking_account` | Cuenta Corriente |
| `savings_account` | Cuenta de Ahorro |
| `sight_account` | Cuenta Vista / Cuenta RUT |
| `line_of_credit` | Linea de Credito |
| `credit_card` | Tarjeta de Credito |

---

## 4. Core Concepts

### Link
A **Link** represents the connection between a user's bank credentials and Fintoc. Each Link:
- Has a `link_token` (returned only at creation, null afterward)
- Contains one or more **Accounts**
- Has a `holder_type`: `individual` or `business`
- Has a `status`: `active` or `login_required` (credentials changed)
- Has a `refresh_status`: `idle`, `refreshing`, `partially_refreshing`, `interrupted`

### Account
Each account under a Link has:
- `id` (acc_xxx), `name`, `type`, `number`, `currency`
- `balance`: `{ available, current, limit }`
- `refreshed_at`, `next_refresh`

### Movement
A bank transaction. Key fields:
- `id`, `amount` (integer, in cents — positive = inflow, negative = outflow)
- `post_date` (accounting date), `transaction_date` (actual date)
- `description`, `type` (`transfer`, `check`, `other`)
- `pending` (boolean — for pending checks)
- `status`: `confirmed`, `processing`, `reversed`, `duplicated`
- `sender_account` / `recipient_account` (transfer metadata, can be null)
- `comment` (transfer comment, can be null)
- `reference_id` (bank's operation number)

---

## 5. Integration Flow (Widget + Exchange Token)

### Step 1: Create a Link Intent (Backend)

```python
# POST /v1/link_intents
import httpx

response = httpx.post(
    "https://api.fintoc.com/v1/link_intents",
    headers={"Authorization": FINTOC_SECRET_KEY},
    json={
        "product": "movements",
        "country": "cl",
        "holder_type": "individual"  # or "business"
    }
)
link_intent = response.json()
# link_intent["widget_token"] → send to frontend
```

### Step 2: Open Widget (Frontend)

```javascript
import { getFintoc } from '@fintoc/fintoc-js';
// Or: <script src="https://js.fintoc.com/v1/"></script>

const Fintoc = await getFintoc();
const widget = Fintoc.create({
  publicKey: 'pk_live_...',       // pk_test_ for sandbox
  widgetToken: widgetTokenFromBackend,  // from link intent
  onSuccess: (linkIntent) => {
    // linkIntent.exchangeToken → send to backend
    sendExchangeTokenToBackend(linkIntent.exchangeToken);
  },
  onExit: () => { /* user closed widget */ },
  onEvent: (eventName, metadata) => { /* tracking */ },
});
widget.open();
```

### Step 3: Exchange Token for Link (Backend)

```python
# GET /v1/links/exchange?exchange_token=li_xxx_exchange_token_yyy
response = httpx.get(
    "https://api.fintoc.com/v1/links/exchange",
    headers={"Authorization": FINTOC_SECRET_KEY},
    params={"exchange_token": exchange_token}
)
link = response.json()
# link["link_token"] → store securely
# link["accounts"] → create BankAccount records
```

### Alternative: webhookUrl Flow (simpler, current Luka approach)

```javascript
const widget = Fintoc.create({
  product: 'movements',
  publicKey: 'pk_live_...',
  holderType: 'individual',
  country: 'cl',
  webhookUrl: 'https://api.luka.cl/webhooks/fintoc-link?household_id=X&user_id=Y',
  onSuccess: () => { /* no params — link_token comes via webhookUrl */ },
});
```

Fintoc POSTs `link.created` event to webhookUrl. This is the **only** way to receive `link.created` — it cannot be received via registered Webhook Endpoints.

---

## 6. API Endpoints

**Base URL:** `https://api.fintoc.com/v1`
**Auth:** `Authorization: sk_live_xxx` (or `sk_test_xxx` for sandbox)

### Links

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/links` | List all links |
| `GET` | `/v1/links/{id}?link_token=...` | Get a specific link |
| `PATCH` | `/v1/links/{id}` | Update a link |
| `DELETE` | `/v1/links/{id}` | Delete a link |
| `GET` | `/v1/links/exchange?exchange_token=...` | Exchange token for link |

### Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/accounts?link_token=...` | List accounts for a link |
| `GET` | `/v1/accounts/{id}?link_token=...` | Get a specific account |

### Movements

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/accounts/{id}/movements?link_token=...` | List movements for account |
| `GET` | `/v1/accounts/{id}/movements/{mov_id}?link_token=...` | Get a specific movement |

**Query params for List Movements:**
- `since` — ISO 8601 date, return movements with `post_date >= since`
- `until` — ISO 8601 date, return movements with `post_date < until`
- `per_page` — default 30, max 300
- `page` — starts from 1
- `confirmed_only` — default `true`. Set to `false` to include pending/reversed/duplicated

### Link Intents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/link_intents` | Create link intent (body: `{product, country, holder_type}`) |

### Refresh Intents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/refresh_intents?link_token=...` | Create refresh intent (on-demand update) |
| `GET` | `/v1/refresh_intents?link_token=...` | List refresh intents |
| `GET` | `/v1/refresh_intents/{id}?link_token=...` | Get a refresh intent |

### Webhook Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/webhook_endpoints` | Register a webhook endpoint |
| `GET` | `/v1/webhook_endpoints` | List webhook endpoints |
| `PATCH` | `/v1/webhook_endpoints/{id}` | Update |
| `DELETE` | `/v1/webhook_endpoints/{id}` | Delete |

---

## 7. Webhooks & Events

### Webhook Setup
- Create endpoint on your server that accepts POST requests
- Respond with 2XX quickly (handle logic async)
- Each event has a unique `id` — save for idempotency
- Fintoc retries on non-2XX responses

### Events Relevant to Luka (Movements Product)

| Event Type | Description |
|------------|-------------|
| `link.created` | Link created (ONLY via `webhookUrl` in widget, not registered endpoints) |
| `link.credentials_changed` | User changed bank password, link needs reconnection |
| `account.refresh_intent.succeeded` | Account updated with latest movements. `data.new_movements` indicates count |
| `account.refresh_intent.failed` | Account update failed (bank down, etc.) |
| `account.refresh_intent.rejected` | Credentials invalid, need reconnection |
| `account.refresh_intent.movements_removed` | Bank deleted transactions (enable in dashboard) |
| `account.refresh_intent.movements_modified` | Bank modified transactions (enable in dashboard) |
| `link.refresh_intent.succeeded` | Entire link updated (all accounts) |

### Event Object Structure

```json
{
  "id": "evt_00000000",
  "type": "account.refresh_intent.succeeded",
  "mode": "live",
  "created_at": "2021-12-07T21:43:54.343Z",
  "data": {
    "object": "refresh_intent",
    "refreshed_object": "account",
    "refreshed_object_id": "acc_00000000",
    "status": "succeeded",
    "public_error": null,
    "type": "only_last",
    "new_movements": 5
  },
  "object": "event"
}
```

---

## 8. Refresh Intents (On-Demand Updates)

Fintoc periodically updates Links, but you can trigger on-demand refreshes:

```python
# Create refresh intent
response = httpx.post(
    "https://api.fintoc.com/v1/refresh_intents",
    headers={"Authorization": FINTOC_SECRET_KEY},
    params={"link_token": link_token}
)
refresh = response.json()
# If refresh["requires_mfa"] is not null → need widget for 2FA
# Otherwise → wait for webhook event (1-3 minutes)
```

**Constraints:**
- 5-minute cooldown between successful refresh intents
- Only one refresh intent can be in progress per link
- Failed/rejected intents can be retried immediately

**If MFA required:** Use the `widget_token` from `requires_mfa` to open the widget so the user can enter their second factor.

---

## 9. Movement Object (Full Schema)

```json
{
  "id": "mov_BO381oEATXonG6bj",
  "object": "movement",
  "amount": 59400,
  "post_date": "2020-04-17T00:00:00.000Z",
  "description": "Traspaso de:Fintoc SpA",
  "transaction_date": "2020-04-16T11:31:12.000Z",
  "currency": "CLP",
  "reference_id": "123740123",
  "type": "transfer",
  "pending": false,
  "status": "confirmed",
  "recipient_account": null,
  "sender_account": {
    "holder_id": "771806538",
    "holder_name": "Comercial y Produccion SpA",
    "number": "1530108000",
    "institution": {
      "id": "cl_banco_de_chile",
      "name": "Banco de Chile",
      "country": "cl"
    }
  },
  "comment": "Pago factura 198"
}
```

### Movement Status Values

| Status | Description |
|--------|-------------|
| `confirmed` | Final, default status |
| `processing` | Being evaluated, resolves within ~12 hours |
| `reversed` | Reversed by the bank |
| `duplicated` | Duplicate, should be excluded from reconciliation |

### Movement Types

| Type | Description |
|------|-------------|
| `transfer` | Bank transfer (TEF) |
| `check` | Check |
| `other` | Everything else (card purchases, ATM, etc.) |

---

## 10. Account Object (Full Schema)

```json
{
  "id": "acc_nMNejK7BT8oGbvO4",
  "object": "account",
  "name": "Cuenta Corriente",
  "official_name": "Cuenta Corriente Moneda Local",
  "number": "9530516286",
  "holder_id": "134910798",
  "holder_name": "Jon Snow",
  "type": "checking_account",
  "currency": "CLP",
  "balance": {
    "available": 500000,
    "current": 500000,
    "limit": 500000
  },
  "refreshed_at": "2020-11-18T18:43:54.591Z",
  "next_refresh": "2020-11-18T22:43:54.591Z",
  "removed_from_link": false,
  "refresh_status": "refreshing"
}
```

### Balance Object

| Field | Description |
|-------|-------------|
| `available` | Available balance (excludes line of credit for checking/savings) |
| `current` | Accounting balance |
| `limit` | For checking: available + line of credit. For LOC: approved limit |

---

## 11. Pagination

- Default: 30 items per page, max 300
- Use `per_page` and `page` query params
- Response includes `Link` header with pagination URLs (`next`, `prev`)
- SDKs handle pagination automatically; cURL/raw HTTP must iterate

---

## 12. API Keys

| Key | Prefix | Environment |
|-----|--------|-------------|
| Public Key (frontend) | `pk_test_` / `pk_live_` | Sandbox / Production |
| Secret Key (backend) | `sk_test_` / `sk_live_` | Sandbox / Production |

---

## 13. Test Mode

Use sandbox credentials to test:
- Username: `41614850-3`
- Password: `jonsnow`
- Works with any bank in sandbox

---

## 14. SDKs

```bash
# Python
pip install fintoc

# Node
npm install fintoc

# Frontend widget
npm install @fintoc/fintoc-js
```
