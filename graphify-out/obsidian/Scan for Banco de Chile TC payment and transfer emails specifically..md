---
source_file: "backend/scripts/scan_tc_payments.py"
type: "rationale"
community: "Email Parser Pipeline"
location: "L1"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Email_Parser_Pipeline
---

# Scan for Banco de Chile TC payment and transfer emails specifically.

## Connections
- [[User]] - `uses` [INFERRED]
- [[scan_tc_payments.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Email_Parser_Pipeline