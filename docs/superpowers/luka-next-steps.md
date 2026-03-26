# Luka — What Needs Your Input & How to Continue
**Date:** 2026-03-26 (session 9)

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
- **DB migration** — Migration 012: balance_available, balance_current columns on bank_accounts ✅
- **Feature** — `POST /bank-accounts/sync-balances` endpoint: fetches Fintoc balances and updates DB ✅
- **Feature** — "Actualizar saldos" button in settings triggers balance sync ✅
- **Feature** — Transactions page: Todos/Personales/Compartidas tabs with correct counts (account_type filtering) ✅
- **Feature** — Transactions: income/expense direction via transaction_type (not amount sign) ✅
- **Feature** — Transactions: parenthetical outflow format `($amount)`, green `+$amount` for income ✅
- **Feature** — Transactions: per-type category lists (income: Sueldo/Freelance/etc, expense: Alimentación/etc) ✅
- **Feature** — Transactions: instant optimistic category updates with revert-on-error ✅
- **Feature** — BudgetPrefetcher: fires prefetchQuery on any dashboard page so budget tab loads from cache ✅
- **Bug fix** — SQLAlchemy FK metadata: merchants model was never imported → NoReferencedTableError on commit ✅
- **Bug fix** — Budget GROUP BY: `func.sum(Transaction.amount)` caused ORM entity injection; rewrote as pure text() SQL ✅
- **Bug fix** — React error #301: `setPage(1)` called inside useMemo (setState during render); moved to useEffect ✅
- **Bug fix** — transaction_type and account_kind missing from Pydantic TransactionResponse schema (FastAPI strips undeclared fields) ✅
- **Bug fix** — Dashboard pie chart mixed income with expenses; now filters to expenses only ✅
- **Bug fix** — Dashboard pie chart hid uncategorized transactions; now shows them as "Otros" so chart is always populated ✅
- **Performance** — Eliminated triple auth call chain: middleware getUser()→getSession(), layout getUser() removed, backend sync Supabase SDK → local PyJWT+JWKS ✅
- **Performance** — All 8 dashboard queries prefetched in StoreInitializer (was 2), BudgetPrefetcher removed ✅
- **Performance** — Dynamic Recharts imports (~200KB deferred), Next.js optimizePackageImports ✅
- **Performance** — Redis user profile cache (5-min TTL) in get_current_user ✅
- **Performance** — Shared DB session via Depends(get_db) in get_current_user (was opening its own session) ✅
- **Performance** — Connection pool tuning: pool_size=5, max_overflow=10, pool_recycle=3600 ✅
- **Architecture** — CORS origins from config (settings.cors_origins env var) ✅
- **Architecture** — CacheHeaderMiddleware: private, max-age=30 on GET endpoints ✅
- **Architecture** — useImportStatus rewritten to use React Query refetchInterval ✅
- **Architecture** — InactivityGuard: added visibilitychange listener ✅
- **Cleanup** — Removed 2.9GB abandoned worktrees (.worktrees/) ✅
- **Cleanup** — Moved Design ideas/ → docs/design-mockups/, Features Ideas/ deleted, railway.worker.md → docs/ ✅
- **Cleanup** — Updated .gitignore: .superpowers, .cursor-plugin/, .claude-plugin/, .ruff_cache/ ✅
- **Docs** — New product documentation: architecture.md, api-reference.md, deployment.md, development.md, roadmap.md ✅
- **Docs** — Root README.md rewritten with tech stack, quick start, project structure ✅
- **Docs** — frontend/README.md replaced (was default Next.js boilerplate) ✅
- **Bug fix** — JWT auth: PyJWT+JWKS for ES256 (Supabase migrated to ECC P-256), fallback chain ES256→HS256→SDK ✅
- **Bug fix** — Transaction dates shifted by timezone (UTC midnight → Chile UTC-3 = previous day); now parses date-only ✅
- **Dependency** — Added PyJWT[crypto] to pyproject.toml ✅
- **Config** — Added supabase_jwt_secret and cors_origins to Settings ✅
- **Frontend Redesign Tier 1** — DM Sans typography, card-based transaction rows, bottom sheets (category + split type), collapsible mobile filters, underline tabs, gradient direction icons, date-grouped transactions ✅
- **Frontend Redesign Tier 2** — Settings page full redesign: 7 sections (Profile, Bank Accounts, Hogar, Notifications, Categories, Privacy, Delete Account) ✅
- **Feature** — Profile editing: PATCH /auth/me (name + phone_whatsapp) ✅
- **Feature** — Notification preferences: GET/PATCH /notifications/preferences with optimistic toggle ✅
- **Feature** — Category preferences: drag-and-drop reorder + hide/show, split into Ingresos/Gastos columns ✅
- **Feature** — Delete account: application-level cascade delete + Supabase auth cleanup ✅
- **Feature** — Hogar section: member info with email, invite partner with shareable link + copy button ✅
- **Feature** — Invite flow: self-invite protection, "Cambiar de cuenta" button, cookie-based post-login redirect ✅
- **Feature** — Resend email integration for transactional emails (Railway blocks SMTP) ✅
- **Feature** — Google OAuth token encrypted storage (Fernet) in users table ✅
- **DB migrations** — 013: phone_whatsapp on users, 014: notification_preferences, 015: user_category_preferences, 016: google_access_token_enc + google_refresh_token_enc ✅
- **Bug fix** — PATCH /auth/me: re-fetch user from DB session (cached user was detached) ✅
- **Bug fix** — apiFetch: extract backend error detail instead of generic "API error 400" ✅
- **Style** — Login + onboarding pages polished (rounded-xl, focus rings, step indicator shadows) ✅
- **Style** — Account type: removed "Pareja" option, renamed "Compartida" to "Hogar" ✅
- **Feature** — WhatsApp PIN verification: send/verify endpoints with Redis TTL + brute-force protection (5 attempts) ✅
- **Feature** — WhatsApp PIN onboarding UI wired (send PIN, verify, skip option) ✅
- **Feature** — Gmail Pub/Sub pipeline end-to-end: webhook → ARQ worker → email fetch → WhatsApp notification ✅
- **Feature** — Gmail watch setup endpoint (POST /auth/setup-email-watch) ✅
- **Feature** — OAuth callback captures provider_token + provider_refresh_token, stores encrypted in backend ✅
- **Feature** — GmailProvider: auto-refresh tokens, persist refreshed token back to DB ✅
- **Feature** — Fallback email fetch: when History API returns empty, fetches latest INBOX message ✅
- **Feature** — WhatsApp email notifications include sender, subject, and Chile-timezone received time ✅
- **Infra** — GCP Pub/Sub OIDC authentication configured with service account ✅
- **Bug fix** — scalar_one_or_none in auth router for stale cached users ✅
- **Bug fix** — Redis user cache invalidation when JWT sub doesn't match cached ID ✅
- **Bug fix** — Force Google refresh token on every login (access_type=offline, prompt=consent) ✅
- **Feature** — Email pre-filter: 27 Spanish financial keywords, bank-agnostic ✅
- **Feature** — Parser: HTML stripping + Banco de Chile compra/comprobante formats ✅
- **Feature** — Gemini 2.5 Flash-Lite replaces OpenAI gpt-4o-mini for merchant categorization ✅
- **Feature** — Merchant service: 1 category for known merchants, 3 for new ✅
- **Feature** — Full WhatsApp transaction flow: split → category → ✅ confirmation ✅
- **Feature** — Email-only users: bank account not required for email pipeline ✅
- **Feature** — Per-email transaction dedup via Redis (24h TTL) ✅
- **Bug fix** — Merchant duplicate race condition (IntegrityError → rollback + re-query) ✅
- **Bug fix** — WhatsApp session phone normalization (+prefix mismatch) ✅
- **Bug fix** — All split types now ask for category (Mío/Pareja were skipping) ✅
- **Bug fix** — WhatsApp webhook error logging (was silent except:pass) ✅
- **Bug fix** — Removed TEMP debug WhatsApp notifications ✅
- **Docs** — Banco de Chile email templates in docs/email-templates/ ✅
- **Feature** — PendingBlock: 2-bucket UI (awaiting reconciliation + unmatched email), inline delete with confirm-in-place, inline category dropdown matching regular cards ✅
- **Feature** — Category editing on pending cards trains merchant_category_selections (feedback loop) ✅
- **Feature** — PendingBlock prefetched in StoreInitializer — no waterfall delay on page load ✅
- **Feature** — Cross-sender dedup: 5-min window prevents BChile double-entry ✅
- **Feature** — Non-Fintoc users: email txns set to settled immediately ✅
- **Fix** — WhatsApp split labels Personal/Hogar (was Mío/Compartido) ✅
- **Fix** — LLM constrained to fixed category list matching frontend ✅
- **Fix** — Desktop transaction list was missing parentheses on outflows ✅
- **Feature** — Luka Connect: standalone bank scraping service (separate repo `luka-connect`) ✅
- **Feature** — Luka Connect: Express API with /scrape + /health, Dockerized with Chromium + Xvfb ✅
- **Feature** — Luka Connect: 9 Chilean bank scrapers (Banco de Chile enhanced, others from fork) ✅
- **Refactor** — Fintoc removed entirely: module, tests, jobs, endpoints, config, frontend widget ✅
- **Feature** — bank_connect module: AES-256-GCM encryption, BankCredential model, service, mapper, router ✅
- **Feature** — bank_connect: 6 API endpoints (connect/disconnect/sync/status/connections/webhook) ✅
- **Feature** — bank_connect: ARQ jobs (schedule_connect_syncs hourly cron + run_connect_sync) ✅
- **Feature** — Migration 017: drop Fintoc columns, create bank_credentials table with RLS ✅
- **Feature** — Frontend: bank credential entry modal (3-screen: form → 2FA → success) ✅
- **Feature** — Frontend: sync status UI in settings (connection cards, manual sync, disconnect) ✅
- **Feature** — Frontend: Luka Connect API methods in api.ts ✅

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

### 1.4 Gmail Push Notifications — Google Cloud Pub/Sub ✅ DONE

**Configured:**
- GCP project: `luka-490500`
- Pub/Sub topic: `luka-gmail-notifications`
- Push subscription: `gmail-push-sub` → `https://luka-production-eb87.up.railway.app/webhooks/gmail`
- OIDC auth: service account `luka-pubsub-push@luka-490500.iam.gserviceaccount.com`
- Gmail API + Pub/Sub API enabled
- `gmail-api-push@system.gserviceaccount.com` granted Publisher on topic
- Google OAuth scopes include `gmail.readonly` (bundled at login time)
- Gmail watch active, expires every 7 days, auto-renewed by `renew_mail_watches` cron
- **End-to-end tested**: email received → WhatsApp notification sent ✅

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

### 1.6 Gemini — LLM for Transaction Categorization ✅ DONE

Swapped from OpenAI gpt-4o-mini to Google Gemini 2.0 Flash (cheaper, async SDK). API key loaded locally. **TODO:** Add `GEMINI_API_KEY` to Railway env vars.

---

### 1.7 ~~Fintoc~~ → Luka Connect ✅ REPLACED

Fintoc has been removed and replaced by **Luka Connect** — a standalone bank scraping service.

**What still needs to be done:**
1. Deploy `luka-connect` repo to a new Railway project (see `luka-connect/docs/implementation-status.md`)
2. Set env vars on Luka backend: `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL`
3. Run `alembic upgrade head` on production Supabase (migration 017)
4. Test end-to-end: onboarding → enter Banco de Chile creds → approve 2FA → transactions imported

---

## Phase 2: Infrastructure Setup ✅ COMPLETE

- **2.1** Database migrations — done (`016 head`)
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

### ✅ 3.5 WhatsApp Onboarding PIN Verification — DONE

Backend: `POST /auth/send-whatsapp-pin` + `POST /auth/verify-whatsapp-pin` with Redis-backed PIN (5-min TTL), brute-force protection (5 attempts). Frontend: onboarding page wired with countdown, resend, skip option.

---

### ✅ 3.7 Connected Accounts List in Settings — DONE

Settings page shows connected bank accounts with type/kind tags, masked account number with reveal toggle, and a disconnect button.

---

## Phase 4: Before First Real User

Checklist before sharing Luka with anyone:

- [x] All Phase 1 credentials obtained and loaded into Railway/Vercel
- [x] `alembic upgrade head` run on production DB (at `011 head`)
- [x] Health check passes: `GET /health → {"status":"ok","app":"luka"}`
- [x] Can log in with Google account (Gmail OAuth + gmail.readonly scope) ✅
- [x] Dashboard loads (no infinite spinner)
- [x] Auth middleware redirects logged-out users
- [x] User row auto-created on first login (no more 401 "User not found")
- [x] Luka Connect deployed to Railway and /health verified ✅ (2026-03-26)
- [x] Migration 017 run on production Supabase ✅ (2026-03-26)
- [x] Backend env vars set ✅ (2026-03-26)
- [x] Bank connect tested end-to-end: 291 transactions imported from Banco de Chile ✅ (2026-03-26)
- [ ] Auto-create bank accounts from scraped data (accountNumber/accountName/currency)
- [ ] Store balances and credit card cupos from scrape data
- [ ] Show bank/account info on transaction rows
- [x] WhatsApp sends test message successfully (verified 2026-03-20)
- [x] Legal pages live and accessible (verified 2026-03-20)
- [x] Gmail webhook receives email and sends WhatsApp notification ✅ (tested 2026-03-24)
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

✅ Week 7 (2026-03-24): Gmail pipeline + WhatsApp PIN verification — COMPLETE
  → Gmail OAuth tokens captured at login, encrypted, stored in DB
  → GCP Pub/Sub configured with OIDC auth
  → Email pipeline end-to-end: Gmail → webhook → worker → WhatsApp notification
  → WhatsApp PIN verification fully wired (backend + frontend)

✅ Week 8 (2026-03-24): Email pre-filter + Gemini LLM + parser fix — COMPLETE
  → Keyword-based email pre-filter (27 Spanish financial terms) skips non-bank emails
  → Gemini 2.0 Flash replaces OpenAI gpt-4o-mini (cheaper, async SDK, lazy client init)
  → Merchant service: 1 category for known merchants, 3 for new (was 4 for all)
  → Parser: strips HTML before regex, fixed merchant extraction for real Banco de Chile emails
  → Email templates folder for Banco de Chile (3 formats)
  → 21 new tests, all passing

✅ Week 9 (2026-03-25): PendingBlock polish + pipeline alignment — COMPLETE
  → PendingBlock: 3-bucket logic → 2-bucket UI (removed needs_classification flood)
  → Cross-sender dedup: 5-min amount+user window prevents BChile compra+comprobante double entry
  → Non-Fintoc users: email txns set to status=settled immediately (nothing to reconcile)
  → Inline optimistic delete with confirm-in-place (no browser dialog, no refetch race)
  → Category editing on pending cards: same inline dropdown as regular cards
  → Merchant training: update_category now calls record_category_selection (WhatsApp + dashboard)
  → PendingBlock prefetched in StoreInitializer alongside all other dashboard queries
  → WhatsApp split labels: Personal/Hogar (was Mío/Compartido)
  → LLM category list constrained to fixed frontend list (no invented categories)
  → Fixed desktop transaction list showing expenses without parentheses

✅ Week 10 (2026-03-26): Luka Connect + Fintoc removal — COMPLETE
  → Built luka-connect: standalone Node.js/Express bank scraping API (separate repo)
  → 9 Chilean bank scrapers (Banco de Chile enhanced, others from fork)
  → Dockerized with Chromium + Xvfb, pushed to GitHub
  → Removed Fintoc entirely: module, tests, jobs, endpoints, config, frontend
  → New bank_connect module: encryption (AES-256-GCM), models, service, mapper, router, ARQ jobs
  → Migration 017: drops Fintoc columns, creates bank_credentials + source_type
  → Frontend: credential entry modal (onboarding), sync status UI (settings)
  → 109 backend tests passing, frontend build clean

  → Deployed to Railway, all env vars set, migration 017 applied
  → Fintoc-style multi-step bank selector with bank logos
  → Connecting flow: polls sync-status → confirms session started → success screen
  → 291 real Banco de Chile transactions imported successfully
  → Fixed: date parser (multi-format), webhook processing (skip invalid dates, pre-fetch lookups)
  → Fixed: 2FA conditional per bank, unified settings card, no user waiting for scrape

Next: Auto-create bank accounts + balances from scrape data
  → See docs/luka-connect-next-session.md for full requirements
  → Scraper returns accountNumber, accountName, currency, balance per movement
  → Need: auto-create bank_account rows, link transactions, store balances, show in frontend
  → Need: credit card cupos (nacional/internacional used/available/total)
  → Priority: this unlocks meaningful dashboard data (balances, account filtering)

Next: Multi-bank parser support
  → Each bank has different email formats — need per-bank parser patterns
  → Banks to support (priority order):
    1. Banco de Chile — ✅ compra + comprobante de pago working, transferencia needs recipient parsing
    2. Banco Falabella — user already receiving emails, need email samples to build patterns
    3. Banco Santander — existing test pattern, needs validation against real emails
    4. BCI — existing test pattern, needs validation against real emails
    5. Banco Estado — common in Chile, need email samples
    6. Banco Itaú / Scotiabank — need email samples
  → Approach: add bank-specific parser modules under backend/modules/email/parsers/
  → Each module exports parse_<bank>_email() with bank-specific regex
  → Router in parse_bank_email() tries all parsers, returns first match
  → Reference templates in docs/email-templates/<bank-name>/

Next: Deduplication
  → Banco de Chile sends pairs: "Compra con TC" (enviodigital) + "Comprobante de Pago" (serviciodetransferencias) for the same purchase
  → Deduplicate by (amount + merchant + date within 5-min window) before creating transaction
  → Or: only process one sender per bank (e.g. prefer enviodigital, skip serviciodetransferencias comprobantes)

Next: Complete transaction pipeline
  → Test with real Chilean bank email → parsed transaction → WhatsApp alert with category options
  → Create WhatsApp message templates (verification_code, transaction_alert) for 24h window bypass
  → Remove TEMP debug notification code

Next: Microsoft Azure / Outlook support
  → 1.5 Azure app registration + Mail.Read permission
  → Enable Microsoft OAuth in Supabase Auth
  → Wire OutlookProvider token storage (same pattern as Gmail)

✅ Session 9 (2026-03-26): Household Enhancement + Subscriptions Tab — COMPLETE
  → Household page rewrite: hero card, per-category breakdown table, settlement card
  → Settlement: "X debe transferir $Y a Z" based on configurable split ratio (50/50 default)
  → Split ratio: PATCH endpoint + modal UI, migration 019 (households.split_ratio JSONB)
  → New subscriptions module: auto-detects recurring merchants (2+ consecutive months, 20% tolerance)
  → Subscriptions page: KPI cards + vertical timeline + price change alerts
  → Nav: "Suscripciones" added to sidebar + "Suscrip." in mobile bottom nav
  → 10 new unit tests, 12 commits, frontend build clean

Next: P0 Features (see docs/roadmap.md)
  → Category budget alerts via WhatsApp
```

---

## Quick Reference: Decisions Summary

| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|
| 1.1 | Supabase: one vs separate dev/prod projects | One or two | Two (dev + prod) to avoid testing against real data |
| 1.2 | Redis provider | Railway add-on, Upstash, Redis Cloud | Railway add-on (easiest, same infra) |
| 1.3 | WhatsApp: personal vs business | Your number vs approved WABA | Start with test number, go through approval when ready for real users |
| 1.6 | LLM: Gemini 2.0 Flash | — | Switched from OpenAI (Gemini is cheaper, user has Google account) |
| 1.7 | ~~Fintoc~~ | Replaced by Luka Connect | Direct bank scraping via luka-connect service |
