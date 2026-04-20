---
source_file: "backend/modules/email/filter.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L248"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Filter_&_Bank_Registry
---

# get_bank_name()

## Connections
- [[GET()]] - `calls` [INFERRED]
- [[Infer a display-friendly bank name from the sender's email domain.]] - `rationale_for` [EXTRACTED]
- [[_extract_domain()_1]] - `calls` [EXTRACTED]
- [[_match_bank_domain()]] - `calls` [EXTRACTED]
- [[filter.py]] - `contains` [EXTRACTED]
- [[test_get_bank_name_no_domain()]] - `calls` [INFERRED]
- [[test_get_bank_name_returns_display_name()]] - `calls` [INFERRED]
- [[test_get_bank_name_unknown_returns_unknown()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Filter_&_Bank_Registry