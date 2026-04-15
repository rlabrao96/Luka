# Next Steps

_Last updated: 2026-04-14_

## Recently Shipped

- **Budget page redesign (budget-v2)** — 1-week parallel sprint complete. New `/budgets` with Sankey flow diagram (Ingresos → Gastos fijos / Cuotas / Meta de ahorro / Disponible → per-category spend), contribution-mode-aware privacy (full / fija / sólo reembolso), cuotas manual entry, savings target + payday day configuration, per-category budget caps, silent-by-default risk alert band, runway card with days-to-payday, overspent-month `otras_fuentes` visualization. Backend: `GET /budgets/v2/{household_id}`, forecast engine (heuristic v1 with same signatures as future Bayesian engine), `user_budget_settings` + `cuota_purchases` tables, `PATCH /settings/contribution` + `PATCH /settings/budget` + `POST/GET/DELETE /cuotas` endpoints. 48 backend tests, 1 privacy regression, 2 Sankey flow conservation regressions. See `docs/superpowers/specs/2026-04-14-budget-page-redesign-design.md` (spec), `docs/superpowers/plans/2026-04-14-budget-page-redesign-plan.md` (plan), `docs/superpowers/specs/reviews/2026-04-14-day4-integration-report.md` (Task I report), and `docs/superpowers/specs/reviews/2026-04-14-budget-ux-review.md` (Task J report).

## In Progress

- **Template Agent production monitoring** — Template agent deployed (2am daily cron on slow worker). Monitoring first autonomous template generations and shadow validations. First LLM-parsed transactions confirmed live (BofA via gemini-2.5-flash, 0.98 confidence).
- **Plaid production rollout** — Plaid production credentials configured and deployed. BofA connected successfully, 290 transactions synced. Zelle person extraction and CC payment detection working. Pending (processing) transactions now visible in frontend. OAuth redirect URIs configured.
- **Email transaction type + sign fixes** — Email pipeline now correctly infers transaction_type (expense/transfer/income) and stores negative amounts for expenses. Person-to-person payments classified as expense/income, CC payments as transfer. Data migration applied to existing transactions. Monitoring for edge cases.

## Pending

### Budget-v2 follow-ups (post-ship polish — non-blocking)
- **Contribution settings preload** — `ContributionSection` currently seeds `currentMode="full"` + null amounts because `/households/{id}/summary` doesn't yet return `contribution_mode` / `fixed_contribution_amount` / `fixed_contribution_currency`. First-time saves work; existing-state preload shows defaults until the summary endpoint is widened.
- **`MarkAsCuotaDialog` in RecentTransactions non-compact rows** — the trigger is only wired into `TransactionCard` (non-compact outflows). `RecentTransactions.tsx` has a `TODO(chunk-E)` comment at the non-compact row — pick it up when touching that component next.
- **Phase 2 forecast engine** — swap `forecast.py` heuristic internals for a Bayesian engine (same function signatures; contract is stable per spec §6.2). Adds uncertainty bands to the risk alert band and better overshoot probabilities for low-history categories.
- **Redis caching for risk categories** — spec §6.3 mentions `budget:risk:{user_id}:{YYYY-MM}` cache with month-long TTL. Deferred in sprint; `v2_service.py` has a `TODO(Phase 2)` marker at the risk-computation block.
- **Income-aware conversational flow** — see below under Email Pipeline.

### Email Pipeline
- **WhatsApp message templates** — Need to create Meta-approved WhatsApp message templates (`verification_code`, `transaction_alert`) for 24-hour window bypass. Currently limited to 24h response window.
- **Income-aware WhatsApp flow** — LLM + split flow not yet income-aware for inflows. WhatsApp alerts fire for income transactions but the conversational flow assumes expenses.

### Outlook Integration
- **Microsoft Azure / Outlook push notifications** — Azure app registration needed. Requires: `Mail.Read` delegated permission, redirect URI, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `OUTLOOK_CLIENT_STATE`. Code exists (`OutlookProvider`) but credentials not configured.

### Merchant System
- **Merchant training curation** — Use `/train` UI to verify, merge, and fix merchant categories. Initial seed: 161 canonical merchants from 229 raw names. Ongoing quality improvement.

### LATAM Expansion
- **Collect real email samples** — Bank registry has 101 banks seeded but most lack real email samples for template generation. Priority: Chilean banks (Banco Falabella, BCI, Banco Estado, Banco Itau, Scotiabank), then Colombian and Mexican banks.
- **Template Agent tuning** — Adjust `TEMPLATE_AGENT_MIN_EMAILS` (currently 20) and `TEMPLATE_AGENT_RECENCY_DAYS` (14) based on real-world email volume per bank.

### Multi-Card Reconciliation
- **Cross-account transfer matching** — When a user connects a second card (e.g. Amex), existing CC payment transactions should auto-reclassify from "expense" to "transfer" and reconcile against the card-side entries.

## Known Issues

- **WhatsApp Business API approval** — Currently using test/dev mode. For multi-user production use, Meta's official WhatsApp Business API approval process is needed.
- **No frontend test infrastructure** — No Jest, Vitest, or Playwright configured. Backend has 48+ test files (incl. budget-v2 suite) but frontend has zero tests.
- **No CI/CD pipeline** — No GitHub Actions workflows. Backend tests are run manually (`pytest`). Deployment is manual via Railway/Vercel.

## Infrastructure TODOs

- **Luka Connect env vars** — Verify `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL` are set on production Railway.
- **Supabase OAuth providers** — Verify Google OAuth and Microsoft OAuth are enabled in Supabase Auth -> Providers.

## Future Ideas

- Category budget alerts via WhatsApp (notify when spending approaches category limit)
- Template Agent dashboard — admin UI to view template status, accuracy, shadow validation results per bank
- Multi-currency budget support (currently assumes single currency per household)
- Bank registry admin API — CRUD endpoints for managing bank_registry entries
