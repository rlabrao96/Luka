# Luka — API Reference

Base URL: `https://luka-production-eb87.up.railway.app`

All endpoints except `/health` require `Authorization: Bearer <supabase_jwt>`.

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{"status":"ok","app":"luka"}` |

## Auth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/me` | Current user profile + household_id. Auto-provisions user on first call. |

## Households

| Method | Path | Description |
|--------|------|-------------|
| POST | `/households/` | Create household (type: `individual` or `couple`) |
| POST | `/households/{id}/invite` | Send email invite with 7-day token |
| GET | `/households/{id}/summary` | Current user's transaction aggregates |
| GET | `/households/{id}/partner-stats` | Partner aggregates (via SECURITY DEFINER RPC) |
| POST | `/invite/accept` | Accept household invite with token |

## Transactions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/transactions/mine?since=YYYY-MM-DD` | User's transactions (default: 6 months) |
| GET | `/transactions/shared?household_id=X` | Household shared transactions |
| GET | `/transactions/monthly-summary?household_id=X` | Last 6 months spending by type |
| PATCH | `/transactions/{id}/category` | Update transaction category |

## Bank Accounts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/bank-accounts` | User's connected accounts with import status |
| GET | `/bank-accounts/fintoc/accounts?link_token=X` | Available Fintoc accounts for a link |
| POST | `/bank-accounts/fintoc/connect` | Store link_id + account_id, enqueue history import |
| PATCH | `/bank-accounts/{id}` | Update account_type, nickname |
| DELETE | `/bank-accounts/{id}` | Hard delete (cascades to transactions/splits) |
| POST | `/bank-accounts/sync-balances` | Fetch + store Fintoc balances |
| GET | `/bank-accounts/import-status?household_id=X` | Import progress polling |

## Budgets

| Method | Path | Description |
|--------|------|-------------|
| GET | `/budgets/monthly/{id}?month=YYYY-MM` | Monthly budget status (budgeted, spent, available) |
| POST | `/budgets/monthly/{id}` | Set monthly budget amount |
| GET | `/budgets/personal/{id}?month=YYYY-MM` | Personal waterfall + pace + income |
| GET | `/budgets/allocation/{id}?month=YYYY-MM` | Current + suggested 50/20/30 allocations |
| POST | `/budgets/allocation/{id}` | Upsert hogar/ahorro/personal percentages |

## Webhooks (Server-to-Server)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/gmail` | Google Pub/Sub notification |
| POST | `/webhooks/outlook` | Microsoft Graph subscription |
| GET | `/webhooks/whatsapp` | WhatsApp webhook verification |
| POST | `/webhooks/whatsapp` | WhatsApp incoming message/button |
| POST | `/bank-accounts/webhooks/fintoc-link` | Fintoc link.created webhook |

## Interactive API Docs

FastAPI auto-generates OpenAPI docs:
- Swagger UI: `{BASE_URL}/docs`
- ReDoc: `{BASE_URL}/redoc`
