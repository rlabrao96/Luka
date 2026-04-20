---
type: community
cohesion: 0.12
members: 25
---

# Bank Connect Mapper

**Cohesion:** 0.12 - loosely connected
**Members:** 25 nodes

## Members
- [[NOTE person-to-person transfers (Traspaso AName) are NOT in this list — th]] - rationale - backend/modules/bank_connect/mapper.py
- [[Generate a dedup key from movement fields.]] - rationale - backend/modules/bank_connect/mapper.py
- [[Map a raw Luka Connect movement to transaction fields.]] - rationale - backend/modules/bank_connect/mapper.py
- [[Normalize description for dedup comparison.]] - rationale - backend/modules/bank_connect/mapper.py
- [[Parse date string and optional HHMM time into a timezone-aware datetime.      S]] - rationale - backend/modules/bank_connect/mapper.py
- [[Return True if the movement description matches a known inter-account pattern.]] - rationale - backend/modules/bank_connect/mapper.py
- [[dedup_key()]] - code - backend/modules/bank_connect/mapper.py
- [[is_inter_account_transfer()]] - code - backend/modules/bank_connect/mapper.py
- [[map_movement_to_transaction()]] - code - backend/modules/bank_connect/mapper.py
- [[mapper.py]] - code - backend/modules/bank_connect/mapper.py
- [[normalize_description()]] - code - backend/modules/bank_connect/mapper.py
- [[parse_movement_date()]] - code - backend/modules/bank_connect/mapper.py
- [[test_bank_connect_mapper.py]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_dedup_key_deterministic()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_dedup_key_different_inputs()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_is_inter_account_transfer_cc_payment()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_is_inter_account_transfer_own_account()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_is_inter_account_transfer_person_not_transfer()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_map_movement_basic()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_map_movement_cc_payment_is_transfer()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_map_movement_income()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_map_movement_person_transfer_is_expense()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_normalize_description()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_parse_movement_date_with_time()]] - code - backend/tests/test_bank_connect_mapper.py
- [[test_parse_movement_date_without_time()]] - code - backend/tests/test_bank_connect_mapper.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Bank_Connect_Mapper
SORT file.name ASC
```

## Connections to other communities
- 2 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 1 edge to [[_COMMUNITY_Backend Core & Infra]]

## Top bridge nodes
- [[map_movement_to_transaction()]] - degree 10, connects to 2 communities
- [[parse_movement_date()]] - degree 6, connects to 1 community