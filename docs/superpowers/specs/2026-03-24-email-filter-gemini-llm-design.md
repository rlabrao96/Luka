# Email Pre-Filter + Gemini LLM Classification

**Date:** 2026-03-24
**Status:** Approved

## Overview

Two changes to the email-to-transaction pipeline:

1. **Email pre-filter** — broad keyword-based filter that runs before the regex parser to quickly skip non-financial emails (newsletters, promos, personal mail).
2. **Gemini LLM swap** — replace OpenAI `gpt-4o-mini` with Google Gemini 2.0 Flash for merchant categorization. Cheaper, user already has a Google AI Studio account.

Additionally: create a `docs/email-templates/` reference folder organized by bank for training parser patterns.

## 1. Email Pre-Filter

### File: `backend/modules/email/filter.py` (new)

**Function:** `is_financial_email(subject: str, sender: str, body: str) → bool`

Concatenates subject + sender + body, lowercases, checks if ANY keyword from a hardcoded set appears. Returns `True` if financial, `False` otherwise.

**Keyword set:**
```python
FINANCIAL_KEYWORDS = {
    "banco", "transferencia", "transaccion", "transacción",
    "compra", "pago", "tarjeta",
    "crédito", "credito", "débito", "debito",
    "abono", "depósito", "deposito",
    "giro", "cajero", "monto",
    "cuenta corriente", "cuenta vista",
    "línea de crédito", "linea de credito",
    "pac", "pat", "cuota", "cargo",
    "comprobante", "saldo",
}
```

**Design rationale:**
- Bank-agnostic: no sender domain or bank name matching.
- Loose filter: any single keyword match passes. The regex parser (`parse_bank_email`) is the second, stricter filter.
- Hardcoded: financial terms in Spanish are stable. Can be extended later.
- Case-insensitive: all comparisons done on lowercased text.

### Integration in `process_email` (tasks.py)

The pre-filter runs inside the per-email loop, BEFORE `parse_bank_email()`:

```python
from modules.email.filter import is_financial_email

# Inside the emails loop (currently line ~287):
if not is_financial_email(raw_email.subject, raw_email.sender, raw_email.body):
    continue  # skip non-financial emails

parsed = parse_bank_email(raw_email.body)
if not parsed:
    continue
```

### Email types captured

Based on Banco de Chile examples (and generalized for other banks):

| Type | Keywords that match |
|------|-------------------|
| Transfer to third party | transferencia, comprobante, cuenta corriente, banco, monto |
| Credit card purchase | compra, tarjeta, crédito, monto |
| Credit card payment | pago, tarjeta, crédito, comprobante, monto |
| Deposit / income | abono, depósito, cuenta |
| PAC/PAT auto-payments | pac, pat, pago, cargo |
| Line of credit | línea de crédito, cargo |
| ATM withdrawal | giro, cajero |

## 2. Gemini LLM Swap

### File: `backend/modules/merchants/llm.py` (modified)

**Before:** OpenAI `gpt-4o-mini`, returns 4 categories.
**After:** Google Gemini 2.0 Flash via `google-genai` SDK, returns 3 categories.

```python
import google.generativeai as genai
from core.config import settings

genai.configure(api_key=settings.gemini_api_key)
model = genai.GenerativeModel("gemini-2.0-flash")
```

**Prompt** (same spirit, updated count):
```
Eres un asistente de finanzas personales chileno.
Cuando recibas el nombre de un comercio de un banco chileno,
responde ÚNICAMENTE con un JSON con exactamente 3 categorías de presupuesto en español.
Formato: {"categories": ["cat1","cat2","cat3"]}
```

**Retry:** Same `tenacity` config (3 attempts, exponential backoff 2-10s).
**Fallback:** Returns `[]` on any exception.

### File: `backend/modules/merchants/service.py` (modified)

Updated `lookup_merchant()` return logic:

| Scenario | What's returned | LLM called? |
|----------|----------------|-------------|
| Merchant in DB with user selections | `[top_category]` (1 item) | No |
| Merchant in DB with only LLM suggestions | `[top_suggestion]` (1 item) | No |
| New merchant (not in DB) | `[cat1, cat2, cat3]` (3 items) | Yes |

The WhatsApp flow already handles both cases:
- 1 category → confirm or change prompt
- 3 categories → list picker

### File: `backend/core/config.py` (modified)

```python
gemini_api_key: str = ""  # Google AI Studio API key
```

Keep `openai_api_key` for now (no other code uses it, but removing is a separate cleanup).

### Dependencies

In `requirements.txt`:
- Add: `google-generativeai`
- Keep `openai` for now (remove in future cleanup)

## 3. Email Templates Folder

### Structure

```
docs/email-templates/
  banco-de-chile/
    transferencia-terceros.html
    compra-tarjeta-credito.txt
    pago-tarjeta-credito.html
```

Each file contains a representative sample with anonymized data. Not consumed by code — reference for extending parser patterns when adding new banks.

Content based on the 3 Banco de Chile screenshots provided by the user.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/modules/email/filter.py` | New | `is_financial_email()` pre-filter |
| `backend/jobs/tasks.py` | Modified | Add pre-filter call before parser |
| `backend/modules/merchants/llm.py` | Modified | Swap OpenAI → Gemini 2.0 Flash, 4→3 categories |
| `backend/modules/merchants/service.py` | Modified | Return 1 category for known merchants, 3 for new |
| `backend/core/config.py` | Modified | Add `gemini_api_key` |
| `requirements.txt` | Modified | Add `google-generativeai` |
| `docs/email-templates/banco-de-chile/` | New | 3 reference email templates |

## Testing

- Unit test `is_financial_email()` with financial and non-financial email samples
- Unit test Gemini LLM mock (same pattern as existing `test_merchant_llm.py`)
- Unit test `lookup_merchant()` returns 1 vs 3 categories based on DB state
- Integration: verify `process_email` skips non-financial emails via pre-filter
