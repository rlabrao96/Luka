---
source_file: "backend/modules/email/models.py"
type: "code"
community: "Email Parser Pipeline"
location: "L38"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Parser_Pipeline
---

# EmailTemplate

## Connections
- [[ANY amount mismatch in shadow validation triggers retirement.]] - `uses` [INFERRED]
- [[Autonomous Template Agent — discovers, generates, validates, promotes, and retir]] - `uses` [INFERRED]
- [[Base]] - `uses` [INFERRED]
- [[Base_1]] - `inherits` [EXTRACTED]
- [[Detect credit card payment emails and return card description as merchant.]] - `uses` [INFERRED]
- [[Extract person name and direction from person-to-person payment emails.      Ret]] - `uses` [INFERRED]
- [[Find banks with enough LLM-parsed emails but no active template.]] - `uses` [INFERRED]
- [[Infer transaction type from email text keywords.]] - `uses` [INFERRED]
- [[Main entry point — runs daily as ARQ cron job.]] - `uses` [INFERRED]
- [[Parse a bank email alert (Chilean or US). Returns None if not a transaction emai]] - `uses` [INFERRED]
- [[Parse amount, returning (amount_int, currency).      US format $17.08 → (1708,]] - `uses` [INFERRED]
- [[Shadow validate active templates compare template vs LLM on a sample.]] - `uses` [INFERRED]
- [[Strip HTML tags, stylescript blocks, and collapse whitespace.]] - `uses` [INFERRED]
- [[Three-layer parser template → LLM waterfall → regex fallback.      Returns (Par]] - `uses` [INFERRED]
- [[Use LLM to generate a declarative extraction template from samples.]] - `uses` [INFERRED]
- [[Validate template vs LLM ground truth. 100% amount match, 95% merchant match req]] - `uses` [INFERRED]
- [[models.py_10]] - `contains` [EXTRACTED]
- [[run_template_agent()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Parser_Pipeline