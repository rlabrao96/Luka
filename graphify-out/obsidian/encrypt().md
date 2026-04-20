---
source_file: "backend/modules/bank_connect/encryption.py"
type: "code"
community: "Backend Core & Infra"
location: "L13"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Backend_Core_&_Infra
---

# encrypt()

## Connections
- [[Encrypt plaintext with AES-256-GCM. Returns (ciphertext, iv).]] - `rationale_for` [EXTRACTED]
- [[_get_key()]] - `calls` [EXTRACTED]
- [[encrypt_token()]] - `calls` [INFERRED]
- [[encryption.py_1]] - `contains` [EXTRACTED]
- [[store_credentials()]] - `calls` [INFERRED]
- [[test_different_plaintexts_produce_different_ciphertexts()]] - `calls` [INFERRED]
- [[test_encrypt_decrypt_roundtrip()]] - `calls` [INFERRED]
- [[test_wrong_iv_fails()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Backend_Core_&_Infra