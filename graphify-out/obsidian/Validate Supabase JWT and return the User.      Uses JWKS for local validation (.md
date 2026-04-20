---
source_file: "backend/core/security.py"
type: "rationale"
community: "Backend Core & Infra"
location: "L87"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Backend_Core_&_Infra
---

# Validate Supabase JWT and return the User.      Uses JWKS for local validation (

## Connections
- [[User]] - `uses` [INFERRED]
- [[get_current_user()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Backend_Core_&_Infra