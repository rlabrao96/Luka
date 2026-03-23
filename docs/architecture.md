# Luka — Architecture

## System Overview

```
                    ┌─────────────┐
                    │   Browser   │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │                         │
      ┌───────┴───────┐        ┌───────┴───────┐
      │  Vercel CDN   │        │  Supabase Auth│
      │  (Next.js)    │        │  (OAuth + JWT)│
      └───────┬───────┘        └───────────────┘
              │
      ┌───────┴───────┐
      │  Railway API  │──────────► Redis (cache + jobs)
      │  (FastAPI)    │                  │
      └───────┬───────┘          ┌───────┴───────┐
              │                  │  Railway Worker│
      ┌───────┴───────┐         │  (ARQ cron)   │
      │   Supabase    │         └───────────────┘
      │  PostgreSQL   │
      └───────────────┘
```

## Auth Flow

1. User clicks "Sign in with Google/Microsoft" on login page
2. Supabase OAuth redirects to provider, user authorizes
3. Callback at `/auth/callback` exchanges code for session (JWT stored in cookies)
4. Middleware reads JWT from cookie locally (`getSession()`) — no external call
5. Dashboard layout fetches `/auth/me` with bearer token
6. Backend validates JWT locally using `python-jose` + Supabase JWT secret
7. User is auto-provisioned in DB on first login

**Key decision:** JWT validation is fully local (no Supabase API call on every request). JWKS/secret-based validation saves ~100ms per request.

## Data Model

```
users ─────────────── household_members ─────── households
  │                         │                      │
  │                         │                  household_budgets
  │                         │                  household_budget_allocations
  │
  └── bank_accounts ──── transactions ──── transaction_splits
                              │
                          merchants ──── merchant_category_selections
                              │
                      processed_webhooks (idempotency)
```

**12 tables, 12 Alembic migrations, 9 performance indexes.**

### Key Tables

| Table | Purpose |
|-------|---------|
| `users` | OAuth-provisioned profiles (email, name, provider, WhatsApp status) |
| `households` | Individual or couple household units |
| `bank_accounts` | Fintoc-linked accounts with import status tracking |
| `transactions` | All financial movements (email-parsed or Fintoc-imported) |
| `transaction_splits` | Personal/shared/partner classification per transaction |
| `merchants` | Global merchant name cache with LLM-suggested categories |
| `household_budgets` | Monthly budget targets per household |

## Async Processing (ARQ Worker)

The ARQ worker handles all long-running or background tasks:

| Job | Trigger | What it does |
|-----|---------|-------------|
| `process_email` | Email webhook | Parse → merchant lookup → create transaction → WhatsApp alert |
| `import_fintoc_history` | Account connect | Bulk import 90 days of bank movements |
| `renew_mail_watches` | Cron (3 AM) | Renew Gmail (7d) + Outlook (3d) subscriptions |
| `purge_raw_emails` | Cron (hourly) | Delete raw email text on transactions >24h old |
| `cleanup_processed_webhooks` | Cron (4 AM) | Delete idempotency records >7 days old |
| `run_fintoc_sync` | Cron (2 AM) | Reconcile pending email txns to settled Fintoc movements |

## Caching Strategy

| Layer | What | TTL | Purpose |
|-------|------|-----|---------|
| Redis | User profile (`user:{email}`) | 5 min | Skip DB lookup on every auth call |
| React Query | Transaction data | 5 min (staleTime) | Avoid refetching on navigation |
| Next.js fetch cache | `/auth/me` response | 60s (revalidate) | Cache SSR user profile |
| HTTP headers | GET endpoints | 30s (Cache-Control) | Browser-level caching |

## Security

- **RLS policies** on all tables — users can only access their own household's data
- **SECURITY DEFINER RPC** for partner stats — aggregated data only, no raw rows
- **1-hour inactivity timeout** with auto-logout and Zustand store reset
- **Webhook signature verification** for Gmail (Pub/Sub), Outlook (client state), WhatsApp (HMAC)
- **Idempotency** via `processed_webhooks` table — prevents duplicate transaction creation
