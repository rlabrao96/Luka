---
type: community
cohesion: 0.08
members: 35
---

# Email Template Executor

**Cohesion:** 0.08 - loosely connected
**Members:** 35 nodes

## Members
- [[CLP integer transform $1.250.000 → 1250000.]] - rationale - backend/tests/test_template_executor.py
- [[Detects transfer type via keywords_transfer.]] - rationale - backend/tests/test_template_executor.py
- [[Execute declarative JSON extraction templates — no dynamic code, only fixed tran]] - rationale - backend/modules/email/template_executor.py
- [[Falls back to utcnow when no date CSS selector matches.]] - rationale - backend/tests/test_template_executor.py
- [[Full extraction CSS selectors yield amount, merchant, date, and transaction typ]] - rationale - backend/tests/test_template_executor.py
- [[Returns None when amount selector finds nothing in the HTML.]] - rationale - backend/tests/test_template_executor.py
- [[Returns None when template has no selectors key.]] - rationale - backend/tests/test_template_executor.py
- [[Returns None when template selectors key is None.]] - rationale - backend/tests/test_template_executor.py
- [[Tests for the declarative JSON template executor.]] - rationale - backend/tests/test_template_executor.py
- [[USD cents transform $17.08 → 1708.]] - rationale - backend/tests/test_template_executor.py
- [[_detect_transaction_type()]] - code - backend/modules/email/template_executor.py
- [[_extract_field()]] - code - backend/modules/email/template_executor.py
- [[_transform_brl_centavos()]] - code - backend/modules/email/template_executor.py
- [[_transform_clp_integer()]] - code - backend/modules/email/template_executor.py
- [[_transform_cop_integer()]] - code - backend/modules/email/template_executor.py
- [[_transform_mxn_cents()]] - code - backend/modules/email/template_executor.py
- [[_transform_now()]] - code - backend/modules/email/template_executor.py
- [[_transform_parse_date_ddmmyyyy()]] - code - backend/modules/email/template_executor.py
- [[_transform_parse_date_ddmmyyyy_hhmm()]] - code - backend/modules/email/template_executor.py
- [[_transform_parse_date_iso()]] - code - backend/modules/email/template_executor.py
- [[_transform_parse_date_mmddyy()]] - code - backend/modules/email/template_executor.py
- [[_transform_pen_centimos()]] - code - backend/modules/email/template_executor.py
- [[_transform_strip()]] - code - backend/modules/email/template_executor.py
- [[_transform_usd_cents()]] - code - backend/modules/email/template_executor.py
- [[execute_template()]] - code - backend/modules/email/template_executor.py
- [[template_executor.py]] - code - backend/modules/email/template_executor.py
- [[test_clp_integer_transform()]] - code - backend/tests/test_template_executor.py
- [[test_date_fallback_to_utcnow_when_no_date_selector()]] - code - backend/tests/test_template_executor.py
- [[test_full_extraction_from_html()]] - code - backend/tests/test_template_executor.py
- [[test_returns_none_for_empty_template()]] - code - backend/tests/test_template_executor.py
- [[test_returns_none_for_invalid_template()]] - code - backend/tests/test_template_executor.py
- [[test_returns_none_when_amount_missing()]] - code - backend/tests/test_template_executor.py
- [[test_template_executor.py]] - code - backend/tests/test_template_executor.py
- [[test_transaction_type_transfer_keyword()]] - code - backend/tests/test_template_executor.py
- [[test_usd_cents_transform()]] - code - backend/tests/test_template_executor.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Email_Template_Executor
SORT file.name ASC
```

## Connections to other communities
- 4 edges to [[_COMMUNITY_Email Parser Pipeline]]
- 3 edges to [[_COMMUNITY_Backend Core & Infra]]

## Top bridge nodes
- [[execute_template()]] - degree 13, connects to 2 communities
- [[_extract_field()]] - degree 3, connects to 1 community
- [[_detect_transaction_type()]] - degree 3, connects to 1 community
- [[Execute declarative JSON extraction templates — no dynamic code, only fixed tran]] - degree 2, connects to 1 community