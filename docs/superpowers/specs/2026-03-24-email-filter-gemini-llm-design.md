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
    "comprobante", "saldo", "retiro",
}
```

**Design rationale:**
- Bank-agnostic: no sender domain or bank name matching.
- Loose filter: any single keyword match passes. The regex parser (`parse_bank_email`) is the second, stricter filter.
- Hardcoded: financial terms in Spanish are stable. Can be extended later.
- Case-insensitive: all comparisons done on lowercased text.
- HTML-safe: bank emails are typically UTF-8 HTML. Keywords appear as plain text within the HTML, so keyword matching works without stripping tags. HTML entities (e.g., `&eacute;`) are unlikely in Chilean bank emails but if they become an issue, an HTML-to-text step can be added later.

### Integration in `process_email` (tasks.py)

There are two `for raw_email in emails:` loops in `process_email`:
1. **Lines 221-268:** TEMP WhatsApp notification loop (sends raw email metadata).
2. **Lines 271-349:** Real transaction processing loop.

The pre-filter goes in the **second loop** (line 271), before `parse_bank_email` at line 287. The TEMP loop continues to notify for all emails (it will be removed when the full pipeline is live).

```python
from modules.email.filter import is_financial_email

# Inside the SECOND emails loop (transaction processing, line ~271):
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
| ATM withdrawal | giro, cajero, retiro |

## 2. Gemini LLM Swap

### File: `backend/modules/merchants/llm.py` (modified)

**Before:** OpenAI `gpt-4o-mini`, returns 4 categories.
**After:** Google Gemini 2.0 Flash via `google-genai` SDK (newer async-capable SDK), returns 3 categories.

**SDK:** Use `google-genai` package (pip install `google-genai`, import as `from google import genai`). This is the newer SDK with native async support via `client.aio.models.generate_content()`, which is required since `_call_llm` is an async function running inside an ARQ worker.

```python
from google import genai
from core.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

# In the async function:
response = await client.aio.models.generate_content(
    model="gemini-2.0-flash",
    contents=f"Comercio: {merchant}",
    config=genai.types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=0.2,
        max_output_tokens=100,
    ),
)
raw = response.text  # Gemini returns .text directly
```

**Response parsing:** Gemini may wrap JSON in markdown code fences (`` ```json ... ``` ``). Strip code fences before `json.loads()`:
```python
raw = response.text.strip()
if raw.startswith("```"):
    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
data = json.loads(raw)
return data.get("categories", [])[:3]
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
| Merchant in DB with user selections | `[top_category]` (1 item) — `.limit(1)` instead of `.limit(4)` | No |
| Merchant in DB with only LLM suggestions | `[top_suggestion]` (1 item) — `merchant.llm_suggested_categories[:1]` | No |
| New merchant (not in DB) | `[cat1, cat2, cat3]` (3 items) | Yes |

**Code changes in `lookup_merchant()`:**
- Line 38: Change `.limit(4)` → `.limit(1)` for user selections query
- Line 42: Change `categories = merchant.llm_suggested_categories` → `categories = merchant.llm_suggested_categories[:1]`
- Line 45: LLM now returns 3 categories (handled by `llm.py` change)

**Redis cache:** The cache stores whatever list is returned. Existing cache entries with 4 categories will naturally expire within 24h (TTL). No migration needed — acceptable inconsistency during transition.

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
- Add: `google-genai` (the newer SDK with async support, NOT `google-generativeai`)
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
| `requirements.txt` | Modified | Add `google-genai` |
| `docs/email-templates/banco-de-chile/` | New | 3 reference email templates |

## Testing

| Test file | What it covers |
|-----------|---------------|
| `backend/tests/test_email_filter.py` (new) | `is_financial_email()` with financial and non-financial samples |
| `backend/tests/test_merchant_llm.py` (modified) | Gemini mock: returns 3 categories, graceful failure, code-fence stripping |
| `backend/tests/test_merchant_service.py` (modified) | `lookup_merchant()` returns 1 vs 3 categories based on DB state |
| `backend/tests/test_process_email.py` (new or extend existing) | `process_email` skips non-financial emails via pre-filter |
