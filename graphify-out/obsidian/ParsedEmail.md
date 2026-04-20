---
source_file: "backend/modules/email/base.py"
type: "code"
community: "Email Parser Pipeline"
location: "L16"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# ParsedEmail

## Connections
- [[Detect credit card payment emails and return card description as merchant.]] - `uses` [INFERRED]
- [[Execute declarative JSON extraction templates — no dynamic code, only fixed tran]] - `uses` [INFERRED]
- [[Extract person name and direction from person-to-person payment emails.      Ret]] - `uses` [INFERRED]
- [[Full pipeline LLM returns None → falls back to regex → still returns a ParsedEm]] - `uses` [INFERRED]
- [[Full pipeline no template → LLM parses successfully → returns ParsedEmail with]] - `uses` [INFERRED]
- [[Infer transaction type from email text keywords.]] - `uses` [INFERRED]
- [[Integration tests for the three-layer parser pipeline.  Tests the interaction be]] - `uses` [INFERRED]
- [[LLM-powered email parser with confidence-based model waterfall.]] - `uses` [INFERRED]
- [[Layer 1 returns template result when template is found and succeeds.]] - `uses` [INFERRED]
- [[Layer 1→2 when execute_template returns None, falls through to LLM.]] - `uses` [INFERRED]
- [[Layer 2 falls through to LLM when no template_id in metadata.]] - `uses` [INFERRED]
- [[Layer 3 falls through to regex when LLM returns None.]] - `uses` [INFERRED]
- [[Parse a bank email alert (Chilean or US). Returns None if not a transaction emai]] - `uses` [INFERRED]
- [[Parse amount, returning (amount_int, currency).      US format $17.08 → (1708,]] - `uses` [INFERRED]
- [[Strip HTML tags, stylescript blocks, and collapse whitespace.]] - `uses` [INFERRED]
- [[Tests for the three-layer parser orchestrator in modules.email.parser.]] - `uses` [INFERRED]
- [[Three-layer parser template → LLM waterfall → regex fallback.      Returns (Par]] - `uses` [INFERRED]
- [[_extraction_to_parsed_email()]] - `calls` [INFERRED]
- [[_make_parsed_email()]] - `calls` [INFERRED]
- [[base.py]] - `contains` [EXTRACTED]
- [[execute_template()]] - `calls` [INFERRED]
- [[parse_bank_email_regex correctly parses the Banco de Chile sample without any mo]] - `uses` [INFERRED]
- [[parse_bank_email_regex()]] - `calls` [INFERRED]
- [[test_expense_email_stores_negative_amount_and_type()]] - `calls` [INFERRED]
- [[test_full_pipeline_llm_path()]] - `calls` [INFERRED]
- [[test_income_email_stores_positive_amount()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline