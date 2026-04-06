# LLM-Powered Email Parser for LATAM Expansion

> **Status:** Draft — reviewed, pending user approval
> **Date:** 2026-04-06
> **Author:** Rafael Labrao + Claude

## Problem Statement

Luka's current email parser uses regex patterns to extract transaction data (merchant name, amount, date, type) from bank notification emails. This approach has three critical limitations:

1. **Accuracy:** ~95% of parsing failures are the regex extracting the wrong string (e.g., grabbing nearby text as the merchant name instead of the actual one)
2. **Scalability:** Adding new banks requires manually writing regex patterns from sample emails — impractical for multi-country expansion
3. **Maintenance:** Banks change their email HTML templates without warning, breaking previously-working regex patterns

## Solution Overview

Replace the regex-based extraction with a **three-layer parsing system**:

1. **Template Layer** (fastest, free) — auto-generated extraction functions for known bank email formats
2. **LLM Layer** (fast, cheap) — Gemini-powered structured extraction with a confidence-based model waterfall
3. **Legacy Regex Layer** (fallback) — existing regex parser as a last resort

An autonomous **Template Agent** runs daily, discovers patterns in LLM-parsed emails, generates extraction templates, validates them, promotes them to production, monitors for drift, and auto-rollbacks when bank formats change — all without human intervention.

## Architecture

### Parsing Flow

```
Email arrives
  → Pre-filter (bank_registry domain lookup + financial keyword match)
  → get_bank_metadata(sender) → {bank, country, template_id}

  IF template_id exists AND template.status == 'active':
    → Run template extraction
    → IF succeeds (all required fields present):
        → Use template result ✓ (cost: $0)
        → 10% chance: also run LLM silently (shadow validation)
    → IF fails (missing field or exception):
        → Fall through to LLM

  ELSE (no template):
    → Run LLM extraction (confidence waterfall)
    → Store raw_email_html for 7 days (template training data)

  IF LLM fails:
    → Fall back to legacy regex parser

  → Continue existing pipeline (merchant lookup, categorization, tx creation, WhatsApp)
```

### Confidence Waterfall

The LLM layer escalates through increasingly expensive/accurate models based on confidence scores:

```
Gemini 3.1 Flash Lite ($0.00028/tx)
  → confidence ≥ 0.9? → Use result ✓
  → confidence < 0.9? → Escalate ↓

Gemini 2.5 Flash ($0.00040/tx)
  → confidence ≥ 0.8? → Use result ✓
  → confidence < 0.8? → Escalate ↓

Gemini 3 Flash ($0.00055/tx)
  → confidence ≥ 0.7? → Use result ✓
  → confidence < 0.7? → Escalate ↓

Gemini 2.5 Pro ($0.00163/tx)
  → Use result regardless (best available)
  → If confidence still < 0.5 → flag for human review via WhatsApp
```

**Expected distribution (steady state):** 75% resolved at Flash Lite, 15% at 2.5 Flash, 8% at 3 Flash, 2% at 2.5 Pro. Weighted average: ~$0.00047/tx.

### LLM Extraction Schema

Input: stripped email text (existing `_strip_html()` preprocessor) + bank metadata context from registry.

System prompt enforces JSON output:

```json
{
  "merchant": "LIDER EXPRESS",
  "amount": 15990,
  "currency": "CLP",
  "transaction_date": "2026-04-05T14:32:00",
  "transaction_type": "expense",
  "transfer_recipient": null,
  "card_last_four": "4532",
  "confidence": 0.95
}
```

- `transaction_type`: one of `"expense"`, `"transfer"`, `"income"`
- `transfer_recipient`: populated only when `transaction_type == "transfer"`
- `amount`: integer in smallest currency unit (CLP as integer, USD as cents, BRL as centavos)
- `confidence`: 0.0–1.0 self-assessed extraction confidence

**Mapping to existing `ParsedEmail` dataclass:** The LLM extraction result is mapped to the existing `ParsedEmail` dataclass before entering the downstream pipeline:
- `merchant` → `ParsedEmail.raw_merchant`
- `amount` → `ParsedEmail.amount`
- `currency` → `ParsedEmail.currency`
- `transaction_date` → `ParsedEmail.transaction_date`
- `transaction_type` → `ParsedEmail.transaction_type`
- `transfer_recipient` → `ParsedEmail.transfer_recipient` (new field to add to dataclass)
- `card_last_four` → `ParsedEmail.card_last_four` (new field to add to dataclass)
- `confidence` → not stored in `ParsedEmail`, only in `parsed_email_log`
- `bank_name` → inferred from `get_bank_metadata()`, not from LLM (same as current flow)

**Per-currency amount instructions in system prompt:** The LLM prompt must include explicit conversion rules:
- CLP (Chile): return integer pesos, no subunits. `$15.990` → `15990`
- COP (Colombia): return integer pesos, no subunits. `$450.000` → `450000`
- MXN (Mexico): return integer centavos. `$1,250.50` → `125050`
- PEN (Peru): return integer céntimos. `S/ 150.00` → `15000`
- BRL (Brazil): return integer centavos. `R$ 1.250,50` → `125050`
- USD (USA): return integer cents. `$17.08` → `1708`

### Template Agent

An autonomous ARQ cron job on the slow worker, runs daily at 2am.

**Lifecycle:**

```
DISCOVER → GENERATE → VALIDATE → PROMOTE → MONITOR → ROLLBACK (if needed)
```

**1. Discover** — Query `parsed_email_log` for banks with 20+ total LLM-parsed transactions (with at least 5 in the last 14 days) that don't have an active template. This cumulative threshold with a recency requirement accommodates both high-volume banks and smaller banks with fewer daily emails.

**2. Generate** — Send 10 sample raw email HTMLs + their LLM extraction results to Gemini Flash with a meta-prompt: *"Given these emails and their correct extractions, generate a declarative extraction template as JSON with CSS selectors and extraction rules."* Output: a JSON template (NOT arbitrary Python code — see Security section below).

**3. Validate** — Run the generated template against all 20+ emails for that bank. Compare output to LLM extraction ground truth. Requirements:
- 100% match on amount
- 95%+ match on merchant (allowing minor normalization differences)
- 90%+ match on date (allowing timezone offset differences)

If validation fails → discard template, retry next day with more samples.

**4. Promote** — Store template in `email_templates` table (status=`active`). Update `bank_registry.active_template_id`. From now on, emails from this bank use the template.

**5. Monitor** — Every day, for 10% of template-parsed transactions, also run the LLM parser (shadow validation) and compare results. Log agreement in `parsed_email_log.shadow_match`.

**6. Rollback** — Two drift thresholds:
- **Amount mismatch:** ANY amount mismatch in a shadow batch → immediate retirement (amounts must be 100% accurate)
- **Other fields (merchant, date, type):** If overall shadow accuracy drops below 90% → retire

On retirement: set status=`retired`, clear `bank_registry.active_template_id`, send WhatsApp alert to admin: *"Template for [Bank Name] retired — email format may have changed. LLM fallback active."* The agent will attempt to generate a new template after accumulating 20+ fresh LLM-parsed emails.

## Data Model

### New Tables

#### `email_templates`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `bank_domain` | VARCHAR (indexed) | e.g., `bancochile.cl` |
| `country` | VARCHAR(2) | ISO country code |
| `template_code` | JSONB | Declarative extraction template (CSS selectors + regex + transforms) |
| `template_hash` | VARCHAR(64) | SHA-256 of template JSON for dedup |
| `status` | VARCHAR | `candidate` / `active` / `retired` / `failed` |
| `validated_count` | INT | Emails validated against before promotion |
| `accuracy` | FLOAT | Validation accuracy (0.0–1.0) |
| `promoted_at` | TIMESTAMP | Nullable |
| `retired_at` | TIMESTAMP | Nullable |
| `retired_reason` | TEXT | Nullable, e.g., "drift detected: amount mismatch 3/10" |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

#### `parsed_email_log`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK → users, CASCADE) | |
| `bank_domain` | VARCHAR (indexed) | |
| `country` | VARCHAR(2) | |
| `raw_email_html` | TEXT (nullable) | Purged after 7 days |
| `llm_extraction` | JSONB | `{merchant, amount, currency, date, type, confidence}` |
| `template_extraction` | JSONB (nullable) | Same schema, when template was used |
| `parser_used` | VARCHAR | `"llm"` / `"template"` |
| `llm_model_used` | VARCHAR | e.g., `"gemini-3.1-flash-lite"` |
| `shadow_match` | BOOLEAN (nullable) | Template vs LLM agreement |
| `waterfall_depth` | INT | 1=first model worked, 2=escalated once, etc. |
| `created_at` | TIMESTAMP (indexed) | For purge job |

#### `bank_registry`

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | |
| `bank_domain` | VARCHAR (unique, indexed) | |
| `bank_name` | VARCHAR | |
| `country` | VARCHAR(2) (indexed) | |
| `known_subjects` | JSONB | `["Comprobante de compra", ...]` |
| `notification_types` | JSONB | `["purchase", "transfer", ...]` |
| `active_template_id` | UUID (FK → email_templates, nullable) | |
| `email_count` | INT DEFAULT 0 | Total emails processed |
| `status` | VARCHAR DEFAULT 'active' | `active` / `push_only` / `deprecated` |
| `last_seen_at` | TIMESTAMP (nullable) | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### Existing Table Changes

None. No changes to existing tables. The `raw_email_text` field on transactions continues with its 24h purge — the new `parsed_email_log.raw_email_html` is a separate, longer retention copy for template training.

## Pre-Filter: LATAM Bank Registry

### Baseline Banks (30 banks, 6 countries)

Seeded into `bank_registry` on first migration.

#### Chile (CL)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| Banco de Chile | `bancochile.cl` | `enviodigital@bancochile.cl`, `serviciodetransferencias@bancochile.cl` | VERIFIED |
| BancoEstado | `bancoestado.cl` | `notificaciones@bancoestado.cl` | MEDIUM |
| Santander Chile | `santander.cl` | `@santander.cl` | VERIFIED |
| BCI | `bci.cl`, `bcidigital.cl` | `notificaciones@bci.cl` | MEDIUM |
| Banco Falabella | `bancofalabella.cl` | `notificaciones@bancofalabella.cl` | MEDIUM |

Known subjects (CL): "Comprobante de compra", "Transferencia a Terceros", "Comprobante Transferencia de fondos", "Aviso de cargo"

#### Colombia (CO)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| Bancolombia | `notificacionesbancolombia.com`, `bancolombia.com.co` | `alertasynotificaciones@notificacionesbancolombia.com` | HIGH |
| Davivienda | `davivienda.com` | `alertas@davivienda.com` | MEDIUM |
| Banco de Bogotá | `bancodebogota.com.co` | Unknown | LOW |
| BBVA Colombia | `bbva.com.co`, `bbva.com` | `@bbva.com.co` | MEDIUM |
| Nequi | `nequi.com.co` | `@nequi.com.co` | LOW PRIORITY (push-only) |

**Note:** Bancolombia uses a separate domain `notificacionesbancolombia.com` — not the main `bancolombia.com`.

#### Mexico (MX)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| BBVA México | `bbva.mx`, `email.bbva.mx` | `@bbva.mx` | MEDIUM |
| Banorte | `banorte.com` | `@banorte.com` | MEDIUM |
| Citibanamex | `banamex.com`, `citibanamex.com` | `notificaciones@banamex.com` | HIGH |
| Santander México | `notificaciones.santander.com.mx`, `santander.com.mx` | `notificaciones@notificaciones.santander.com.mx` | VERIFIED |
| Nu México | `nu.com.mx` | `@nu.com.mx` | LOW PRIORITY (push-only) |

#### Peru (PE)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| BCP | `bcp.com.pe` | `bcpcomunica@bcp.com.pe` | VERIFIED |
| Interbank | `interbank.pe`, `interbank.com.pe` | `@interbank.pe` | MEDIUM |
| BBVA Perú | `bbva.pe`, `bbva.com` | `@bbva.pe` | LOW |
| Scotiabank Perú | `scotiabank.com.pe` | `@scotiabank.com.pe` | MEDIUM |
| Yape (BCP) | `bcp.com.pe`, `yape.com.pe` | `bcpcomunica@bcp.com.pe` | LOW PRIORITY (push-only) |

#### Brazil (BR)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| Nubank | `nubank.com.br`, `novidades.nubank.com.br` | `todomundo@nubank.com.br` | HIGH |
| Itaú | `itau.com.br`, `itau-unibanco.com.br` | `@itau.com.br` | MEDIUM |
| Bradesco | `bradesco.com.br` | `@bradesco.com.br` | MEDIUM |
| Banco do Brasil | `bb.com.br` | `@bb.com.br` | LOW PRIORITY (push-only since Dec 2024) |
| Banco Inter | `bancointer.com.br`, `inter.co` | `@bancointer.com.br` | MEDIUM |

**Note:** Brazil is trending push-only. Nubank, Banco do Brasil, and Banco Inter primarily use push for real-time transaction alerts. Email is used for statements and account communications.

#### USA (US)

| Bank | Sender Domain(s) | Sender Address | Confidence |
|------|------------------|----------------|------------|
| Bank of America | `ealerts.bankofamerica.com`, `bankofamerica.com` | `onlinebanking@ealerts.bankofamerica.com` | VERIFIED |
| Chase | `chase.com`, `alertsp.chase.com` | `no.reply.alerts@chase.com` | HIGH |
| Wells Fargo | `notify.wellsfargo.com`, `wellsfargo.com` | `alerts@notify.wellsfargo.com` | VERIFIED |
| Citi | `citi.com`, `citibank.com`, `info3.citibank.com` | `citicards@info3.citibank.com` | HIGH |
| PNC | `pnc.com` | `pncalerts@pnc.com`, `noreply.pncalerts@pnc.com` | VERIFIED |

### Regional Amount & Date Formats

| Region | Currency | Amount Format | Example | Date Format |
|--------|----------|---------------|---------|-------------|
| Chile | CLP | `$XX.XXX` (dot=thousands, no decimals) | `$15.990` | `DD/MM/YYYY HH:MM` |
| Colombia | COP | `$XXX.XXX` (dot=thousands, no decimals) | `$450.000` | `DD/MM/YYYY` |
| Mexico | MXN | `$XX,XXX.XX` (comma=thousands, dot=decimal) | `$1,250.50` | `DD/MM/YYYY` |
| Peru | PEN | `S/ XX.XX` (dot=decimal) | `S/ 150.00` | `DD/MM/YYYY` |
| Brazil | BRL | `R$ XX.XXX,XX` (dot=thousands, comma=decimal) | `R$ 1.250,50` | `DD/MM/AAAA` |
| USA | USD | `$XX,XXX.XX` (comma=thousands, dot=decimal) | `$1,250.50` | `MM/DD/YYYY` or `Month DD, YYYY` |

### Financial Keywords to Add

```python
# Portuguese (Brazilian banks)
PORTUGUESE_KEYWORDS = [
    "transação", "transacao", "compra aprovada", "cartão", "cartao",
    "fatura", "pagamento", "pix", "débito", "crédito",
]

# Additional Spanish (Colombia/Mexico/Peru)
ADDITIONAL_SPANISH_KEYWORDS = [
    "movimiento", "consumo", "aviso", "alerta",
    "notificación", "notificacion",
]
```

### Push-Only Banks (Low Priority)

These banks do NOT send real-time transaction alerts via email — they use push notifications exclusively:

| Bank | Country | Notes |
|------|---------|-------|
| Nequi | CO | App-only transaction notifications |
| Nu México | MX | App-only transaction notifications |
| Banco do Brasil | BR | Moved to push-only Dec 2024 |
| Yape | PE | Mobile wallet, push-only |
| Banco de Bogotá | CO | Email for educational content only |

These banks are included in the registry (for future compatibility) but are not expected to generate parseable transaction emails.

### Key Discovery: Notification Subdomains

Several major banks use separate subdomains for notification emails — the pre-filter must match these:

| Bank | Main Domain | Notification Domain |
|------|-------------|-------------------|
| Bancolombia | `bancolombia.com.co` | `notificacionesbancolombia.com` |
| Santander MX | `santander.com.mx` | `notificaciones.santander.com.mx` |
| Bank of America | `bankofamerica.com` | `ealerts.bankofamerica.com` |
| Wells Fargo | `wellsfargo.com` | `notify.wellsfargo.com` |
| Citi | `citi.com` | `info3.citibank.com` |

## Integration Points

### Files Modified

**1. `backend/modules/email/parser.py`**
- Current `parse_bank_email()` → renamed to `parse_bank_email_regex()` (kept as last-resort fallback)
- New `parse_bank_email()` orchestrates: template → LLM waterfall → regex fallback
- `_strip_html()` stays as-is (preprocessing for all paths)

**2. `backend/modules/email/filter.py`**
- `BANK_SENDER_DOMAINS` dict replaced with DB lookup to `bank_registry` table (Redis-cached)
- `is_bank_sender()` and `get_bank_name()` now query `bank_registry`
- `is_financial_email()` expanded with Portuguese and additional Spanish keywords
- New: `get_bank_metadata()` returns full registry entry for LLM context

**3. `backend/jobs/tasks.py`**
- `process_email()`: after parsing, write a row to `parsed_email_log`
- No other changes — downstream pipeline untouched

**4. `backend/worker.py`**
- Add `template_agent` to `SlowWorkerSettings.cron_jobs` (daily at 2am)
- Add `purge_email_logs` to `FastWorkerSettings.cron_jobs` (daily, cleans 7-day HTML)

### New Modules

**5. `backend/modules/email/llm_parser.py`** (new)
- `parse_with_llm(email_text, bank_metadata) → ParsedEmail`
- Confidence waterfall logic
- Structured JSON prompt with bank context
- Retry + fallback handling

**6. `backend/modules/email/template_agent.py`** (new)
- `run_template_agent()` — daily cron entry point
- `discover_patterns(bank_domain)` — find banks with 20+ untemplatized emails
- `generate_template(samples, extractions)` — LLM meta-prompt to create declarative JSON template
- `validate_template(template, emails, llm_results)` — accuracy check
- `promote_template(template_id)` — update bank_registry, set status=active
- `shadow_validate()` — 10% sample comparison
- `retire_template(template_id, reason)` — rollback + WhatsApp alert

### What Does NOT Change

- `backend/modules/email/base.py` (EmailProvider ABC)
- `backend/modules/email/gmail.py` / `outlook.py` (providers)
- `backend/modules/email/router.py` (webhooks)
- `backend/modules/merchants/` (categorization — completely separate concern)
- `backend/modules/transactions/` (models, service, idempotency)
- `backend/modules/whatsapp/` (alerts)
- Frontend — zero changes

## Data Privacy & Retention

| Data | Retention | Purpose |
|------|-----------|---------|
| `raw_email_html` in `parsed_email_log` | 7 days | Template Agent training data |
| `llm_extraction` in `parsed_email_log` | 90 days | Shadow validation + accuracy metrics |
| `template_extraction` in `parsed_email_log` | 90 days | Drift detection |
| Generated templates in `email_templates` | Forever | Active + retired for reference |
| Confidence scores + waterfall depth | 90 days | Threshold calibration |

**Privacy guardrails:**
- Raw HTML is stripped of user-identifiable info (names, RUTs, account numbers) before Template Agent analysis
- Template generation prompts only see HTML structure + extracted fields, not full personal content
- User data deletion (existing feature) cascades to `parsed_email_log`
- `purge_email_logs` cron runs daily on fast worker

**Storage estimate:** ~2KB per `parsed_email_log` row. At 10K tx/month with 7-day HTML retention: ~5MB rotating. Negligible.

## Cost Model

### Per-Transaction Costs

| Path | Cost/tx |
|------|---------|
| Template (active) | $0.00 |
| Shadow validation (10% of template txs) | $0.000028 avg |
| LLM — 3.1 Flash Lite (75%) | $0.00028 |
| LLM — 2.5 Flash escalation (15%) | $0.00068 cumulative |
| LLM — 3 Flash escalation (8%) | $0.00123 cumulative |
| LLM — 2.5 Pro escalation (2%) | $0.00286 cumulative |
| **Weighted LLM average** | **$0.00047/tx** |

### Monthly Projections (Gemini API only)

| Period | Template Coverage | Avg Cost/tx | Monthly @ 10K tx |
|--------|------------------|-------------|------------------|
| Month 1 (launch) | 0% — all LLM | $0.00047 | $4.70 |
| Month 2 | ~40% templates | $0.00030 | $3.00 |
| Month 3+ | ~70% templates | $0.00016 | $1.60 |
| Month 6+ | ~85% templates | $0.00009 | $0.90 |

### Infrastructure (unchanged)

| Component | Cost/month |
|-----------|-----------|
| Railway API + 2 workers | ~$10 |
| Gemini API (10K tx) | ~$1-5 (varies by month) |
| **Total** | **~$11-15** |

Budget headroom: $0.005/tx budget × 10K tx = $50/month budget. Actual spend: ~$5. **10x under budget.**

### Latency Impact

| Path | Latency Added | When |
|------|--------------|------|
| Template | ~5ms | After templates promoted (~70%+ of traffic by month 3) |
| LLM — Flash Lite only | ~300-500ms | 75% of LLM-path transactions |
| LLM — full waterfall | ~3-5s | <2% of transactions |
| Legacy regex fallback | ~5ms | Only if LLM also fails |

All parsing runs inside the async ARQ job — WhatsApp alert delivery adds ~300-500ms vs current. Imperceptible in a messaging flow.

## Competitive Context

Research on Kuanto.cl (the closest Chilean competitor) confirmed:

- **Kuanto uses the same email-based approach** — no real bank APIs, no Fintoc, no Floid
- They require **manual email forwarding** to `movimientos@kuanto.cl` (vs Luka's OAuth-based access)
- Built on **Xano + FlutterFlow** (no-code stack) — significantly less flexible
- Supports 8 Chilean banks, expanding to Colombia in 2026
- Chile's open banking mandate (Ley Fintec) won't be fully implemented until 2026-2028

This LLM parser gives Luka a structural advantage: any bank, any country, day one — without writing per-bank templates manually.

## Security

### Template Execution Safety

Templates are **declarative JSON** — NOT arbitrary Python code. The LLM generates a structured extraction template:

```json
{
  "bank_domain": "bancochile.cl",
  "version": 1,
  "selectors": {
    "amount": {
      "css": "td.monto",
      "regex": "\\$([\\d.]+)",
      "transform": "clp_integer"
    },
    "merchant": {
      "css": "td.comercio",
      "regex": "Comercio\\s+(.+?)\\s+Monto",
      "transform": "strip"
    },
    "date": {
      "css": "td.fecha",
      "regex": "(\\d{2}/\\d{2}/\\d{4}\\s+\\d{2}:\\d{2})",
      "transform": "parse_date_ddmmyyyy"
    },
    "transaction_type": {
      "keywords_expense": ["compra", "cargo", "pago"],
      "keywords_transfer": ["transferencia"],
      "keywords_income": ["abono", "deposito"]
    }
  }
}
```

A **template executor** (fixed Python code, not generated) interprets the JSON:
1. Parses HTML with BeautifulSoup
2. Applies CSS selectors from the template
3. Applies regex patterns from the template
4. Applies only pre-defined transforms (`clp_integer`, `usd_cents`, `strip`, `parse_date_ddmmyyyy`, etc.)

This architecture means:
- **No dynamic code execution** — templates are data, not code
- The set of allowed transforms is fixed and auditable
- A malformed template can only produce bad extractions (caught by validation), not run arbitrary operations
- Templates are validated against LLM ground truth before promotion — garbage templates never reach production

### RLS Policy for `parsed_email_log`

```sql
ALTER TABLE parsed_email_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY parsed_email_log_user_isolation ON parsed_email_log
  USING (user_id = auth.uid());
```

The Template Agent queries across users via a `SECURITY DEFINER` function (same pattern as existing partner privacy aggregate RPCs). The function returns only structural data (HTML patterns, extracted fields) — never user-identifiable information.

## Error Handling

### LLM API Failures in Waterfall

For each model in the waterfall:
- Try API call
- If 429 (rate limit) or 500 (server error): retry once with 2s backoff. If retry fails, escalate to next model (don't count as "low confidence")
- If malformed JSON response: escalate to next model
- If valid response with confidence score: apply confidence threshold

If all 4 models fail (API errors, not low confidence): fall back to legacy regex parser and log event for alerting.

**Circuit breaker:** If more than 50% of LLM calls in the last hour have failed (API errors), bypass the waterfall entirely and route all traffic to legacy regex for 15 minutes before retrying. This prevents cascading delays when Gemini has an outage.

### Confidence Calibration Strategy

LLM self-reported confidence is unreliable out of the box. Calibration strategy:

1. **Month 1:** Log all confidence scores alongside actual accuracy (verified via shadow validation or user corrections via WhatsApp)
2. **Month 2:** Analyze correlation between reported confidence and actual accuracy per model
3. **Adjust thresholds empirically:** If Flash Lite reports 0.9 confidence but is only 85% accurate, lower the threshold to 0.95. If it reports 0.7 but is 95% accurate, raise the threshold to 0.8.
4. **Store thresholds in config** (not hardcoded) — `WATERFALL_THRESHOLDS` in settings, adjustable without code deploy

Initial thresholds (0.9 / 0.8 / 0.7 / accept-all) are starting points, not final values.

## Observability

Key metrics to track (structured log entries, queryable):

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Waterfall depth distribution | `parsed_email_log.waterfall_depth` | More than 30% reaching depth 3+ |
| Template coverage % | `parsed_email_log.parser_used` | Below 50% after month 3 |
| Shadow mismatch rate | `parsed_email_log.shadow_match` | More than 5% mismatches per bank |
| Amount mismatch (shadow) | Shadow validation | ANY amount mismatch triggers immediate alert |
| LLM API error rate | LLM parser logs | More than 10% in 15-minute window |
| Avg LLM latency by model | LLM parser logs | Over 2s for Flash Lite |
| Template retirement events | Template Agent logs | Any retirement triggers WhatsApp alert |

Shadow validation sample rate is **configurable** (default 10%, recommend 25% in month 1, tunable down as templates stabilize).

`parsed_email_log.parser_used` includes three values: `"llm"`, `"template"`, `"regex"` — the regex fallback is also logged for visibility into how often it fires.

## Migration Strategy

### Alembic Migration Plan

**Migration 1 (single revision):** Create `email_templates`, `parsed_email_log`, `bank_registry` tables + RLS policies + indexes. Seed `bank_registry` with the 30 baseline banks from the LATAM Bank Registry section + all existing banks from the current `BANK_SENDER_DOMAINS` in `filter.py` (Chilean fintechs: Mercado Pago, Mach, Tenpo, TAPP, etc. + US neobanks: Venmo, Cash App, etc.). This ensures zero regression — every domain currently recognized stays recognized.

### `bank_registry.status` Field

Add a `status` field to `bank_registry`:
- `active` — bank sends transaction emails, parse them
- `push_only` — bank uses push notifications only, included for future compatibility
- `deprecated` — bank domain no longer in use

The pre-filter skips `push_only` and `deprecated` banks to avoid unnecessary LLM calls.
