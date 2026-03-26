# Fintoc Limitations & Constraints for Luka

> Real limitations discovered from Fintoc's documentation.
> Source: [Fintoc Docs](https://docs.fintoc.com/docs/welcome) — scraped 2026-03-25.

---

## 1. Credit Card Transactions

### Can I get credit card transactions for personal accounts in Banco de Chile?

**NO.** This is one of the most significant limitations.

Looking at the Products & Institutions table for the Movements product:

| Bank | Individual Account Types |
|------|------------------------|
| Banco de Chile | Checking Accounts, Sight Accounts **only** |
| Banco Santander | Checking Accounts, Sight Accounts **only** |
| Banco Itau | Checking Accounts, Sight Accounts **only** |
| Banco BICE | Checking Accounts, Sight Accounts **only** |
| Banco Scotiabank | Checking Accounts, Sight Accounts **only** |
| Banco BCI | Checking Accounts, Sight Accounts **only** |
| Banco Estado | Checking Accounts, Sight Accounts **only** |

**No Chilean bank supports credit card movements for individual (personal) accounts through Fintoc.**

The only bank that lists credit card support is **Banco Santander for business accounts**. Even then, this is business-only.

### Impact on Luka
- Card purchases that debit directly from checking/sight accounts (debit card payments) **do appear** as movements in those accounts
- Credit card purchases that accumulate into a monthly statement **do NOT appear** until they are paid (when the credit card payment shows as a debit movement in the checking account)
- Users won't see individual credit card transactions — only the lump sum payment to the credit card
- This is a fundamental gap for expense tracking: if a user primarily uses a credit card, Luka via Fintoc will only see the monthly credit card bill, not individual purchases

---

## 2. No Savings Account Movements Listed

While the Account Object defines `savings_account` as a valid type, the Products & Institutions table only lists **Checking Accounts** and **Sight Accounts** as supported products for movements. Savings accounts may show up as account objects with balances but may not have full movement history available.

---

## 3. Transaction History Limits

History is **not unlimited**. It varies by bank and account type:

| Bank | Individual History | Business History |
|------|-------------------|-----------------|
| Banco de Chile | 24 months | 24 months |
| Banco Santander | 24 months | 24 months |
| Banco Itau | 24 months | 12 months |
| Banco BICE | 12 months | 12 months |
| Banco Scotiabank | 12 months | 12 months |
| Banco BCI | 12 months | 6 months (Empresarios) / 3 months (360) |
| Banco Estado | 12 months | 12 months |
| Banco Security | N/A | 12 months |

**Implication:** When a user first connects, you get up to this historical window. After that, Fintoc fetches new movements incrementally. If you miss movements and they fall outside the window, they're gone.

---

## 4. Data Freshness — NOT Real-Time

- Movements are **not** real-time. Fintoc periodically syncs with the bank.
- The sync frequency depends on your **pricing plan** (not publicly documented).
- On-demand refresh via Refresh Intents takes **1-3 minutes** to complete.
- 5-minute cooldown between successful refresh intents.
- Only one refresh intent can be in progress per link at a time.

**Impact on Luka:** If using email push notifications for real-time alerts AND Fintoc for transaction data, there will be a time gap between when the email arrives and when the transaction appears in Fintoc. The email-based pipeline will always be faster.

---

## 5. Credential Management Issues

### Bank Password Changes
- When a user changes their bank password, the link enters `login_required` status
- Fintoc sends a `link.credentials_changed` webhook event
- The user must **re-connect** through the widget with new credentials
- Until reconnected, no movements are fetched

### MFA Requirements
- Some banks require multi-factor authentication (SMS, email, device, coordinate card, captcha)
- For automatic refreshes: if MFA is required, the refresh will fail
- For on-demand refreshes: if MFA is required, you must open the widget so the user can enter their 2FA
- This means **fully automated background refreshes may break** if the bank suddenly starts requiring MFA

### Credential Lock Risk
- If a refresh intent is rejected (credentials invalid) and you retry too aggressively, the **bank may lock the user's account**
- Must implement backoff/wait logic for rejected refresh intents

---

## 6. Banco Security — No Individual Accounts

Banco Security **only supports business accounts**. If a user has a personal account at Banco Security, they **cannot** connect it through Fintoc.

---

## 7. Foreign Currency Accounts Refresh Slowly

From the docs:
> "Foreign currency accounts refresh once a day"

If you need USD-denominated accounts to refresh more frequently, you must contact Fintoc support. This is a per-account configuration, not an API setting.

---

## 8. Transfer Metadata Can Be Unreliable

From the docs:
> "Transfer data can sometimes be null or wrong. This can be due to the movement not being a transfer or because of matching problems with the banks statements."

Specifically:
- `sender_account` and `recipient_account` can be null even for transfers
- `institution` within those objects can be null
- Transfer data **can change up to 5 days** after the movement was created
- `reference_id` can be null

**Impact:** Don't rely solely on sender/recipient data for categorization. The `description` field is more reliable for identifying merchants/counterparties.

---

## 9. Post Date vs Transaction Date Mismatch

- `post_date` = accounting date (what the bank uses internally)
- `transaction_date` = actual transaction time
- Banks may backdate or future-date: a Saturday transaction gets a Monday `post_date`
- `transaction_date` can be `null` for non-transfer movements
- The `since`/`until` filters on the List Movements endpoint use `post_date`, not `transaction_date`

**Impact:** When displaying transactions to users, use `transaction_date` when available, fall back to `post_date`. But for fetching incremental updates, filter on `post_date`.

---

## 10. Movement Status Transitions

- Movements start as `confirmed` but can later become `reversed` or `duplicated`
- `processing` status typically resolves within 12 hours
- By default, List Movements only returns `confirmed` movements (`confirmed_only=true`)
- You must explicitly set `confirmed_only=false` to see reversed/duplicated/processing

**Impact:** A movement you imported as confirmed could later be reversed by the bank. You need to either:
1. Periodically re-fetch and check for status changes, or
2. Enable `movements_removed` and `movements_modified` webhook events in the Fintoc dashboard

---

## 11. Pending Checks

- Checks take up to 48 business hours to be confirmed
- Pending checks can be reversed (insufficient funds, etc.)
- Marked with `pending: true`

---

## 12. link.created Event Delivery

The `link.created` event **cannot** be received via registered Webhook Endpoints. It is **only** delivered to the `webhookUrl` parameter passed in the widget configuration.

This means your webhook endpoint registration for other events (refresh_intent, credentials_changed) is separate from the link creation flow.

---

## 13. Widget Callback Limitations

- `onSuccess` callback takes **no parameters** (or a linkIntent object with exchangeToken in the new flow)
- There is **NO** `onError` callback — only `onExit` and `onEvent`
- Frontend events should **never** be used to determine resource creation status — only webhooks are authoritative
- The widget is an iframe — limited customization, some mobile browsers may have issues

---

## 14. Pagination Default

Default page size is **30 movements**. If you don't adjust `per_page`, you'll miss movements for active accounts. Always use `per_page=300` (max) and iterate through pages.

---

## 15. API Rate Limits

Rate limits exist but are not publicly documented with specific numbers. The docs mention "API rate limits" as a topic but the actual limits depend on your plan. The known limit is:
- Refresh Intents: 5-minute cooldown between successful requests per link

---

## 16. Pricing / Fees (Movements Product)

Fintoc does **not** publicly list pricing for the Movements product. The fees page only documents Payment Initiation fees (percentage-based). Movements pricing is custom/plan-based — requires contacting sales.

The refresh frequency and features available depend on your plan tier.

---

## 17. Banks NOT Supported

Notable Chilean banks/institutions NOT in the supported list:
- **Banco Falabella** (CMR Falabella credit cards)
- **Banco Ripley**
- **Banco Consorcio**
- **Coopeuch**
- **MACH** (BCI digital wallet — separate from BCI banking)
- **Tenpo**
- **Mercado Pago**
- Any **fintech** or **prepaid card** provider

---

## Summary: What This Means for Luka

| Feature | Available? | Notes |
|---------|-----------|-------|
| Checking account movements | Yes | All 8 banks for individuals |
| Sight account (Cuenta Vista/RUT) movements | Yes | All 8 banks |
| Credit card transactions (individual) | **NO** | Not available for ANY bank |
| Credit card transactions (business) | Partial | Santander business only |
| Savings account movements | Unclear | Listed as type but not in supported products |
| Real-time transactions | **NO** | Minutes to hours delay |
| Historical data | 3-24 months | Varies by bank |
| Automatic background sync | Yes | But breaks on MFA/password changes |
| Line of credit movements | Unclear | LOC shows as account type with balance |

### Recommended Luka Strategy

1. **Keep the email pipeline as primary** for real-time transaction capture
2. **Use Fintoc as a secondary source** for:
   - Historical backfill when user first connects
   - Catching transactions that email notifications might miss
   - Balance verification
   - Reconciliation
3. **Clearly communicate to users** that credit card transactions are not available through bank connection — they rely on email notifications for those
4. **Implement `confirmed_only=false`** and handle reversed/duplicated movements
5. **Handle MFA gracefully** — prompt users to re-authenticate when needed
