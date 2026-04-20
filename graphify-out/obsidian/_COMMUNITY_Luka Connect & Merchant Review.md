---
type: community
cohesion: 0.04
members: 148
---

# Luka Connect & Merchant Review

**Cohesion:** 0.04 - loosely connected
**Members:** 148 nodes

## Members
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - rationale - backend/jobs/tasks.py
- [[Approve (and optionally edit) a canonical merchant.]] - rationale - backend/modules/merchant_review/service.py
- [[Approveedit a canonical merchant.]] - rationale - backend/modules/merchant_review/train_router.py
- [[ApproveBody]] - code - backend/modules/merchant_review/train_router.py
- [[BankCredential]] - code - backend/modules/bank_connect/models.py
- [[CLI tool for curating the global canonical merchant database.  Usage     python]] - rationale - backend/scripts/train_merchants.py
- [[Call Luka Connect to start a scrape. Returns sync response.]] - rationale - backend/modules/bank_connect/service.py
- [[CanonicalMerchant]] - code - backend/modules/merchant_review/models.py
- [[ConnectCallback]] - code - backend/modules/bank_connect/router.py
- [[ConnectRequest]] - code - backend/modules/bank_connect/router.py
- [[Convert Transaction + optional Split to response dict.]] - rationale - backend/modules/transactions/service.py
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - rationale - backend/jobs/tasks.py
- [[Create canonical merchants from LLM grouping output. Returns list of createdlin]] - rationale - backend/modules/merchant_review/service.py
- [[Daily cron detect inter-account transfers across all households.]] - rationale - backend/jobs/tasks.py
- [[Daily cron enqueue sync for all active Plaid items.]] - rationale - backend/jobs/tasks.py
- [[Daily job delete idempotency records older than 7 days.]] - rationale - backend/jobs/tasks.py
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - rationale - backend/jobs/tasks.py
- [[Decrypt rut and password from a BankCredential.]] - rationale - backend/modules/bank_connect/service.py
- [[Delete a canonical merchant and unlink its raw names.]] - rationale - backend/modules/merchant_review/train_router.py
- [[Dismiss a review — accept all proposed categories, delete job and notification.]] - rationale - backend/modules/merchant_review/service.py
- [[Encrypt and store bank credentials. Sets initial sync schedule.]] - rationale - backend/modules/bank_connect/service.py
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - rationale - backend/jobs/tasks.py
- [[FailedJob]] - code - backend/modules/transactions/models.py
- [[Find all credentials due for sync (next_sync_at = now).]] - rationale - backend/modules/bank_connect/scheduler.py
- [[Get all canonical merchants for a review job, with aggregated transaction data.]] - rationale - backend/modules/merchant_review/service.py
- [[Get credential record (without decrypting).]] - rationale - backend/modules/bank_connect/service.py
- [[Get existing or create new canonical merchant. Returns dict with id, display_nam]] - rationale - backend/modules/merchant_review/service.py
- [[Global merchant DB stats.]] - rationale - backend/modules/merchant_review/train_router.py
- [[Hard delete a pending email transaction.     Returns 'deleted', 'not_found', or]] - rationale - backend/modules/transactions/service.py
- [[Hard delete credentials for a user+bank.]] - rationale - backend/modules/bank_connect/service.py
- [[Hard delete credentials, auto-created accounts, and their transactions.]] - rationale - backend/modules/bank_connect/router.py
- [[Heavy computation query transactions, detect patterns, store in DB cache.]] - rationale - backend/modules/subscriptions/service.py
- [[Helper to log failed job to database.]] - rationale - backend/jobs/tasks.py
- [[Hourly job clear raw_email_text after 24h.]] - rationale - backend/jobs/tasks.py
- [[Interactive review of unverified canonical merchants.]] - rationale - backend/scripts/train_merchants.py
- [[Link merchant rows to their canonical merchant.]] - rationale - backend/modules/merchant_review/service.py
- [[List all bank connections for a user.]] - rationale - backend/modules/bank_connect/service.py
- [[List all connected banks for the current user.]] - rationale - backend/modules/bank_connect/router.py
- [[List canonical merchants for training. Single query with aggregation.]] - rationale - backend/modules/merchant_review/train_router.py
- [[Local-only admin router for merchant training UI. Served at train — no auth req]] - rationale - backend/modules/merchant_review/train_router.py
- [[Luka merchant training CLI.]] - rationale - backend/scripts/train_merchants.py
- [[Merchant]] - code - backend/modules/merchants/models.py
- [[MerchantReviewJob]] - code - backend/modules/merchant_review/models.py
- [[Merge source canonical merchant into target.]] - rationale - backend/scripts/train_merchants.py
- [[Merge source into target canonical merchant.]] - rationale - backend/modules/merchant_review/train_router.py
- [[MergeBody]] - code - backend/modules/merchant_review/train_router.py
- [[Notification]] - code - backend/modules/notifications/models.py
- [[ParsedEmailLog]] - code - backend/modules/email/models.py
- [[Periodic cron recompute subscription detection for all active users (batched).]] - rationale - backend/jobs/tasks.py
- [[PlaidItem]] - code - backend/modules/plaid/models.py
- [[Poll sync progress (for frontend during initial connection).]] - rationale - backend/modules/bank_connect/router.py
- [[Process movements dedup, reconcile with email txns, create new ones.]] - rationale - backend/modules/bank_connect/router.py
- [[ProcessedWebhook]] - code - backend/modules/transactions/models.py
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - rationale - backend/jobs/tasks.py
- [[RawNameInfo]] - code - backend/modules/merchant_review/train_router.py
- [[Re-run LLM grouping on all unverified merchants.]] - rationale - backend/scripts/train_merchants.py
- [[Receive callback from Luka Connect after a scrape completes.]] - rationale - backend/modules/bank_connect/router.py
- [[Reset credentials stuck in 'in_progress' for over 2 hours.]] - rationale - backend/modules/bank_connect/scheduler.py
- [[Resolve CC movement to card account using cardLabel (precise) or fallback (first]] - rationale - backend/modules/bank_connect/router.py
- [[Resolve bank_account_id for any movement.]] - rationale - backend/modules/bank_connect/router.py
- [[Return pending transactions grouped into 2 buckets     - awaiting_reconciliatio]] - rationale - backend/modules/transactions/service.py
- [[Run a Plaid transaction sync for one item.]] - rationale - backend/jobs/tasks.py
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - rationale - backend/jobs/tasks.py
- [[Scan recent transactions for transfer pairs. Returns number of pairs detected.]] - rationale - backend/modules/reconciliation/transfers.py
- [[Schedule next sync ~24h from now (jittered ±2h to avoid thundering herd).]] - rationale - backend/modules/bank_connect/service.py
- [[Seed canonical merchants from DB or file.]] - rationale - backend/scripts/train_merchants.py
- [[Serve the single-page training UI.]] - rationale - backend/modules/merchant_review/train_router.py
- [[Show global merchant database statistics.]] - rationale - backend/scripts/train_merchants.py
- [[Skip entire review — auto-accept all LLM values.]] - rationale - backend/modules/merchant_review/service.py
- [[Store encrypted credentials and trigger initial full sync (async).     Frontend]] - rationale - backend/modules/bank_connect/router.py
- [[SyncStatusResponse]] - code - backend/modules/bank_connect/router.py
- [[TrainCard]] - code - backend/modules/merchant_review/train_router.py
- [[Transfer detection identifies inter-account transfers and CC payments.  Detecti]] - rationale - backend/modules/reconciliation/transfers.py
- [[Trigger a manual sync (async with webhook callback).]] - rationale - backend/modules/bank_connect/router.py
- [[Triggered after new bank account — recompute subscriptions for one user.]] - rationale - backend/jobs/tasks.py
- [[Two-tier dedup for email transactions     1. Same amount + SAME bank within 5 m]] - rationale - backend/modules/transactions/service.py
- [[Update transaction category. Returns False if transaction not found or not owned]] - rationale - backend/modules/transactions/service.py
- [[Update transaction split type. Returns False if not found or not owned.]] - rationale - backend/modules/transactions/service.py
- [[WhatsAppSession]] - code - backend/modules/whatsapp/session.py
- [[_clear_stuck_jobs()]] - code - backend/modules/bank_connect/scheduler.py
- [[_compute_and_store()]] - code - backend/modules/subscriptions/service.py
- [[_get_db_and_redis()]] - code - backend/scripts/train_merchants.py
- [[_get_or_create_canonical()]] - code - backend/modules/merchant_review/service.py
- [[_interactive_review()]] - code - backend/scripts/train_merchants.py
- [[_link_merchants_to_canonical()]] - code - backend/modules/merchant_review/service.py
- [[_process_movements()]] - code - backend/modules/bank_connect/router.py
- [[_random_next_sync()]] - code - backend/modules/bank_connect/service.py
- [[_resolve_account()]] - code - backend/modules/bank_connect/router.py
- [[_resolve_cc_account()]] - code - backend/modules/bank_connect/router.py
- [[_seed_from_db()]] - code - backend/scripts/train_merchants.py
- [[_seed_from_file()]] - code - backend/scripts/train_merchants.py
- [[approve_merchant()]] - code - backend/modules/merchant_review/service.py
- [[approve_merchant()_1]] - code - backend/modules/merchant_review/train_router.py
- [[cleanup_processed_webhooks()]] - code - backend/jobs/tasks.py
- [[cli()]] - code - backend/scripts/train_merchants.py
- [[connect_bank()]] - code - backend/modules/bank_connect/router.py
- [[create_canonicals_from_groups()]] - code - backend/modules/merchant_review/service.py
- [[create_notification()]] - code - backend/modules/notifications/service.py
- [[decrypt_credentials()]] - code - backend/modules/bank_connect/service.py
- [[delete_credentials()]] - code - backend/modules/bank_connect/service.py
- [[delete_merchant()]] - code - backend/modules/merchant_review/train_router.py
- [[detect_transfers()]] - code - backend/modules/reconciliation/transfers.py
- [[disconnect_bank()]] - code - backend/modules/bank_connect/router.py
- [[dismiss_review()]] - code - backend/modules/merchant_review/service.py
- [[get_connection_status()]] - code - backend/modules/bank_connect/service.py
- [[get_due_syncs()]] - code - backend/modules/bank_connect/scheduler.py
- [[get_review_cards()]] - code - backend/modules/merchant_review/service.py
- [[get_review_status()]] - code - backend/modules/merchant_review/service.py
- [[get_stats()]] - code - backend/modules/merchant_review/train_router.py
- [[get_user_connections()]] - code - backend/modules/bank_connect/service.py
- [[handle_connect_callback()]] - code - backend/modules/bank_connect/router.py
- [[list_connections()]] - code - backend/modules/bank_connect/router.py
- [[list_merchants()]] - code - backend/modules/merchant_review/train_router.py
- [[manual_sync()]] - code - backend/modules/bank_connect/router.py
- [[merge()]] - code - backend/scripts/train_merchants.py
- [[merge_merchant()]] - code - backend/modules/merchant_review/train_router.py
- [[models.py_1]] - code - backend/modules/merchant_review/models.py
- [[models.py_5]] - code - backend/modules/transactions/models.py
- [[models.py_6]] - code - backend/modules/bank_connect/models.py
- [[models.py_8]] - code - backend/modules/plaid/models.py
- [[models.py_9]] - code - backend/modules/notifications/models.py
- [[process_merchant_review()]] - code - backend/jobs/tasks.py
- [[purge_email_logs()]] - code - backend/jobs/tasks.py
- [[purge_raw_emails()]] - code - backend/jobs/tasks.py
- [[refresh_subscriptions_cache()]] - code - backend/jobs/tasks.py
- [[refresh_subscriptions_for_user()]] - code - backend/jobs/tasks.py
- [[regroup()]] - code - backend/scripts/train_merchants.py
- [[review()]] - code - backend/scripts/train_merchants.py
- [[router.py_7]] - code - backend/modules/bank_connect/router.py
- [[run_connect_sync()]] - code - backend/jobs/tasks.py
- [[run_plaid_sync_job()]] - code - backend/jobs/tasks.py
- [[run_reconciliation_job()]] - code - backend/jobs/tasks.py
- [[schedule_connect_syncs()]] - code - backend/jobs/tasks.py
- [[scheduler.py]] - code - backend/modules/bank_connect/scheduler.py
- [[seed()]] - code - backend/scripts/train_merchants.py
- [[send_invite_email()]] - code - backend/jobs/tasks.py
- [[service.py_1]] - code - backend/modules/merchant_review/service.py
- [[service.py_6]] - code - backend/modules/bank_connect/service.py
- [[skip_review()]] - code - backend/modules/merchant_review/service.py
- [[stats()]] - code - backend/scripts/train_merchants.py
- [[store_credentials()]] - code - backend/modules/bank_connect/service.py
- [[sync_status()]] - code - backend/modules/bank_connect/router.py
- [[tasks.py]] - code - backend/jobs/tasks.py
- [[train_merchants.py]] - code - backend/scripts/train_merchants.py
- [[train_router.py]] - code - backend/modules/merchant_review/train_router.py
- [[train_ui()]] - code - backend/modules/merchant_review/train_router.py
- [[transfers.py]] - code - backend/modules/reconciliation/transfers.py
- [[trigger_sync()]] - code - backend/modules/bank_connect/service.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Luka_Connect_&_Merchant_Review
SORT file.name ASC
```

## Connections to other communities
- 178 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 42 edges to [[_COMMUNITY_Plaid & Subscriptions]]
- 30 edges to [[_COMMUNITY_Backend Core & Infra]]
- 15 edges to [[_COMMUNITY_Merchants & WhatsApp]]
- 8 edges to [[_COMMUNITY_Email Parser Pipeline]]
- 7 edges to [[_COMMUNITY_Pydantic Schemas]]
- 6 edges to [[_COMMUNITY_Transactions API]]
- 3 edges to [[_COMMUNITY_LLM Parser & Merchant Grouping]]
- 2 edges to [[_COMMUNITY_Bank Connect Mapper]]
- 1 edge to [[_COMMUNITY_Notifications API]]

## Top bridge nodes
- [[_process_movements()]] - degree 9, connects to 4 communities
- [[WhatsAppSession]] - degree 31, connects to 3 communities
- [[ParsedEmailLog]] - degree 25, connects to 3 communities
- [[PlaidItem]] - degree 22, connects to 3 communities
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - degree 17, connects to 3 communities