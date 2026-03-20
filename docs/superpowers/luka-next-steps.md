# Luka — What Needs Your Input & How to Continue
**Date:** 2026-03-20

This document walks through every decision and credential that requires your input before Luka can go live, ordered by dependency.

## ✅ Completed (all sessions to date)

- **Supabase** — project live, all credentials loaded
- **Redis** — Railway add-on configured
- **OpenAI** — API key loaded in Railway
- **Database migrations** — all 9 migrations at `009 head` (008: performance indexes, 009: last_synced_at + import_started_at on bank_accounts)
- **Note:** run future migrations manually: `cd backend && python3 -m alembic upgrade head`
- **Railway backend** — live at `https://luka-production-eb87.up.railway.app`
- **Vercel frontend** — live at `https://luka-lovat.vercel.app`
- **WhatsApp Cloud API** — **Verified in Live Mode**. Webhooks/Sender fully functional. ✅
- **Legal Documentation** — Privacy Policy, Terms, and Data Deletion pages live (Meta compliant). ✅
- **Branding** — New custom minimalist logo generated. ✅
- **Gap 3.1** — Auth middleware (`frontend/middleware.ts`) ✅
- **Gap 3.2** — Accept-invite flow (backend + frontend page) ✅
- **Gap 3.3** — Zustand store initialization (`StoreInitializer`) ✅
- **Gap 3.4** — SpendingChart monthly data (backend endpoint + hook) ✅
- **Gap 3.6** — Fintoc bank connect UI flow (onboarding + settings) ✅
- **Gap 3.7** — Connected accounts list in settings (with reveal toggle + disconnect button) ✅
- **Bug fix** — Fintoc movements endpoint corrected (proper URL path with link token, correct auth format) ✅
- **Bug fix** — Worker healthcheck removed from railway.toml (worker no longer fails to start) ✅
- **Bug fix** — job_timeout increased to 300s for Fintoc history import ✅
- **Feature** — Fintoc history import working end-to-end (confirmed in production: 200 transactions saved) ✅
- **Security** — Inactivity auto-logout after 1h ✅
- **Bug fix** — User auto-provisioning on first OAuth login (no more 401 "User not found") ✅
- **Bug fix** — Token refresh before API calls (`getUser()` before `getSession()`) ✅
- **Bug fix** — React hydration error #418 (dynamic SSR:false wrapper on client-only components) ✅
- **Bug fix** — CORS errors from 307 redirects resolved ✅
- **Bug fix** — asyncpg PgBouncer compatibility (`statement_cache_size=0`) ✅
- **Bug fix** — Fintoc DataCloneError (`Window.prototype.postMessage` patch) ✅
- **Infra fix** — Railway domain rotated to `luka-production-eb87` (stale domain routing fixed) ✅
- **Feature** — Transactions: 6-month fetch with no row cap, full client-side filtering ✅
- **Feature** — Transactions: pagination (10/30/100 per page, prev/next/first/last buttons) ✅
- **Feature** — Transactions: category filter + uncategorized toggle ✅
- **Feature** — Transactions: summary bar shows current-month by default, updates label on month filter ✅
- **Feature** — Bank account hard delete cascades splits → transactions → account ✅
- **Feature** — Import status: stale guard (15 min timeout), import_started_at + last_synced_at columns (migration 009) ✅
- **Feature** — Settings: smart polling while first import active, stops when done ✅
- **Bug fix** — Railway startup crash (wrong module for require_membership) ✅
- **Bug fix** — Vercel TypeScript build errors (queryKeys type, hasActiveFirstImport type) ✅
- **Bug fix** — Stale transaction cache after bank account delete now invalidated ✅
- **Bug fix** — python-dateutil missing from pyproject.toml ✅
- **Maintenance** — 42 orphan transactions cleaned from production DB ✅
- **Feature** — Fintoc classifier: INCOME / EXPENSE / TRANSFER / INBOUND_TRANSFER_SKIP detection ✅
- **Feature** — Personal budget service: waterfall ceiling, pace chart, household + personal blocks ✅
- **Feature** — Allocation service: 50/20/30 suggestions (historical + recommended), upsert ✅
- **Feature** — Budget API: 3 new endpoints (personal, allocation GET/POST) ✅
- **Feature** — Frontend: PaceChart (Recharts), AllocationCard (dual sliders), WaterfallCards ✅
- **Feature** — Budgets page rewritten with month selector, income header, pace, allocation, waterfall ✅
- **DB migration** — Migration 011: transaction_type, transfer_to_account_id, household_budget_allocations ✅

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

**Done.** All credentials loaded and verified end-to-end.

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

- **2.1** Database migrations — done (`011 head`)
- **2.2** Railway backend — live at `https://luka-production-eb87.up.railway.app`
- **2.3** Vercel frontend — live at `https://luka-lovat.vercel.app`
- **2.4** Supabase redirect URL configured for Vercel callback

---

## Phase 3: Gaps to Close (Code Work)

### ✅ 3.1 Frontend Auth Middleware — DONE
### ✅ 3.2 Accept-Invite Flow — DONE
### ✅ 3.3 Populate Zustand Store on Login — DONE
### ✅ 3.4 SpendingChart Monthly Data — DONE
### ✅ 3.6 Fintoc Bank Connect UI Flow — DONE

---

### 3.5 WhatsApp Onboarding PIN Verification (Small — ~2h)

**Problem:** The onboarding step at `/onboarding/verify-whatsapp` exists in the UI but the backend verification logic (`whatsapp_verified = True` on User) isn't fully wired to the onboarding flow.

**What to build:**
- Backend: `POST /auth/verify-whatsapp` that takes `{phone, pin}`, validates, sets `user.whatsapp_verified = True`
- Frontend: connect the form in `verify-whatsapp/page.tsx` to this endpoint

---

### ✅ 3.7 Connected Accounts List in Settings — DONE

Settings page shows connected bank accounts with type/kind tags, masked account number with reveal toggle, and a disconnect button.

---

## Phase 4: Before First Real User

Checklist before sharing Luka with anyone:

- [x] All Phase 1 credentials obtained and loaded into Railway/Vercel
- [x] `alembic upgrade head` run on production DB (at `011 head`)
- [x] Health check passes: `GET /health → {"status":"ok","app":"luka"}`
- [ ] Can log in with Google or Microsoft account — **blocked on GCP OAuth setup (1.4)**
- [x] Dashboard loads (no infinite spinner)
- [x] Auth middleware redirects logged-out users
- [x] User row auto-created on first login (no more 401 "User not found")
- [ ] Fintoc widget opens and connects a real bank account end-to-end — **needs real Fintoc sandbox test**
- [x] WhatsApp sends test message successfully (verified 2026-03-20)
- [x] Legal pages live and accessible (verified 2026-03-20)
- [ ] Gmail webhook receives a test email — **blocked on GCP Pub/Sub setup (1.4)**
- [x] Pre-commit hooks active: `pre-commit install`

---

## Recommended Execution Order

```
✅ Week 1: Credentials + first deploy — COMPLETE
✅ Week 2: Critical code gaps — COMPLETE (3.1, 3.2, 3.3, 3.4)
✅ Week 3: Fintoc UI + all critical bug fixes — COMPLETE (3.6, user provisioning, hydration, CORS)
✅ Week 4: Fintoc history import working + settings connected accounts + Fintoc API bug fixes — COMPLETE
✅ Week 5 (2026-03-20): Transaction UX overhaul (pagination, filters, smart summary) + import status stale guard + production bug fixes — COMPLETE
✅ Week 6 (2026-03-20): Budgeting waterfall — Fintoc classifier, personal budget service, pace chart, allocation editor, waterfall cards, budgets page rewrite, migration 011 — COMPLETE

Next: Enable login (blocking everything else)
  → 1.4 Google Cloud: create OAuth 2.0 credentials → enable in Supabase Auth → Google
  → 1.5 Azure: app registration + Mail.Read permission → enable in Supabase Auth → Azure
  → Test: can log in with real Google/Microsoft account
  → Test: Fintoc widget opens and connects real bank account

Next: Enable email pipeline
  → 1.4 GCP Pub/Sub topic + Gmail webhook push subscription
  → 1.5 Azure Mail.Read delegated permission
  → Test end-to-end: bank email → transaction captured → WhatsApp alert

Polish (optional, can do anytime):
  → 3.5 WhatsApp PIN verify (once WhatsApp credentials available)
  → 3.7 Connected accounts list in settings (~1h)
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
