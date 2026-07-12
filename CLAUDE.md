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
- **Amount unit convention:** `transactions.amount`, `category_budgets.amount`, and `household_budgets.budgeted` are **integer minor units** (cents for 2-decimal currencies; whole units for CLP/COP). All scaling goes through `modules/currencies/units.py` (`to_minor_units` / `to_major_units` / `major_unit_quantum`) — never hand-roll a ×100/÷100. The frontend converts at input/display boundaries via `storedToMajor`/`majorToStored` in `app/lib/currency.ts`.
- **Counts-toward-totals rule:** every money aggregate (dashboard, budgets, household contributions/settlement) uses ONE exclusion predicate — `modules/transactions/totals.py`: exclude orphans, `transaction_type='transfer'` rows, refund pairs, reimbursement groups. A `transfer_pair_id` alone is NOT an exclusion signal (the wallet leg of a Venmo/PayPal funding pair carries the pair id but is the canonical expense and must count). The frontend dashboard mirrors this rule.
- **Transaction types:** `expense` / `income` / `transfer`. "Transfer" = own-account moves only (CC bill payments, checking→savings). Person-to-person payments (Zelle, etc.) = expense/income.
- **Split types:** `personal` / `shared`. Joint bank accounts auto-classify all transactions as shared.
- **Multi-currency:** transactions carry their own currency. Never hardcode USD or assume a single currency.
- **Email parsing layers:** Template (zero LLM cost) → Gemini waterfall (4 models, confidence-based) → legacy regex fallback.
- **Worker routing:** fast worker (email, cron, ≤60s) vs. slow worker (bank syncs, LLM review, ≤600s).
- **Categories:** fetched dynamically via API. All dropdowns reflect user preferences in real time.
- **Testing:** backend uses pytest with `asyncio_mode = auto`. No DB mocks — tests hit a real database. Frontend has no test infrastructure yet.
- **Settlement ratio ordering:** `households.split_ratio[i]` maps positionally to active members ordered by `joined_at ASC` — the single canonical ordering shared by `calculate_settlement` and budgets v2 `_caller_ratio_share`. Never re-sort before indexing the ratio.
- **Trips visibility:** the entire Trips (Viajes) feature is gated by `users.feature_trips_enabled` (default false). Backend 403s with `feature_disabled` on every `/trips/*` route; frontend nav-filters the entry.
- **Trip ledger sign convention:** `trip_expenses.amount`, `trip_expense_splits.share_amount`, and `trip_settlements.amount` are all stored as **positive numerics**. Direction is conveyed structurally via `payer_attendee_id` / `from_attendee_id` + `to_attendee_id`. Luka's negative-expense convention applies only to the `transactions` table — when linking a Luka transaction into a trip expense, `amount = abs(transaction.amount)`.
- **Trip-only stubs** (`trip_expenses` rows with `transaction_id IS NULL`) never appear in any user's personal ledger, budget, or category totals. They live entirely inside the trip ledger.
- **Trip ↔ household split mutual exclusivity:** a transaction with a `trip_expenses` link cannot have `transaction_splits` rows of `split_type='shared'`, and vice versa; enforced via two BEFORE triggers (migration 048, narrowed to `shared`-only in 049). Personal split rows are tags, not divisions, and coexist freely with trip links — every Luka transaction has a personal split row by default. Joint-account (shared) transactions return HTTP 409 `joint_account_dual_split_not_supported` when tagged to a trip in v1. Dual-split is a v2 feature.
- **Trip FX rates** are frozen at expense-creation time and never re-fetched (except during a base-currency change re-anchor — itself a v2 feature). v1 enforces `expense.currency == trip.base_currency` at write (422 otherwise) so FX fields stay NULL.

---

## Codebase Knowledge Graph (RAG)

A pre-built knowledge graph of this repo lives in `graphify-out/`. **Use it as the first lookup when answering codebase questions — it's ~50× cheaper than reading files.**

- `graphify-out/graph.json` — 2,536 nodes, 5,161 edges, 209 clustered communities covering backend modules, frontend pages, specs, plans, email templates, and design mockups. Every edge is tagged `EXTRACTED` / `INFERRED` / `AMBIGUOUS` with a confidence score.
- `graphify-out/GRAPH_REPORT.md` — god nodes (top abstractions: `Transaction`, `User`, `HouseholdMember`, `Household`, `BankAccount`), surprising cross-document connections, and suggested questions.
- `graphify-out/graph.html` — interactive visualization, open in a browser.

### How to query
- **Open-ended question:** `/graphify query "<question>"` (BFS traversal, broad context) or `--dfs` for tracing a specific chain.
- **Connection between two concepts:** `/graphify path "NodeA" "NodeB"` — shortest path with edge relations.
- **Explain one node:** `/graphify explain "NodeName"` — plain-language summary of everything it connects to.
- **Direct read:** load `graphify-out/graph.json` with `networkx.readwrite.json_graph.node_link_graph(data, edges='links')` and traverse.

### When the graph is stale
After code changes, run `/graphify --update` (incremental — only re-extracts changed files). Code-only changes skip the LLM entirely (AST-only rebuild). The `graphify claude install` command wires this into sessions automatically.

**Rule:** before grepping/globbing for a concept, ask the graph. Only fall back to file search when the graph lacks the answer or is out of date.

---


