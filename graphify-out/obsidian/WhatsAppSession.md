---
source_file: "backend/modules/whatsapp/session.py"
type: "code"
community: "Luka Connect & Merchant Review"
location: "L9"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Luka_Connect_&_Merchant_Review
---

# WhatsAppSession

## Connections
- [[ARQ job Phase 1 (LLM group + name) → Phase 2 (categorize) → finalize.]] - `uses` [INFERRED]
- [[Core pipeline job fetch email → parse → lookup merchant → send WhatsApp alert.]] - `uses` [INFERRED]
- [[Create a manual transaction from a parsed expense message and start the session.]] - `uses` [INFERRED]
- [[Daily cron detect inter-account transfers across all households.]] - `uses` [INFERRED]
- [[Daily cron enqueue sync for all active Plaid items.]] - `uses` [INFERRED]
- [[Daily job delete idempotency records older than 7 days.]] - `uses` [INFERRED]
- [[Daily job renew Gmail (7d) and Outlook (~3d) subscriptions.]] - `uses` [INFERRED]
- [[Detect currency override from keywords in the message.      Returns (currency, c]] - `uses` [INFERRED]
- [[Every 6h cron find users due for daily sync, enqueue run_connect_sync for each.]] - `uses` [INFERRED]
- [[Handle a free-text reply during an active edit step, or a new manual expense tri]] - `uses` [INFERRED]
- [[Helper to log failed job to database.]] - `uses` [INFERRED]
- [[Hourly job clear raw_email_text after 24h.]] - `uses` [INFERRED]
- [[Parse a human-entered amount string into the DB storage unit.      USD → stored]] - `uses` [INFERRED]
- [[Parse natural-language expense messages into (amount_int, merchant).      Accept]] - `uses` [INFERRED]
- [[Periodic cron recompute subscription detection for all active users (batched).]] - `uses` [INFERRED]
- [[Purge raw_email_html from parsed_email_log entries older than 7 days.]] - `uses` [INFERRED]
- [[Return (user_id, household_id, preferred_currency) for a verified WhatsApp phone]] - `uses` [INFERRED]
- [[Route a WhatsApp button reply to the correct split action.]] - `uses` [INFERRED]
- [[Route a WhatsApp list selection to category save.]] - `uses` [INFERRED]
- [[Run a Plaid transaction sync for one item.]] - `uses` [INFERRED]
- [[Run a single bank sync decrypt creds, send WhatsApp 2FA nudge, call Luka Connec]] - `uses` [INFERRED]
- [[Send 3 fake WhatsApp expense alerts for buenahorarojas@gmail.com.  Looks up the]] - `uses` [INFERRED]
- [[Test the WhatsApp split+category flow without a real purchase.  Creates a fake p]] - `uses` [INFERRED]
- [[Triggered after new bank account — recompute subscriptions for one user.]] - `uses` [INFERRED]
- [[_handle_manual_expense_trigger()]] - `calls` [INFERRED]
- [[get_session()]] - `calls` [EXTRACTED]
- [[main()_6]] - `calls` [INFERRED]
- [[process_email()]] - `calls` [INFERRED]
- [[send_test_transaction()]] - `calls` [INFERRED]
- [[session.py]] - `contains` [EXTRACTED]
- [[test_save_and_retrieve_session()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Luka_Connect_&_Merchant_Review