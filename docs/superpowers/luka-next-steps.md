# Luka — What Needs Your Input & How to Continue
**Date:** 2026-03-18

This document walks through every decision and credential that requires your input before Luka can go live, ordered by dependency.

## ✅ Completed This Session

- **Supabase** — project live, all credentials loaded
- **Redis** — Railway add-on configured
- **OpenAI** — API key loaded in Railway
- **Database migrations** — `alembic upgrade head` run, all 3 migrations at `003 head`
- **Railway backend** — live at `https://luka-production-14f5.up.railway.app`
- **Vercel frontend** — live at `https://luka-lovat.vercel.app`
- **Gap 3.1** — Auth middleware (`frontend/middleware.ts`) ✅
- **Gap 3.2** — Accept-invite flow (backend + frontend page) ✅
- **Gap 3.3** — Zustand store initialization (`StoreInitializer`) ✅
- **Gap 3.4** — SpendingChart monthly data (backend endpoint + hook) ✅
- **Security** — Inactivity auto-logout after 1h ✅

---

---

## Phase 1: External Services (Blocking — do these first)

These are third-party accounts you need to create or configure. Without them, the app cannot run.

---

### 1.1 Supabase — Database + Auth ✅ DONE

Project live at `mvovcodijqjvzxxthsxg.supabase.co`. All credentials loaded.

**Still needed:** Enable Google OAuth and Microsoft OAuth providers in Supabase → Auth → Providers. Requires GCP OAuth credentials (see 1.4) and Azure app registration (see 1.5).

---

### 1.2 Redis — Job Queue ✅ DONE

Railway add-on configured. `REDIS_URL` auto-injected.

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

### 1.6 OpenAI — LLM for Transaction Categorization ✅ DONE

API key loaded in Railway.

---

### 1.7 Fintoc — Chilean Open Banking (Optional for MVP)

**What you need:**
1. Request API access at [fintoc.com](https://fintoc.com) — they're a Chilean startup, sign up for sandbox
2. Collect: `FINTOC_API_KEY`

**Note:** Fintoc reconciliation is the "accuracy booster" — transactions still work without it (captured from emails). Fintoc adds the confirmed settlement amounts. You can skip this for initial launch and add later.

**Decision needed:** Do you want Fintoc at launch or post-launch?

---

## Phase 2: Infrastructure Setup ✅ COMPLETE

- **2.1** Database migrations — done (`003 head`)
- **2.2** Railway backend — live at `https://luka-production-14f5.up.railway.app`
- **2.3** Vercel frontend — live at `https://luka-lovat.vercel.app`
- **2.4** Supabase redirect URL configured for Vercel callback

---

## Phase 3: Gaps to Close (Code Work)

### ✅ 3.1 Frontend Auth Middleware — DONE
### ✅ 3.2 Accept-Invite Flow — DONE
### ✅ 3.3 Populate Zustand Store on Login — DONE
### ✅ 3.4 SpendingChart Monthly Data — DONE

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

- [x] All Phase 1 credentials obtained and loaded into Railway/Vercel
- [x] `alembic upgrade head` run on production DB
- [x] Health check passes: `GET /health → {"status":"ok","app":"luka"}`
- [ ] Can log in with Google or Microsoft account — **blocked on GCP OAuth setup (1.4)**
- [x] Dashboard loads (no infinite spinner)
- [x] Auth middleware redirects logged-out users
- [ ] WhatsApp sends test message successfully — **blocked on Meta credentials (1.3)**
- [ ] Gmail webhook receives a test email — **blocked on GCP Pub/Sub setup (1.4)**
- [x] Pre-commit hooks active: `pre-commit install`

---

## Recommended Execution Order

```
✅ Week 1: Credentials + first deploy — COMPLETE
✅ Week 2: Critical code gaps — COMPLETE (3.1, 3.2, 3.3, 3.4)

Next: Enable login
  → 1.4 Google Cloud: create OAuth 2.0 credentials → enable in Supabase Auth → Google
  → 1.5 Azure: app registration + Mail.Read permission → enable in Supabase Auth → Azure
  → Test: can log in with real Google/Microsoft account

Next: Enable email pipeline
  → 1.3 WhatsApp Cloud API (Meta for Developers)
  → 1.4 GCP Pub/Sub topic + Gmail webhook push subscription
  → 1.5 Azure Mail.Read delegated permission
  → Test end-to-end: bank email → transaction captured → WhatsApp alert

Later: Polish
  → 3.5 WhatsApp PIN verify (once WhatsApp credentials available)
  → 3.6 Fintoc link UI (optional, post-MVP)
  → Write a test transaction email and verify the full pipeline
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
