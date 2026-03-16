# Luka — What Needs Your Input & How to Continue
**Date:** 2026-03-16

This document walks through every decision and credential that requires your input before Luka can go live, ordered by dependency.

---

## Phase 1: External Services (Blocking — do these first)

These are third-party accounts you need to create or configure. Without them, the app cannot run.

---

### 1.1 Supabase — Database + Auth

**What you need:**
1. Create a project at [supabase.com](https://supabase.com)
2. Enable Google OAuth: Settings → Auth → Providers → Google
   - Needs a Google Cloud project with OAuth 2.0 credentials (Client ID + Secret)
3. Enable Microsoft OAuth: Settings → Auth → Providers → Azure
   - Needs Azure app registration (Client ID + Secret)
4. Collect from Supabase dashboard:
   - `SUPABASE_URL` (e.g. `https://xxxx.supabase.co`)
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_KEY`
   - `DATABASE_URL` — connection string from Settings → Database → Connection string (use the **asyncpg** format: `postgresql+asyncpg://...`)

**Decision needed:**
- What do you want to call the Supabase project? (e.g. "luka-prod")
- Do you want one project for dev + prod, or separate projects?

---

### 1.2 Redis — Job Queue

**What you need:**
- Any Redis 7+ instance. Options:
  - **Railway Redis** (add-on, easiest — same platform as backend) → gives you `REDIS_URL` automatically
  - **Upstash** (serverless Redis, free tier) — good if budget-conscious
  - **Redis Cloud** (free 30MB tier)

**Decision needed:** Which Redis provider do you want?

---

### 1.3 WhatsApp Cloud API — Business Account

**What you need:**
1. [Meta for Developers](https://developers.facebook.com) → Create app → Business type
2. Add "WhatsApp" product
3. Create a WhatsApp Business Account (WABA)
4. Add a phone number (can use a test number Meta provides, or your real number)
5. Collect:
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_ACCESS_TOKEN` (permanent token, not temporary)
   - `WHATSAPP_APP_SECRET`
6. Configure webhook URL (will be your Railway URL): `https://your-api.railway.app/webhooks/whatsapp`
7. Subscribe to `messages` webhook field

**Decision needed:**
- Do you have an existing Meta Business account?
- Is this for personal use (your own phone number) or for other users too? If other users, you need to go through Meta's official WhatsApp Business API approval process.

---

### 1.4 Gmail Push Notifications — Google Cloud Pub/Sub

**What you need:**
1. Google Cloud Console → Create project (or use existing) → Enable Gmail API + Cloud Pub/Sub API
2. Create Pub/Sub topic: e.g. `luka-gmail-notifications`
3. Create subscription on that topic with push delivery to: `https://your-api.railway.app/webhooks/gmail`
4. Grant Gmail service account publish rights on the topic
5. Collect:
   - `GCP_PROJECT_ID` (your Google Cloud project ID)
   - `PUBSUB_AUDIENCE` = your Railway backend URL (used for OIDC token verification)

**Note:** Gmail watch subscriptions expire every 7 days. The `renew_mail_watches` ARQ cron job handles renewal automatically — but you need to call `POST /email/setup-gmail-watch` (or wire the initial watch setup) once after first login.

**Decision needed:**
- Do you have a Google Cloud project already? If you used one for Google OAuth above, you can reuse it.

---

### 1.5 Microsoft Azure — Outlook Push Notifications

**What you need:**
1. [Azure Portal](https://portal.azure.com) → App Registration (same registration you used for OAuth in 1.1)
2. In the app registration:
   - Add `Mail.Read` delegated permission
   - Configure redirect URI for your backend
3. Choose a random string for `OUTLOOK_CLIENT_STATE` (used to verify webhook authenticity)
4. Collect:
   - `MICROSOFT_CLIENT_ID`
   - `MICROSOFT_CLIENT_SECRET`
   - `OUTLOOK_CLIENT_STATE` (your chosen secret)

**Note:** Outlook push subscriptions expire every 3 days. The `renew_mail_watches` cron job handles this — same as Gmail.

---

### 1.6 OpenAI — LLM for Transaction Categorization

**What you need:**
1. [platform.openai.com](https://platform.openai.com) → Create API key
2. Add billing (gpt-4o-mini is ~$0.15/1M input tokens — very cheap for categorization)
3. Collect: `OPENAI_API_KEY`

**Decision needed:** Do you want to use OpenAI or another LLM? The code currently uses `gpt-4o-mini`. If you want to use a different model (Claude, Gemini), that requires a small code change in `backend/modules/merchants/llm.py`.

---

### 1.7 Fintoc — Chilean Open Banking (Optional for MVP)

**What you need:**
1. Request API access at [fintoc.com](https://fintoc.com) — they're a Chilean startup, sign up for sandbox
2. Collect: `FINTOC_API_KEY`

**Note:** Fintoc reconciliation is the "accuracy booster" — transactions still work without it (captured from emails). Fintoc adds the confirmed settlement amounts. You can skip this for initial launch and add later.

**Decision needed:** Do you want Fintoc at launch or post-launch?

---

## Phase 2: Infrastructure Setup

Once you have credentials, these steps deploy the app.

---

### 2.1 Run Database Migrations

After Supabase is set up and `DATABASE_URL` is configured:

```bash
cd backend
alembic upgrade head
```

This runs all 3 migrations:
1. `001` — Creates all 12 tables
2. `002` — Enables RLS + creates `get_partner_stats()` function
3. `003` — Adds Fintoc fields to bank_accounts

---

### 2.2 Deploy Backend to Railway

1. Create Railway project → "Deploy from GitHub repo"
2. Select the `backend/` folder as root
3. Add environment variables (all from Phase 1)
4. Add a second service: "ARQ Worker" with start command: `arq worker.WorkerSettings`
5. Add Redis as an add-on (if using Railway Redis)

Your Railway backend URL will be: `https://luka-api-XXXX.railway.app`

---

### 2.3 Deploy Frontend to Vercel

1. Connect GitHub repo to Vercel
2. Set root directory to `frontend/`
3. Add environment variables:
   ```
   NEXT_PUBLIC_API_URL=https://luka-api-XXXX.railway.app
   NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=...
   ```
4. Deploy

Your Vercel URL will be: `https://luka-XXXX.vercel.app`

Update `FRONTEND_URL` in Railway env vars to this Vercel URL (for CORS).

---

### 2.4 Configure OAuth Redirect URIs

After you have both URLs:

**Supabase Auth → Google OAuth:**
- Add redirect URI: `https://xxxx.supabase.co/auth/v1/callback`

**Supabase Auth → Microsoft OAuth:**
- Add redirect URI: `https://xxxx.supabase.co/auth/v1/callback`

**Vercel (frontend):**
- Add: `https://luka-XXXX.vercel.app/auth/callback` as an allowed redirect URL in Supabase

---

## Phase 3: Gaps to Close (Code Work)

These are code features that are missing or incomplete. Estimated scope per item.

---

### 3.1 Frontend Auth Middleware (Medium — ~2h)

**Problem:** Anyone can access `/household`, `/transactions`, etc. without being logged in. There's no Next.js middleware to redirect unauthenticated users.

**What to build:**
- `frontend/middleware.ts` at root
- Check Supabase session cookie
- If no session → redirect to `/login`
- Protected routes: `/`, `/transactions`, `/household`, `/budgets`, `/settings`
- Public routes: `/login`, `/auth/callback`, `/onboarding/*`

---

### 3.2 Accept-Invite Flow (Medium — ~3h)

**Problem:** `POST /households/{id}/invite` sends an email invite with a token — but there's no endpoint to accept it, and no frontend page that handles the invite link.

**What to build:**
- Backend: `GET /households/accept-invite?token=XXX` endpoint that finds the invite, creates `HouseholdMember`, marks invite accepted
- Frontend: `/invite?token=XXX` page that calls the endpoint and redirects to onboarding or dashboard

---

### 3.3 Populate Zustand Store on Login (Medium — ~2h)

**Problem:** After Google/Microsoft OAuth, the Zustand store (`householdId`, `userId`, `userFullName`) is empty. The dashboard will show loading spinners indefinitely because all hooks have `enabled: !!householdId`.

**What to build:**
- After OAuth callback (in `app/auth/callback/route.ts` or in the dashboard layout), call `GET /auth/me` to get user + household info
- Populate Zustand store via `setUser()` and `setHousehold()`

**Simplest fix:** In `app/(dashboard)/layout.tsx`, add a `useEffect` that calls `GET /auth/me` on mount and populates the store if empty.

---

### 3.4 SpendingChart Monthly Data (Small — ~2h)

**Problem:** `SpendingChart` always renders empty (`data={[]}`). There's no endpoint that returns month-by-month spending totals.

**What to build:**
- Backend: `GET /transactions/monthly-summary?household_id=X` — aggregate personal + shared totals grouped by month (last 6 months)
- Frontend: new `useMonthlySpending()` hook, wire into `app/(dashboard)/page.tsx`

---

### 3.5 WhatsApp Onboarding PIN Verification (Small — ~2h)

**Problem:** The onboarding step at `/onboarding/verify-whatsapp` exists in the UI but the backend verification logic (`whatsapp_verified = True` on User) isn't fully wired to the onboarding flow.

**What to build:**
- Backend: `POST /auth/verify-whatsapp` that takes `{phone, pin}`, validates, sets `user.whatsapp_verified = True`
- Frontend: connect the form in `verify-whatsapp/page.tsx` to this endpoint

---

### 3.6 Fintoc Link UI Flow (Large — ~1 day, optional for MVP)

**Problem:** `run_fintoc_sync` cron needs `fintoc_link_id` and `fintoc_account_id` on `BankAccount`. These are set during Fintoc's OAuth flow, but there's no UI for it yet.

**What to build:**
- A "Connect bank via Fintoc" button in onboarding or settings
- Open Fintoc's Link widget (their JS SDK)
- On success, call backend endpoint to store `fintoc_link_id` + `fintoc_account_id`

**Note:** Skip if launching email-only first.

---

## Phase 4: Before First Real User

Checklist before sharing Luka with anyone:

- [ ] All Phase 1 credentials obtained and loaded into Railway/Vercel
- [ ] `alembic upgrade head` run on production DB
- [ ] Health check passes: `GET /health → {"status":"ok","app":"luka"}`
- [ ] Can log in with Google or Microsoft account
- [ ] Dashboard loads (no infinite spinner) — need 3.3 fix
- [ ] Auth middleware redirects logged-out users — need 3.1 fix
- [ ] WhatsApp sends test message successfully
- [ ] Gmail webhook receives a test email
- [ ] Pre-commit hooks active: `pre-commit install`

---

## Recommended Execution Order

```
Week 1: Get credentials
  → 1.1 Supabase (database + auth)
  → 1.2 Redis (Railway add-on)
  → 1.3 WhatsApp Cloud API
  → 1.6 OpenAI API key

Week 1: First deploy
  → 2.1 alembic upgrade head
  → 2.2 Railway backend
  → 2.3 Vercel frontend
  → 2.4 OAuth redirect URIs
  → Verify /health passes

Week 2: Fix critical gaps
  → 3.3 Populate Zustand store on login (blocking — dashboard broken without this)
  → 3.1 Auth middleware (security)
  → 3.2 Accept-invite flow (needed for couple use)
  → 3.5 WhatsApp PIN verify

Week 2: Gmail + Outlook
  → 1.4 Google Cloud Pub/Sub setup
  → 1.5 Azure app permissions
  → Test end-to-end: bank email → transaction captured → WhatsApp alert

Week 3: Polish
  → 3.4 SpendingChart monthly data
  → 3.6 Fintoc (if desired)
  → Write yourself a test transaction email and verify the full pipeline
```

---

## Quick Reference: Decisions Summary

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1.1 | Supabase: one vs separate dev/prod projects | One or two | Two (dev + prod) to avoid testing against real data |
| 1.2 | Redis provider | Railway add-on, Upstash, Redis Cloud | Railway add-on (easiest, same infra) |
| 1.3 | WhatsApp: personal vs business | Your number vs approved WABA | Start with test number, go through approval when ready for real users |
| 1.6 | LLM: OpenAI vs other | OpenAI, Claude, Gemini | OpenAI gpt-4o-mini (already coded, cheapest, best for structured output) |
| 1.7 | Fintoc at launch? | Yes / No / Later | Later — email capture works without it |
| 3.6 | Fintoc link UI for MVP? | Yes / No | No for MVP, yes for v1.1 |
