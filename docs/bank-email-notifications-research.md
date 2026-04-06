# Bank Email Notification Research

> Research date: 2026-04-06
> Purpose: Document email notification formats for the top 5 banks in 6 countries to support Luka's multi-country email parsing pipeline.

## Methodology

Data gathered via web searches of official bank documentation, security pages, community forums, CSIRT alerts, and fintech aggregator projects. Confidence levels are marked per bank:
- **VERIFIED** = sender address confirmed from official bank source or existing project templates
- **HIGH** = sender address found in multiple credible sources
- **MEDIUM** = sender domain known, specific address inferred from patterns
- **LOW** = only domain known; specific sender address unconfirmed

---

## Chile (CL)

### 1. Banco de Chile (bancochile.cl)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED (from project email templates) |
| **Sender emails** | `enviodigital@bancochile.cl` (purchase alerts), `serviciodetransferencias@bancochile.cl` (transfer confirmations) |
| **Sender domain(s)** | `bancochile.cl` |
| **Known subjects** | "Transferencia a Terceros", inline notification (no subject for purchase alerts — delivered as push+email combo) |
| **Notification types** | Credit card purchase, debit card purchase, outgoing transfer to third parties, credit card payment confirmation |
| **Email format** | HTML (transfers use `<table>` layout with origin/destination sections), plain text (purchase alerts — single paragraph with amount, card, merchant, date) |
| **Amount format** | CLP: `$1.450` / `$40.000` (dot = thousands separator, no decimals) |
| **Date format** | `DD/MM/YYYY HH:MM` (e.g., `11/03/2026 15:09`) or prose `viernes 14 de noviembre de 2025 16:30` |
| **Key fields** | Card last 4 digits, merchant name + city, amount, date/time, transaction ID (transfers) |
| **Sample body (purchase)** | `Te informamos que se ha realizado una compra por $1.450 con Tarjeta de Credito ****5032 en PARKING COSTANERA SANTIAGO CL el 11/03/2026 15:09.` |
| **Sample body (transfer)** | HTML table with sections: Origen (account type, number), Destino (name, RUT, bank, account), Monto, Fecha y Hora, Transaccion ID |

### 2. BancoEstado (bancoestado.cl)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | `notificaciones@bancoestado.cl` (likely), `contactocentrodeayuda@bancoestado.cl` (support) |
| **Sender domain(s)** | `bancoestado.cl` |
| **Known subjects** | Unknown — BancoEstado primarily uses push notifications via app since 2017 |
| **Notification types** | Purchase alerts (Cuenta RUT, credit/debit), transfers, withdrawals, deposits |
| **Email format** | HTML (likely similar table format to other Chilean banks) |
| **Amount format** | CLP standard: `$XX.XXX` |
| **Notes** | BancoEstado was one of the last major Chilean banks to add smart notifications (2017). They emphasize they NEVER send links in emails. Primary notification channel is push via app, with email as secondary. |

### 3. Santander Chile (santander.cl)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED (from project email templates) |
| **Sender emails** | Sender domain `santander.cl` (specific address not captured in templates but emails originate from this domain) |
| **Sender domain(s)** | `santander.cl` |
| **Known subjects** | "Comprobante Transferencia de fondos" |
| **Notification types** | Outgoing transfers, credit/debit card purchases (via push + email), ATM withdrawals |
| **Email format** | HTML rendered to structured text. Transfer emails use labeled fields: `Monto transferido`, `Datos de origen`, `Datos de destino` with Name, RUT, Bank, Account type/number, Email |
| **Amount format** | CLP: `$ 8.226` (space after $, dot = thousands) |
| **Date format** | `DD/MM/YYYY` (e.g., `03/03/2026`) |
| **Key fields** | Recipient name, RUT, destination bank, account type/number, amount, date, comment field |
| **Notes** | Push notifications launched as app feature. Email confirmations sent for transfers specifically. |

### 4. BCI (bci.cl)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | `notificaciones@bci.cl` (confirmed from web search referencing this address) |
| **Sender domain(s)** | `bci.cl`, `bcidigital.cl` (for MACH/digital products) |
| **Known subjects** | Unknown specific subjects — notifications configurable for credit and debit cards |
| **Notification types** | Credit card purchase, debit card purchase, suspicious activity alerts, transfer confirmations |
| **Email format** | HTML (likely) |
| **Amount format** | CLP standard |
| **Notes** | BCI allows customers to configure notifications via push, SMS, and/or email. Available through Bci.cl sidebar > "Notificaciones". Can be set for all transactions or above a threshold amount. |

### 5. Banco Falabella (bancofalabella.cl)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Likely `notificaciones@bancofalabella.cl` or `alertas@bancofalabella.cl` (pattern from Colombia subsidiary uses `NotificacionesEmbargos@bancofalabella.com.co`) |
| **Sender domain(s)** | `bancofalabella.cl` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Real-time purchase alerts (configurable for all or threshold), credit card transactions |
| **Email format** | HTML (likely) |
| **Amount format** | CLP standard |
| **Notes** | Banco Falabella offers real-time notifications via app and web. Also associated with CMR Falabella credit card notifications. CSIRT Chile has flagged multiple phishing campaigns impersonating this bank. |

---

## Colombia (CO)

### 1. Bancolombia (bancolombia.com / bancolombia.com.co)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | `alertasynotificaciones@notificacionesbancolombia.com` (transaction alerts), `validaciondeseguridad@notificacionesbancolombia.com` (security validations) |
| **Sender domain(s)** | `notificacionesbancolombia.com` (NOT bancolombia.com — they use a separate notifications subdomain), `bancolombia.com.co` (corporate) |
| **Known subjects** | "Compra por [amount]" (purchase), "Transferencia" (transfer), security validation subjects |
| **Notification types** | Purchase alerts, transfer confirmations, ATM withdrawals, security validations, product changes |
| **Email format** | HTML with Bancolombia branding |
| **Amount format** | COP: `$XXX.XXX` (dot = thousands, typical Colombian format) |
| **Notes** | Important: sender domain is `notificacionesbancolombia.com`, NOT `bancolombia.com`. SMS alerts come from number 891 333. Report suspicious emails to `correosospechoso@bancolombia.com.co`. |

### 2. Davivienda (davivienda.com)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Likely `alertas@davivienda.com` or `notificaciones@davivienda.com` |
| **Sender domain(s)** | `davivienda.com` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Credit card purchases (>= $600,000 COP at certain times), unusual ATM/POS transactions at atypical hours/frequencies/amounts/locations, product information |
| **Email format** | HTML (likely) |
| **Amount format** | COP standard |
| **Notes** | Davivienda offers free alerts and notifications via email or mobile phone. Also operates DaviBank (international) and has push notification service via App Davivienda. |

### 3. Banco de Bogota (bancodebogota.com.co)

| Field | Value |
|---|---|
| **Confidence** | LOW |
| **Sender emails** | Unknown — bank states they communicate via email only for "educational multimedia content, demos, videos and infographics" |
| **Sender domain(s)** | `bancodebogota.com.co` |
| **Known subjects** | Unknown |
| **Notification types** | Primarily push/SMS-based. Email used for educational content rather than transaction alerts. |
| **Email format** | Unknown |
| **Notes** | Banco de Bogota appears to rely more on SMS and push notifications rather than email for transaction alerts. Support email: `solicitudesbancapersonas@bancodebogota.com.co`. They have WhatsApp-based fraud reporting. |

### 4. BBVA Colombia (bbva.com.co)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Likely from `bbva.com.co` domain or shared BBVA notification infrastructure |
| **Sender domain(s)** | `bbva.com.co`, `bbva.com` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Real-time card purchase notifications (amount, date, establishment), security alerts for unusual movements, account balance notifications |
| **Email format** | HTML with BBVA branding |
| **Amount format** | COP standard |
| **Notes** | BBVA globally offers real-time purchase notifications for Visa credit and debit cards including amount, date, and establishment. Email + mobile notification sent automatically for security alerts. |

### 5. Nequi (nequi.com.co)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `@nequi.com.co` domain. Support: `ayuda@nequi.com.co`. Report suspicious: `correosospechoso@nequi.com` |
| **Sender domain(s)** | `nequi.com.co` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Transfer confirmations, purchase alerts, account updates, regulatory acceptance confirmations |
| **Email format** | HTML (likely, modern fintech styling) |
| **Amount format** | COP standard |
| **Notes** | Nequi is a mobile-first fintech (Bancolombia subsidiary). Primary notification channel is push via app. Nequi explicitly states "notifications never arrive via SMS or email" for transaction alerts — they are app-only. Email is used for account communications, not real-time transaction alerts. This makes Nequi LOW PRIORITY for email parsing. |

---

## Mexico (MX)

### 1. BBVA Mexico (bbva.mx)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `bbva.mx` domain. Marketing emails from `cloud.email.bbva.mx` |
| **Sender domain(s)** | `bbva.mx`, `email.bbva.mx` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchases/charges/withdrawals (any amount — basic free service), account balance info, card transaction alerts |
| **Email format** | HTML with BBVA branding |
| **Amount format** | MXN: `$XX,XXX.XX` (comma = thousands, dot = decimal) |
| **Notes** | BBVA Mexico's basic notification service (free) covers purchases, charges, and withdrawals of any amount, plus account info. CONDUSEF has warned about phishing campaigns targeting BBVA users. |

### 2. Banorte (banorte.com)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Likely from `banorte.com` domain. Abuse reports to `abuso@banorte.com` |
| **Sender domain(s)** | `banorte.com` |
| **Known subjects** | "Banorte Avisa" notification subjects (specific formats unknown) |
| **Notification types** | Card purchases, account charges, deposits, check deposits, programmed operations confirmation, recurring transfers confirmation |
| **Email format** | HTML (likely) |
| **Amount format** | MXN standard |
| **Notes** | "Banorte Avisa" is their branded notification service. Alerts available via email and/or mobile phone. Covers deposits, charges, check deposits, confirmation of scheduled/recurring operations. |

### 3. Citibanamex (banamex.com / citibanamex.com)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | `notificaciones@banamex.com` (confirmed from official Banamex help center) |
| **Sender domain(s)** | `banamex.com`, `citibanamex.com` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchases, withdrawals, deposits, account additions/deletions/modifications, password changes, security alerts |
| **Email format** | HTML (likely) |
| **Amount format** | MXN standard |
| **Notes** | Official sender is `notificaciones@banamex.com` — users advised to add to contacts to avoid spam filtering. Requires NetKey via BancaNet or branch activation. Mobile number portability supported across all Mexican carriers. |

### 4. Santander Mexico (santander.com.mx)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED |
| **Sender emails** | `notificaciones@notificaciones.santander.com.mx` (confirmed by official Santander Mexico Twitter/X account) |
| **Sender domain(s)** | `notificaciones.santander.com.mx`, `santander.com.mx` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Card purchases, transfers, account operations |
| **Email format** | HTML (likely) |
| **Amount format** | MXN standard |
| **Notes** | Official sender confirmed as `notificaciones@notificaciones.santander.com.mx` (note: subdomain `notificaciones.santander.com.mx`). Report fraud to `delitosinformaticos@santander.com.mx`. Report phishing to `reportphishing@gruposantander.com`. |

### 5. Nu Mexico (nu.com.mx)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | From `@nu.com.mx` domain. Support: `ayuda@nu.com.mx` |
| **Sender domain(s)** | `nu.com.mx` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchase/payment alerts (debit and credit card), account changes |
| **Email format** | HTML (modern fintech design) |
| **Amount format** | MXN standard |
| **Notes** | Official emails end in `@nu.com.mx` only — never generic domains. However, Nu states that "notifications never arrive via SMS or email" — they are push-only from the official app. Email is used for account communications (statements, regulatory), not real-time purchase alerts. Similar to Nequi, this makes Nu Mexico LOW PRIORITY for real-time transaction email parsing. |

---

## Peru (PE)

### 1. BCP - Banco de Credito del Peru (viabcp.com)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED |
| **Sender emails** | `bcpcomunica@bcp.com.pe` (official — confirmed by BCP security page: "Los correos oficiales del BCP son enviados solo desde el buzon BCP Comunica: bcpcomunica@bcp.com.pe") |
| **Sender domain(s)** | `bcp.com.pe` |
| **Known subjects** | Unknown specific subjects — notifications of purchases abroad and in Peru arrive at registered email |
| **Notification types** | Purchase alerts (domestic and international), transfer confirmations, account notifications |
| **Email format** | HTML (likely with BCP branding) |
| **Amount format** | PEN: `S/ XX.XX` (soles with dot decimal) or USD: `$ XX.XX` |
| **Notes** | Single official sender: `bcpcomunica@bcp.com.pe`. All internal links direct to `.viabcp.com` domains. To unsubscribe, reply to `bcpcomunica@bcp.com.pe` with subject "REMOVER". |

### 2. Interbank (interbank.pe)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `interbank.pe` domain. Suspicious email verification: `alertasinterbank@interbank.pe` |
| **Sender domain(s)** | `interbank.pe`, `interbank.com.pe` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchase alerts (card transactions), consumption alerts with configurable threshold (default S/ 60.00), security alerts |
| **Email format** | HTML (likely) |
| **Amount format** | PEN standard |
| **Notes** | Interbank offers "Alertas de consumo" (consumption alerts) as a security feature. Default threshold of S/ 60.00 triggers validation code request. Legitimate emails reference customer name (vs. generic "Estimado" in phishing). Forward suspicious emails to `alertasinterbank@interbank.pe`. |

### 3. BBVA Peru (bbva.pe)

| Field | Value |
|---|---|
| **Confidence** | LOW |
| **Sender emails** | Likely from `bbva.pe` or shared BBVA infrastructure (`bbva.com`) |
| **Sender domain(s)** | `bbva.pe`, `bbva.com` |
| **Known subjects** | Unknown |
| **Notification types** | Card purchase alerts, deposit notifications, security alerts for unusual movements |
| **Email format** | HTML with BBVA branding |
| **Amount format** | PEN standard |
| **Notes** | BBVA Peru follows the global BBVA notification pattern. App-based monitoring + email/SMS alerts for security events. Limited specific documentation found for Peru-specific email formats. |

### 4. Scotiabank Peru (scotiabank.com.pe)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Support/verification: `scotiaenlinea@scotiabank.com.pe`. Notification sender likely from same domain. |
| **Sender domain(s)** | `scotiabank.com.pe` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Push notifications for card transactions (primary channel), email for OTP codes, security alerts |
| **Email format** | HTML (likely) |
| **Amount format** | PEN standard |
| **Notes** | Scotiabank Peru emphasizes push notifications as the primary alert channel. They will never request secret password, PIN, Token Key, card number, or account number via email. Forward suspicious emails to `scotiaenlinea@scotiabank.com.pe`. |

### 5. Yape by BCP (yape.com.pe)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | `bcpcomunica@bcp.com.pe` (shares BCP's email infrastructure for card-related notifications) |
| **Sender domain(s)** | `bcp.com.pe`, `yape.com.pe` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Transfer confirmations, payment alerts (configurable threshold, default S/ 60.00), account updates |
| **Email format** | HTML (likely) |
| **Amount format** | PEN standard |
| **Notes** | Yape is BCP's mobile wallet — primarily push-based. Email notifications for transfers are optional and configurable in app settings. Uses same `bcpcomunica@bcp.com.pe` sender as parent BCP. WhatsApp support: +51 939 339 299. LOW PRIORITY for email parsing — Yape is fundamentally a push-notification product. |

---

## Brazil (BR)

### 1. Nubank (nubank.com.br)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | `todomundo@nubank.com.br` (confirmed legitimate by NuCommunity), `todomundo@novidades.nubank.com.br` (marketing/news). Support: `meajuda@nubank.com.br` |
| **Sender domain(s)** | `nubank.com.br`, `novidades.nubank.com.br` |
| **Known subjects** | Unknown specific subjects — purchase notifications sent via push only |
| **Notification types** | Account statements, regulatory confirmations, product updates via email. Purchase/transfer alerts via push ONLY (not email). |
| **Email format** | HTML (modern design, SendGrid-powered) |
| **Amount format** | BRL: `R$ XX.XXX,XX` (dot = thousands, comma = decimal) |
| **Notes** | Nubank explicitly states purchase notifications are push-only, never SMS or email. Email used for statements, account communications, and marketing. Uses Twilio/SendGrid for email delivery. LOW PRIORITY for real-time transaction email parsing. |

### 2. Itau (itau.com.br)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `itau-unibanco.com.br` or `itau.com.br` domain. Report suspicious: `emailsuspeito@itau-unibanco.com.br` |
| **Sender domain(s)** | `itau.com.br`, `itau-unibanco.com.br` |
| **Known subjects** | "Aviso SMS" subjects (specific email subjects unknown) |
| **Notification types** | Card purchase alerts (SMS service — R$7.99/month), WhatsApp alerts for suspicious transactions, app push notifications |
| **Email format** | HTML (likely) |
| **Amount format** | BRL standard |
| **Notes** | Itau's primary purchase notification channel is "Aviso SMS" (paid service R$7.99/month) and WhatsApp alerts for suspicious transactions. Email notifications are less prominent — app push and SMS are primary channels. Itau also offers stock/investment alerts via email through Itau Corretora. |

### 3. Bradesco (bradesco.com.br)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | Report fraud to: `evidencia@bradesco.com.br`. Transaction senders likely from `bradesco.com.br` domain |
| **Sender domain(s)** | `bradesco.com.br` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchase alerts (via Bradesco Cartoes app push), card transaction notifications (date, time, amount, card used), security alerts |
| **Email format** | HTML (likely) |
| **Amount format** | BRL standard |
| **Notes** | Bradesco offers "InfoEmail e InfoCelular" service for email and mobile notifications. Purchase alerts primarily via push notification through the app. Has both credit card (Bradesco Cartoes) and general banking notification services. |

### 4. Banco do Brasil (bb.com.br)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `@bb.com.br` domain (specific notification address unknown) |
| **Sender domain(s)** | `bb.com.br` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Card purchases (>= R$30), Pix transactions, transfers, withdrawals, scheduled payments, deposits, stock transactions |
| **Email format** | HTML (likely) |
| **Amount format** | BRL standard |
| **Notes** | IMPORTANT: Since December 2024, Banco do Brasil moved card purchase notifications from SMS to push-only via the BB app (per Central Bank guidelines). Email may still be used for statement-type communications. LOW PRIORITY for real-time transaction email parsing. |

### 5. Banco Inter (bancointer.com.br / inter.co)

| Field | Value |
|---|---|
| **Confidence** | MEDIUM |
| **Sender emails** | From `bancointer.com.br` or `inter.co` domain. Security: `gestao.incidentes@bancointer.com.br` |
| **Sender domain(s)** | `bancointer.com.br`, `inter.co` |
| **Known subjects** | Unknown specific subjects |
| **Notification types** | Purchase alerts (push), PJ account transaction emails (Pix, TED, bill payments), security alerts |
| **Email format** | HTML (likely) |
| **Amount format** | BRL standard |
| **Notes** | Banco Inter sends purchase alerts primarily via push. For PJ (business) accounts, transaction communications (Pix, TED, bill payments) are sent to email. Pix receipts are NOT sent via email — must be generated in-app. Personal account notifications are primarily app-based. |

---

## USA (US)

### 1. Bank of America (bankofamerica.com)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED (from project email templates) |
| **Sender emails** | `onlinebanking@ealerts.bankofamerica.com` (transaction alerts, Zelle), `customerservice@ealerts.bankofamerica.com` (account service alerts) |
| **Sender domain(s)** | `ealerts.bankofamerica.com`, `bankofamerica.com` |
| **Known subjects** | "Credit card transaction exceeds alert limit you set", "Zelle(R) payment of $X to NAME has been sent" |
| **Notification types** | Credit card purchase (threshold-based), Zelle payment sent/received, account balance alerts, unusual activity, payment due reminders |
| **Email format** | HTML with structured text. Purchase alerts use labeled fields: `Amount:`, `Date:`, `Where:`. Zelle uses: `Sent from account`, `To`, `Your message`, `Confirmation` |
| **Amount format** | USD: `$17.08` / `$2,000.00` (dot = decimal, comma = thousands) |
| **Date format** | English: `March 28, 2026` |
| **Key fields** | Card name + last 4 digits, amount, date, merchant ("Where:"), account ending |
| **Sample body (purchase)** | `Customized Cash Rewards Visa Signature ending in 5876 \n Amount: $17.08 \n Date: March 28, 2026 \n Where: TARGET STORE- T3206` |
| **Sample body (Zelle)** | `Zelle(R) payment of $2,000.00 to BENJAMIN BRAITHWAITE has been sent \n Sent from account ending in 7422 \n To 646-215-0024` |

### 2. Chase / JPMorgan (chase.com)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | `no.reply.alerts@chase.com` (transaction alerts — widely reported by users), possibly also `no-reply@alertsp.chase.com` (though this one has been flagged as suspicious by some users) |
| **Sender domain(s)** | `chase.com`, `alertsp.chase.com` |
| **Known subjects** | "Your [account type] transaction", "Payment posted", "Balance alert" (specific formats vary by alert type) |
| **Notification types** | Card charges/refunds, balance transfer/payment posted, balance and credit limit, payment due/posted, transaction threshold alerts |
| **Email format** | HTML with Chase branding |
| **Amount format** | USD standard |
| **Notes** | Chase sends alerts by email, text, and push. Does not request confidential info via email. Report phishing to `phishing@chase.com`. Exact subject line templates not publicly documented. |

### 3. Wells Fargo (wellsfargo.com)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED |
| **Sender emails** | `alerts@notify.wellsfargo.com` (transaction alerts — confirmed by official FAQ), `notification@securemail.wellsfargo.com` (secure messages), `PaymentRemittanceInformation@wellsfargo.com` (payment remittances) |
| **Sender domain(s)** | `notify.wellsfargo.com`, `securemail.wellsfargo.com`, `wellsfargo.com` |
| **Known subjects** | "Payment details from [company] sent by Wells Fargo" (remittance), transaction alert subjects (specific formats vary) |
| **Notification types** | Card purchase (near real-time at authorization), deposit posted, balance thresholds, payment confirmations, security/access change alerts, one-time passcodes |
| **Email format** | HTML with transaction details (amount, time, date, merchant name, location) |
| **Amount format** | USD standard |
| **Notes** | Alerts sent near real-time at authorization (e.g., gas station purchase). Deposit alerts typically sent next business day. Available for checking, savings, credit cards, mortgages, auto loans, CDs. Add `alerts@notify.wellsfargo.com` to contacts to prevent spam filtering. |

### 4. Citi (citi.com)

| Field | Value |
|---|---|
| **Confidence** | HIGH |
| **Sender emails** | `citicards@info3.citibank.com` (Fraud Early Warning), general alerts from `@citi.com` domain |
| **Sender domain(s)** | `citi.com`, `citibank.com`, `info3.citibank.com` |
| **Known subjects** | Unknown specific transaction alert subjects |
| **Notification types** | Statement availability, payment reminders, balance levels, credit limit exceeded, real-time card transaction alerts (commercial cards), Fraud Early Warning alerts |
| **Email format** | HTML with Citi branding |
| **Amount format** | USD standard |
| **Notes** | Alerts can be sent to up to 2 email addresses and 2 mobile numbers. Official emails end with `@citi.com`. Report phishing to `spoof@citi.com`. Citi also offers SMS Fraud Early Warning for suspicious transactions. |

### 5. PNC (pnc.com)

| Field | Value |
|---|---|
| **Confidence** | VERIFIED (from project email templates + official documentation) |
| **Sender emails** | `pncalerts@pnc.com`, `noreply.pncalerts@pnc.com` |
| **Sender domain(s)** | `pnc.com` |
| **Known subjects** | "You sent a Zelle(R) payment to [NAME]", "You Received a Zelle(R) payment from [NAME]", transaction alert subjects |
| **Notification types** | Card purchases (online, phone, international), Zelle sent/received, security alerts (username/password changes, contact info changes), account access alerts |
| **Email format** | HTML/text. Zelle emails use structured fields with date format `MM/DD/YY` (e.g., `04/06/26`) |
| **Amount format** | USD standard |
| **Date format** | `MM/DD/YY` (e.g., `Payment Date: 04/06/26`) |
| **Key fields** | Transaction amount, date, merchant/recipient name (ALL CAPS for Zelle recipients) |
| **Notes** | Report phishing to `abuse@pnc.com`. PNC supports Zelle integration. Already parsed in Luka's pipeline with specific patterns for PNC Zelle. |

---

## Summary: Priority Matrix for Email Parsing

### Tier 1 — Already Parsing / Verified Templates
| Bank | Country | Sender |
|---|---|---|
| Banco de Chile | CL | `enviodigital@bancochile.cl`, `serviciodetransferencias@bancochile.cl` |
| Santander Chile | CL | `@santander.cl` |
| Bank of America | US | `onlinebanking@ealerts.bankofamerica.com` |
| PNC | US | `pncalerts@pnc.com`, `noreply.pncalerts@pnc.com` |

### Tier 2 — High Confidence, Ready to Implement
| Bank | Country | Sender |
|---|---|---|
| Bancolombia | CO | `alertasynotificaciones@notificacionesbancolombia.com` |
| BCP Peru | PE | `bcpcomunica@bcp.com.pe` |
| Santander Mexico | MX | `notificaciones@notificaciones.santander.com.mx` |
| Citibanamex | MX | `notificaciones@banamex.com` |
| Wells Fargo | US | `alerts@notify.wellsfargo.com` |
| Chase | US | `no.reply.alerts@chase.com` |
| Citi | US | `citicards@info3.citibank.com` |

### Tier 3 — Domain Known, Needs Email Samples
| Bank | Country | Domain |
|---|---|---|
| BancoEstado | CL | `bancoestado.cl` |
| BCI | CL | `bci.cl` |
| Banco Falabella | CL | `bancofalabella.cl` |
| Davivienda | CO | `davivienda.com` |
| BBVA Colombia | CO | `bbva.com.co` |
| BBVA Mexico | MX | `bbva.mx` |
| Banorte | MX | `banorte.com` |
| Interbank | PE | `interbank.pe` |
| Scotiabank Peru | PE | `scotiabank.com.pe` |
| Nubank BR | BR | `nubank.com.br` |
| Itau | BR | `itau.com.br`, `itau-unibanco.com.br` |
| Bradesco | BR | `bradesco.com.br` |
| Banco Inter | BR | `bancointer.com.br`, `inter.co` |

### Tier 4 — Low Priority (Push-Only / No Email Transaction Alerts)
| Bank | Country | Reason |
|---|---|---|
| Nequi | CO | Push-only for transaction alerts |
| Nu Mexico | MX | Push-only for transaction alerts |
| Banco do Brasil | BR | Moved to push-only Dec 2024 |
| Yape | PE | Mobile wallet, push-only |
| BBVA Peru | PE | Limited email documentation |
| Banco de Bogota | CO | Email for educational content only |

---

## Key Patterns by Region

### Chile
- **Amount format**: `$XX.XXX` (dot = thousands, no decimals for CLP)
- **Date format**: `DD/MM/YYYY HH:MM` or `DD/MM/YYYY`
- **Language**: Spanish with Chilean banking terminology (`compra`, `transferencia`, `tarjeta de credito/debito`, `cuenta corriente`, `cuenta vista`)
- **Common keywords**: `compra por`, `transferencia de fondos`, `Monto`, `Comercio`, `Datos de destino/origen`

### Colombia
- **Amount format**: `$XXX.XXX` (dot = thousands, COP has no decimal typical usage)
- **Language**: Spanish with Colombian banking terms
- **Notable**: Bancolombia uses a separate domain (`notificacionesbancolombia.com`) for notification emails
- **Common keywords**: `Compra por`, `Transferencia`, `Alertas y Notificaciones`

### Mexico
- **Amount format**: `$XX,XXX.XX` (comma = thousands, dot = decimal)
- **Language**: Spanish with Mexican banking terms
- **Notable**: Santander Mexico uses subdomain (`notificaciones.santander.com.mx`), BBVA uses subdomain (`email.bbva.mx`)
- **Common keywords**: `compra`, `transferencia`, `notificacion`

### Peru
- **Amount format**: `S/ XX.XX` (Soles), `$ XX.XX` (USD)
- **Language**: Spanish with Peruvian banking terms
- **Notable**: BCP is the only bank with a fully verified single sender address
- **Common keywords**: `compra`, `transferencia`, `consumo`

### Brazil
- **Amount format**: `R$ XX.XXX,XX` (dot = thousands, comma = decimal)
- **Language**: Portuguese
- **Notable**: Major trend toward push-only notifications (BB moved Dec 2024). Email used more for statements than real-time alerts.
- **Common keywords**: `compra`, `transferencia`, `transacao`, `cartao`, `fatura`

### USA
- **Amount format**: `$XX,XXX.XX` (comma = thousands, dot = decimal)
- **Date format**: `Month DD, YYYY` (Bank of America) or `MM/DD/YY` (PNC)
- **Language**: English
- **Notable**: Most mature email notification ecosystem. Zelle is a cross-bank pattern.
- **Common keywords**: `Amount:`, `Where:`, `Date:`, `payment`, `transaction`, `Zelle`

---

## Domains to Add to BANK_SENDER_DOMAINS (filter.py)

```python
# Colombia
"bancolombia.com",
"bancolombia.com.co",
"notificacionesbancolombia.com",
"davivienda.com",
"bancodebogota.com.co",
"bbva.com.co",
"nequi.com.co",

# Mexico
"bbva.mx",
"email.bbva.mx",
"banorte.com",
"banamex.com",
"citibanamex.com",
"santander.com.mx",
"notificaciones.santander.com.mx",
"nu.com.mx",

# Peru
"bcp.com.pe",
"viabcp.com",
"interbank.pe",
"interbank.com.pe",
"bbva.pe",
"scotiabank.com.pe",
"yape.com.pe",

# Brazil
"nubank.com.br",
"novidades.nubank.com.br",
"itau.com.br",
"itau-unibanco.com.br",
"bradesco.com.br",
"bb.com.br",
"bancointer.com.br",
"inter.co",
```

## Financial Keywords to Add (filter.py)

```python
# Portuguese (Brazilian banks)
"transacao",
"transação",
"compra aprovada",
"cartao",
"cartão",
"fatura",
"pagamento",
"transferencia",  # already present (shared with Spanish)
"pix",
"deposito",  # already present
"saldo",  # already present
"debito",  # already present
"credito",  # already present

# Colombian / Mexican specific
"movimiento",
"consumo",
"retiro",  # already present
"aviso",
"alerta",
"notificacion",
"notificación",
```
