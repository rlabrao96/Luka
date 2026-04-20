---
source_file: "backend/modules/merchant_review/models.py"
type: "code"
community: "Luka Connect & Merchant Review"
location: "L26"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# MerchantReviewJob

## Connections
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - `uses` [INFERRED]
- [[Approve (and optionally edit) a canonical merchant.]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[ConnectCallback]] - `uses` [INFERRED]
- [[ConnectRequest]] - `uses` [INFERRED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `uses` [INFERRED]
- [[Create canonical merchants from LLM grouping output. Returns list of createdlin]] - `uses` [INFERRED]
- [[Daily cron detect inter-account transfers across all households.]] - `uses` [INFERRED]
- [[Daily cron enqueue sync for all active Plaid items.]] - `uses` [INFERRED]
- [[Daily job delete idempotency records older than 7 days.]] - `uses` [INFERRED]
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - `uses` [INFERRED]
- [[Dismiss a review — accept all proposed categories, delete job and notification.]] - `uses` [INFERRED]
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - `uses` [INFERRED]
- [[Get all canonical merchants for a review job, with aggregated transaction data.]] - `uses` [INFERRED]
- [[Get existing or create new canonical merchant. Returns dict with id, display_nam]] - `uses` [INFERRED]
- [[Hard delete credentials, auto-created accounts, and their transactions.]] - `uses` [INFERRED]
- [[Helper to log failed job to database.]] - `uses` [INFERRED]
- [[Hourly job clear raw_email_text after 24h.]] - `uses` [INFERRED]
- [[Link merchant rows to their canonical merchant.]] - `uses` [INFERRED]
- [[List all connected banks for the current user.]] - `uses` [INFERRED]
- [[Periodic cron recompute subscription detection for all active users (batched).]] - `uses` [INFERRED]
- [[Poll sync progress (for frontend during initial connection).]] - `uses` [INFERRED]
- [[Process movements dedup, reconcile with email txns, create new ones.]] - `uses` [INFERRED]
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - `uses` [INFERRED]
- [[Receive callback from Luka Connect after a scrape completes.]] - `uses` [INFERRED]
- [[Resolve CC movement to card account using cardLabel (precise) or fallback (first]] - `uses` [INFERRED]
- [[Resolve bank_account_id for any movement.]] - `uses` [INFERRED]
- [[Run a Plaid transaction sync for one item.]] - `uses` [INFERRED]
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - `uses` [INFERRED]
- [[Skip entire review — auto-accept all LLM values.]] - `uses` [INFERRED]
- [[Store encrypted credentials and trigger initial full sync (async).     Frontend]] - `uses` [INFERRED]
- [[SyncStatusResponse]] - `uses` [INFERRED]
- [[Trigger a manual sync (async with webhook callback).]] - `uses` [INFERRED]
- [[Triggered after new bank account — recompute subscriptions for one user.]] - `uses` [INFERRED]
- [[handle_connect_callback()]] - `calls` [INFERRED]
- [[models.py_1]] - `contains` [EXTRACTED]
- [[run_plaid_sync_job()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review