# Next Steps

_Last updated: 2026-04-05_

## In Progress

- **Worker queue scaling** — fast/slow split deployed and verified. Monitoring for production stability with multiple concurrent users.

## Pending

### Email Pipeline
- **Multi-bank email parser support** — Currently only Banco de Chile email formats are fully parsed. Banks still needing email samples: Banco Falabella, BCI, Banco Estado, Banco Itau, Scotiabank. Reference templates in `docs/email-templates/chile/<bank-name>/`.
- **WhatsApp message templates** — Need to create Meta-approved WhatsApp message templates (`verification_code`, `transaction_alert`) for 24-hour window bypass. Currently limited to 24h response window.

### Outlook Integration
- **Microsoft Azure / Outlook push notifications** — Azure app registration needed. Requires: `Mail.Read` delegated permission, redirect URI, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `OUTLOOK_CLIENT_STATE`. Code exists (`OutlookProvider`) but credentials not configured.

### Merchant System
- **Merchant training curation** — Use `/train` UI to verify, merge, and fix merchant categories. Initial seed: 161 canonical merchants from 229 raw names. Ongoing quality improvement.

## Known Issues

- **`.env.example` has stale `FINTOC_API_KEY`** — Fintoc was removed; this env var should be removed from `.env.example`.
- **`OPENAI_API_KEY` in `.env.example`** — OpenAI was replaced by Gemini for merchant categorization. The key is optional (fallback only) but `.env.example` doesn't reflect this.
- **WhatsApp Business API approval** — Currently using test/dev mode. For multi-user production use, Meta's official WhatsApp Business API approval process is needed.

## Infrastructure TODOs

- **`GEMINI_API_KEY` on Railway** — May need verification that this is set in production env vars.
- **Luka Connect env vars** — Verify `LUKA_CONNECT_URL`, `LUKA_CONNECT_API_KEY`, `CONNECT_ENCRYPTION_KEY`, `BACKEND_PUBLIC_URL` are set on production Railway.
- **Supabase OAuth providers** — Verify Google OAuth and Microsoft OAuth are enabled in Supabase Auth → Providers.

## Future Ideas

- Category budget alerts via WhatsApp (notify when spending approaches category limit)
- Income-aware WhatsApp flow (LLM + split flow not yet income-aware for inflows)
- Plaid production credentials (currently sandbox; upgrade when ready for real US users)
