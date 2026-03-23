# Luka — Deployment Guide

## Infrastructure

| Service | Provider | URL |
|---------|----------|-----|
| API | Railway | `https://luka-production-eb87.up.railway.app` |
| Worker | Railway | Same project, separate service |
| Frontend | Vercel | `https://luka-lovat.vercel.app` |
| Database | Supabase | `mvovcodijqjvzxxthsxg.supabase.co` |
| Redis | Railway add-on | Auto-injected `REDIS_URL` |

## Railway (Backend)

### API Service

- **Root directory:** `/` (uses `backend/Dockerfile`)
- **Start command:** `alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Config:** `railway.toml` at project root

### Worker Service

- **Created manually** in Railway dashboard (not via `railway.toml`)
- **Root directory:** `backend/`
- **Start command:** `python -m arq worker.WorkerSettings`
- **Environment variables:** Same as API (shares Redis URL, DB URL, etc.)

### Environment Variables (Backend)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Supabase PostgreSQL connection string (port 6543 for PgBouncer) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Yes | JWT secret from Supabase Dashboard > Settings > API |
| `REDIS_URL` | Yes | Redis connection (auto-injected by Railway) |
| `FINTOC_API_KEY` | Yes | Fintoc open banking API key |
| `OPENAI_API_KEY` | Yes | OpenAI API key (gpt-4o-mini for categorization) |
| `FRONTEND_URL` | Yes | Production frontend URL |
| `CORS_ORIGINS` | No | Additional comma-separated CORS origins |
| `WHATSAPP_APP_SECRET` | Yes | Meta WhatsApp Business API secret |
| `WHATSAPP_PHONE_NUMBER_ID` | Yes | WhatsApp Business phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | Yes | WhatsApp permanent access token |
| `GCP_PROJECT_ID` | No | Google Cloud project (for Gmail Pub/Sub) |
| `PUBSUB_AUDIENCE` | No | Gmail push notification audience |
| `MICROSOFT_CLIENT_ID` | No | Azure AD app client ID (for Outlook) |
| `MICROSOFT_CLIENT_SECRET` | No | Azure AD app client secret |
| `ENVIRONMENT` | No | `development` or `production` |

## Vercel (Frontend)

- **Framework:** Next.js (auto-detected)
- **Root directory:** `frontend/`
- **Build command:** `npm run build`

### Environment Variables (Frontend)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `NEXT_PUBLIC_API_URL` | Yes | Railway API URL |
| `NEXT_PUBLIC_FINTOC_PUBLIC_KEY` | Yes | Fintoc widget public key |

## Database Migrations

Migrations are run as part of the Railway API start command. For manual migration:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

## Supabase Auth Setup

1. Enable Google provider in Supabase Dashboard > Authentication > Providers
   - Add OAuth 2.0 credentials from Google Cloud Console
   - Scopes: `openid email profile https://www.googleapis.com/auth/gmail.readonly`

2. Enable Microsoft provider
   - Register app in Azure Portal
   - Scopes: `openid email profile Mail.Read`

3. Set redirect URLs in Supabase:
   - `https://luka-lovat.vercel.app/auth/callback`
   - `http://localhost:3000/auth/callback` (development)
