# Next Steps

_Last updated: 2026-04-06_

## In Progress

- **Template Agent production monitoring** — Template agent deployed (2am daily cron on slow worker). Monitoring first autonomous template generations and shadow validations. First LLM-parsed transactions confirmed live (BofA via gemini-2.5-flash, 0.98 confidence).

## Pending

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

## Known Issues

- **WhatsApp Business API approval** — Currently using test/dev mode. For multi-user production use, Meta's official WhatsApp Business API approval process is needed.
- **No frontend test infrastructure** — No Jest, Vitest, or Playwright configured. Backend has 46 test files but frontend has zero tests.
- **No CI/CD pipeline** — No GitHub Actions workflows. Backend tests are run manually (`pytest`). Deployment is manual via Railway/Vercel.

## Infrastructure TODOs

- **Luka Connect env vars** — Verify `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL` are set on production Railway.
- **Supabase OAuth providers** — Verify Google OAuth and Microsoft OAuth are enabled in Supabase Auth -> Providers.

## Future Ideas

- Category budget alerts via WhatsApp (notify when spending approaches category limit)
- Plaid production credentials (currently sandbox; upgrade when ready for real US users)
- Template Agent dashboard — admin UI to view template status, accuracy, shadow validation results per bank
- Multi-currency budget support (currently assumes single currency per household)
- Bank registry admin API — CRUD endpoints for managing bank_registry entries
