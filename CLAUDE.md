# Luka — Claude Development Guide

Luka is a Latin American personal finance SaaS for individuals, couples, and groups of people. It automatically captures transactions from bank email notifications (Gmail/Outlook), bank scraping (Luka Connect), and open banking (Plaid for US); classifies them via LLM; enables actions via WhatsApp; and visualizes spending on a responsive web dashboard. The platform is LATAM-first — supporting CL, CO, MX, PE, BR, and US — with a three-layer email parser (declarative templates → Gemini LLM waterfall → legacy regex) covering 101 banks across 6 countries.

---

## Problem to be Solved

- **User:** Difficulty managing personal finances (expenditure, budgeting, income, etc.) across multiple bank accounts, fintech accounts, cards, shared/household expenses, subscriptions, and currencies.
- **Customer (B2B):** Low to no access to good-quality financial behavior data from Latin American individuals for fintechs and financial institutions to assess and offer tailored, profitable financial products.

---

## Target User

Latin American mid-to-high income banked or semi-banked individuals with any level of financial knowledge, wanting to track their expenses and optimize their personal finance management.

---

## Value-add to the User

1. One-stop automated platform (web + app) to smoothly track, understand, analyze, and act on all personal finances.
2. AI-generated classification and automatic notification of every income and expense transaction — live, not on a weekly or monthly basis.
3. Single application combining what users currently do across multiple apps (e.g., Splitwise, Rocket Money, traditional bank apps) — not necessarily replacing them, but connecting and displaying everything in one place.
4. Predictive budgeting and personalized best practices to achieve specific financial goals, based on the user's own behavior.

---

## Target Customer

- Latin American fintechs and financial institutions looking to provide credit and offer financial products to creditworthy individuals.
- Eventually, other institutions wanting to understand individual financial behavior to offer products or services (e.g., consumer goods, travel and leisure companies).

---

## Value-add to the Customer

1. Structured and detailed individual financial behavior data (aggregated or individual) to make creditworthiness predictions and offer personalized financial products to current or new customers.
2. Centralized channel to access a pool of creditworthy individuals who previously had no relationship with their institution.

---

## Business Model

Two-sided revenue stream:
- **Users** pay a small subscription to use the app with their data kept private.
- **B2B customers** pay for aggregated, anonymized financial behavior data — similar to YouTube's ad model where users can pay to opt out.

The user always comes first. A large, happy user base generating behavioral data is the foundation that makes the B2B product valuable. Never compromise user trust or experience for short-term B2B gain.

The model can evolve. If during development you spot a new revenue opportunity or a structural improvement, flag it.

---

## Tech Stack (summary)

| Layer | Stack |
|-------|-------|
| Backend | Python 3.12 + FastAPI 0.111, SQLAlchemy 2.0 async, ARQ queue, Redis |
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS 4, shadcn/ui, Zustand 5, TanStack Query 5 |
| Database | Supabase PostgreSQL 15, Alembic migrations |
| Auth | Supabase Auth (Google/Microsoft OAuth), PyJWT + JWKS |
| LLM | Google Gemini (email parsing waterfall + merchant categorization) |
| Infrastructure | Railway (backend + workers), Vercel (frontend), Google Cloud Pub/Sub |

**Scope:** LATAM-first — currently supporting CL, CO, MX, PE, BR, and US. Bank email parsing, currencies, and transaction formats must account for all supported countries. Nothing should be hardcoded for Chile only.

See `ARCHITECTURE.md` for the full data model, API endpoints, and key flows.

---

## Coding Values

1. **User first.** Every coding and product decision must center on the user — making it as simple, clear, and useful as possible. Never degrade the user experience.
2. **Balance complexity and usability.** More is not always better. Keep the user experience as simple as possible.
3. **Be diligent.** Always achieve the best possible outcome given time and resource constraints.
4. **Don't assume — ask.** If an instruction lacks a clear goal or a clear path, ask clarifying questions before starting.
5. **Challenge the status quo.** Always use state-of-the-art tools and techniques. Research what "state of the art" looks like before defaulting to the familiar.
6. **Brevity over cleverness.** Short, clear code. No unnecessary abstractions or bells and whistles.

---

## Ways of Working

### Who we are
Two Wharton MBAs (mechanical engineer + industrial engineer). We can code and review errors quickly, and have strong mathematical backgrounds for verifying logic. Our focus is product and business — not reviewing every line of code.

### Workflow rules
- **Before designing a new feature:** use `/brainstorming` to align on approach first.
- **After every significant code change:** run `requesting-code-review` to verify efficiency and correctness.
- **After every feature implementation:** run a verification pass — test locally or use `/browser-use` for frontend checks. Target: 95%+ of proposed implementation working before marking complete.
- **For final polish:** use iteration loops to catch edge cases and regressions.
- **For all frontend work:** maintain UI/UX consistency across the app. Mobile-first, clean, and coherent with existing design language.

### Documentation — keep these always up to date
- `README.md` — project overview and feature tracking.
- `ARCHITECTURE.md` — tech stack, data model, API endpoints, key flows.
- `NEXT-STEPS.md` — pending features, known issues, future ideas.
- `CLAUDE.md` — update this file whenever a major architectural or product decision is made.

### Project hygiene
- Keep the directory clean. Delete every folder and file that will no longer be used.
- Prefer editing existing files over creating new ones.
- No orphan files, dead code, or half-finished implementations left behind.

---

## Key Architectural Conventions

- **Amount sign convention:** expenses and transfers stored as negative, income as positive — everywhere (email, Plaid, bank connect).
- **Transaction types:** `expense` / `income` / `transfer`. "Transfer" = own-account moves only (CC bill payments, checking→savings). Person-to-person payments (Zelle, etc.) = expense/income.
- **Split types:** `personal` / `shared`. Joint bank accounts auto-classify all transactions as shared.
- **Multi-currency:** transactions carry their own currency. Never hardcode USD or assume a single currency.
- **Email parsing layers:** Template (zero LLM cost) → Gemini waterfall (4 models, confidence-based) → legacy regex fallback.
- **Worker routing:** fast worker (email, cron, ≤60s) vs. slow worker (bank syncs, LLM review, ≤600s).
- **Categories:** fetched dynamically via API. All dropdowns reflect user preferences in real time.
- **Testing:** backend uses pytest with `asyncio_mode = auto`. No DB mocks — tests hit a real database. Frontend has no test infrastructure yet.

---


