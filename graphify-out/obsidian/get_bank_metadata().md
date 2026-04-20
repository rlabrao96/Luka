---
source_file: "backend/modules/email/bank_registry_service.py"
type: "code"
community: "Email Filter & Bank Registry"
location: "L149"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Email_Filter_&_Bank_Registry
---

# get_bank_metadata()

## Connections
- [[_extract_domain()]] - `calls` [EXTRACTED]
- [[_lookup_domain()]] - `calls` [EXTRACTED]
- [[bank_registry_service.py]] - `contains` [EXTRACTED]
- [[process_email()]] - `calls` [INFERRED]
- [[test_get_bank_metadata_db_fallback()]] - `calls` [INFERRED]
- [[test_get_bank_metadata_no_domain()]] - `calls` [INFERRED]
- [[test_get_bank_metadata_returns_full_dict()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Email_Filter_&_Bank_Registry