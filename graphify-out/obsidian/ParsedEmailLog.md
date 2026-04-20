---
source_file: "backend/modules/email/models.py"
type: "code"
community: "Luka Connect & Merchant Review"
location: "L56"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# ParsedEmailLog

## Connections
- [[ANY amount mismatch in shadow validation triggers retirement.]] - `uses` [INFERRED]
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - `uses` [INFERRED]
- [[Autonomous Template Agent — discovers, generates, validates, promotes, and retir]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `uses` [INFERRED]
- [[Daily cron detect inter-account transfers across all households.]] - `uses` [INFERRED]
- [[Daily cron enqueue sync for all active Plaid items.]] - `uses` [INFERRED]
- [[Daily job delete idempotency records older than 7 days.]] - `uses` [INFERRED]
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - `uses` [INFERRED]
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - `uses` [INFERRED]
- [[Find banks with enough LLM-parsed emails but no active template.]] - `uses` [INFERRED]
- [[Helper to log failed job to database.]] - `uses` [INFERRED]
- [[Hourly job clear raw_email_text after 24h.]] - `uses` [INFERRED]
- [[Main entry point — runs daily as ARQ cron job.]] - `uses` [INFERRED]
- [[Periodic cron recompute subscription detection for all active users (batched).]] - `uses` [INFERRED]
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - `uses` [INFERRED]
- [[Run a Plaid transaction sync for one item.]] - `uses` [INFERRED]
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - `uses` [INFERRED]
- [[Shadow validate active templates compare template vs LLM on a sample.]] - `uses` [INFERRED]
- [[Triggered after new bank account — recompute subscriptions for one user.]] - `uses` [INFERRED]
- [[Use LLM to generate a declarative extraction template from samples.]] - `uses` [INFERRED]
- [[Validate template vs LLM ground truth. 100% amount match, 95% merchant match req]] - `uses` [INFERRED]
- [[models.py_10]] - `contains` [EXTRACTED]
- [[process_email()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review