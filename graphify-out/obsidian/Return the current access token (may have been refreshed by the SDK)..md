---
source_file: "backend/modules/email/gmail.py"
type: "rationale"
community: "Backend Core & Infra"
location: "L30"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Backend_Core_&_Infra
---

# Return the current access token (may have been refreshed by the SDK).

## Connections
- [[.get_current_token()]] - `rationale_for` [EXTRACTED]
- [[EmailProvider_1]] - `uses` [INFERRED]
- [[RawEmail]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Backend_Core_&_Infra