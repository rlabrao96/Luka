---
source_file: "backend/modules/bank_connect/models.py"
type: "code"
community: "Luka Connect & Merchant Review"
location: "L9"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# BankCredential

## Connections
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Call Luka Connect to start a scrape. Returns sync response.]] - `uses` [INFERRED]
- [[ConnectCallback]] - `uses` [INFERRED]
- [[ConnectRequest]] - `uses` [INFERRED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `uses` [INFERRED]
- [[Daily cron detect inter-account transfers across all households.]] - `uses` [INFERRED]
- [[Daily cron enqueue sync for all active Plaid items.]] - `uses` [INFERRED]
- [[Daily job delete idempotency records older than 7 days.]] - `uses` [INFERRED]
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - `uses` [INFERRED]
- [[Decrypt rut and password from a BankCredential.]] - `uses` [INFERRED]
- [[Encrypt and store bank credentials. Sets initial sync schedule.]] - `uses` [INFERRED]
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - `uses` [INFERRED]
- [[Find all credentials due for sync (next_sync_at = now).]] - `uses` [INFERRED]
- [[Get credential record (without decrypting).]] - `uses` [INFERRED]
- [[Hard delete credentials for a user+bank.]] - `uses` [INFERRED]
- [[Hard delete credentials, auto-created accounts, and their transactions.]] - `uses` [INFERRED]
- [[Helper to log failed job to database.]] - `uses` [INFERRED]
- [[Hourly job clear raw_email_text after 24h.]] - `uses` [INFERRED]
- [[List all bank connections for a user.]] - `uses` [INFERRED]
- [[List all connected banks for the current user.]] - `uses` [INFERRED]
- [[Periodic cron recompute subscription detection for all active users (batched).]] - `uses` [INFERRED]
- [[Poll sync progress (for frontend during initial connection).]] - `uses` [INFERRED]
- [[Process movements dedup, reconcile with email txns, create new ones.]] - `uses` [INFERRED]
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - `uses` [INFERRED]
- [[Receive callback from Luka Connect after a scrape completes.]] - `uses` [INFERRED]
- [[Reset credentials stuck in 'in_progress' for over 2 hours.]] - `uses` [INFERRED]
- [[Resolve CC movement to card account using cardLabel (precise) or fallback (first]] - `uses` [INFERRED]
- [[Resolve bank_account_id for any movement.]] - `uses` [INFERRED]
- [[Run a Plaid transaction sync for one item.]] - `uses` [INFERRED]
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - `uses` [INFERRED]
- [[Schedule next sync ~24h from now (jittered ±2h to avoid thundering herd).]] - `uses` [INFERRED]
- [[Store encrypted credentials and trigger initial full sync (async).     Frontend]] - `uses` [INFERRED]
- [[SyncStatusResponse]] - `uses` [INFERRED]
- [[Trigger a manual sync (async with webhook callback).]] - `uses` [INFERRED]
- [[Triggered after new bank account — recompute subscriptions for one user.]] - `uses` [INFERRED]
- [[models.py_6]] - `contains` [EXTRACTED]
- [[store_credentials()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review