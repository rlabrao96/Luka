---
source_file: "backend/modules/merchant_review/models.py"
type: "code"
community: "Luka Connect & Merchant Review"
location: "L11"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# CanonicalMerchant

## Connections
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - `uses` [INFERRED]
- [[Approve (and optionally edit) a canonical merchant.]] - `uses` [INFERRED]
- [[Approveedit a canonical merchant.]] - `uses` [INFERRED]
- [[ApproveBody]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[CLI tool for curating the global canonical merchant database.  Usage     python]] - `uses` [INFERRED]
- [[Convert Transaction + optional Split to response dict.]] - `uses` [INFERRED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `uses` [INFERRED]
- [[Create canonical merchants from LLM grouping output. Returns list of createdlin]] - `uses` [INFERRED]
- [[Daily cron detect inter-account transfers across all households.]] - `uses` [INFERRED]
- [[Daily cron enqueue sync for all active Plaid items.]] - `uses` [INFERRED]
- [[Daily job delete idempotency records older than 7 days.]] - `uses` [INFERRED]
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - `uses` [INFERRED]
- [[Delete a canonical merchant and unlink its raw names.]] - `uses` [INFERRED]
- [[Dismiss a review — accept all proposed categories, delete job and notification.]] - `uses` [INFERRED]
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - `uses` [INFERRED]
- [[Get all canonical merchants for a review job, with aggregated transaction data.]] - `uses` [INFERRED]
- [[Get existing or create new canonical merchant. Returns dict with id, display_nam]] - `uses` [INFERRED]
- [[Global merchant DB stats.]] - `uses` [INFERRED]
- [[Hard delete a pending email transaction.     Returns 'deleted', 'not_found', or]] - `uses` [INFERRED]
- [[Helper to log failed job to database.]] - `uses` [INFERRED]
- [[Hourly job clear raw_email_text after 24h.]] - `uses` [INFERRED]
- [[Interactive review of unverified canonical merchants.]] - `uses` [INFERRED]
- [[Link merchant rows to their canonical merchant.]] - `uses` [INFERRED]
- [[List canonical merchants for training. Single query with aggregation.]] - `uses` [INFERRED]
- [[Local-only admin router for merchant training UI. Served at train — no auth req]] - `uses` [INFERRED]
- [[Luka merchant training CLI.]] - `uses` [INFERRED]
- [[Merge source canonical merchant into target.]] - `uses` [INFERRED]
- [[Merge source into target canonical merchant.]] - `uses` [INFERRED]
- [[MergeBody]] - `uses` [INFERRED]
- [[Periodic cron recompute subscription detection for all active users (batched).]] - `uses` [INFERRED]
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - `uses` [INFERRED]
- [[RawNameInfo]] - `uses` [INFERRED]
- [[Re-run LLM grouping on all unverified merchants.]] - `uses` [INFERRED]
- [[Return pending transactions grouped into 2 buckets     - awaiting_reconciliatio]] - `uses` [INFERRED]
- [[Run a Plaid transaction sync for one item.]] - `uses` [INFERRED]
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - `uses` [INFERRED]
- [[Seed canonical merchants from DB or file.]] - `uses` [INFERRED]
- [[Serve the single-page training UI.]] - `uses` [INFERRED]
- [[Show global merchant database statistics.]] - `uses` [INFERRED]
- [[Skip entire review — auto-accept all LLM values.]] - `uses` [INFERRED]
- [[TrainCard]] - `uses` [INFERRED]
- [[Triggered after new bank account — recompute subscriptions for one user.]] - `uses` [INFERRED]
- [[Two-tier dedup for email transactions     1. Same amount + SAME bank within 5 m]] - `uses` [INFERRED]
- [[Update transaction category. Returns False if transaction not found or not owned]] - `uses` [INFERRED]
- [[Update transaction split type. Returns False if not found or not owned.]] - `uses` [INFERRED]
- [[_get_or_create_canonical()]] - `calls` [INFERRED]
- [[_seed_from_file()]] - `calls` [INFERRED]
- [[models.py_1]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review