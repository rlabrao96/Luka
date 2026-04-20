---
type: community
cohesion: 0.04
members: 85
---

# Email Filter & Bank Registry

**Cohesion:** 0.04 - loosely connected
**Members:** 85 nodes

## Members
- [[Check if an email is likely a financial notification based on keyword matching.]] - rationale - backend/modules/email/filter.py
- [[Create a fake ORM BankRegistry-like object from a dict.]] - rationale - backend/tests/test_bank_registry_service.py
- [[DB session mock that returns None for all queries.]] - rationale - backend/tests/test_bank_registry_service.py
- [[DB session mock that returns a single ORM-like entry.]] - rationale - backend/tests/test_bank_registry_service.py
- [[DB-backed bank registry with Redis cache — replaces hardcoded BANK_SENDER_DOMAIN]] - rationale - backend/modules/email/bank_registry_service.py
- [[Detects financial emails with English keywords.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Detects financial emails with PortugueseBrazilian keywords.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Detects financial emails with Spanish keywords.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Extract the domain from a From header like 'Banco X noti@banco.cl'.]] - rationale - backend/modules/email/filter.py
- [[Falls back to DB when Redis misses, then caches the result.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Falls through to parent domain lookup for subdomains (e.g. noti.bancochile.cl).]] - rationale - backend/tests/test_bank_registry_service.py
- [[Infer a display-friendly bank name from the sender's email domain.]] - rationale - backend/modules/email/filter.py
- [[Redis mock that returns None (cache miss).]] - rationale - backend/tests/test_bank_registry_service.py
- [[Redis mock that returns a cached entry.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Return True if the sender's domain matches a known bank.]] - rationale - backend/modules/email/filter.py
- [[Return the matching BANK_SENDER_DOMAINS entry for a domain (exact or subdomain).]] - rationale - backend/modules/email/filter.py
- [[Returns 'Unknown' when domain is not found.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns 'Unknown' when sender string has no email address.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns False for clearly non-financial emails.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns False for push_only banks (not fully integrated).]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns False when domain not found in Redis or DB.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns False when sender string has no email address.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns None when sender string has no email address.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns True for a known active domain when Redis returns cached data.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns bank_name string for known sender.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Returns complete metadata dict for a known bank.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Tests for bank_registry_service — async DB-backed bank lookups with Redis cache.]] - rationale - backend/tests/test_bank_registry_service.py
- [[Verify the filter would accept a financial email in the pipeline.]] - rationale - backend/tests/test_process_email_filter.py
- [[Verify the filter would reject a non-financial email in the pipeline.]] - rationale - backend/tests/test_process_email_filter.py
- [[_extract_domain()]] - code - backend/modules/email/bank_registry_service.py
- [[_extract_domain()_1]] - code - backend/modules/email/filter.py
- [[_lookup_domain()]] - code - backend/modules/email/bank_registry_service.py
- [[_match_bank_domain()]] - code - backend/modules/email/filter.py
- [[bank_registry_service.py]] - code - backend/modules/email/bank_registry_service.py
- [[filter.py]] - code - backend/modules/email/filter.py
- [[get_bank_metadata()]] - code - backend/modules/email/bank_registry_service.py
- [[get_bank_name()]] - code - backend/modules/email/bank_registry_service.py
- [[get_bank_name()_1]] - code - backend/modules/email/filter.py
- [[is_bank_sender()]] - code - backend/modules/email/bank_registry_service.py
- [[is_bank_sender()_1]] - code - backend/modules/email/filter.py
- [[is_financial_email()]] - code - backend/modules/email/bank_registry_service.py
- [[is_financial_email()_1]] - code - backend/modules/email/filter.py
- [[make_bank_entry()]] - code - backend/tests/test_bank_registry_service.py
- [[make_db_miss()]] - code - backend/tests/test_bank_registry_service.py
- [[make_db_returning()]] - code - backend/tests/test_bank_registry_service.py
- [[make_redis_hit()]] - code - backend/tests/test_bank_registry_service.py
- [[make_redis_miss()]] - code - backend/tests/test_bank_registry_service.py
- [[test_bank_registry_service.py]] - code - backend/tests/test_bank_registry_service.py
- [[test_bank_sender_exact_domain()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_fintech()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_rejects_empty()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_rejects_gmail()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_rejects_unknown()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_subdomain()]] - code - backend/tests/test_email_filter.py
- [[test_bank_sender_with_display_name()]] - code - backend/tests/test_email_filter.py
- [[test_case_insensitive()]] - code - backend/tests/test_email_filter.py
- [[test_email_filter.py]] - code - backend/tests/test_email_filter.py
- [[test_filter_accepts_financial_in_pipeline_context()]] - code - backend/tests/test_process_email_filter.py
- [[test_filter_rejects_non_financial_in_pipeline_context()]] - code - backend/tests/test_process_email_filter.py
- [[test_get_bank_metadata_db_fallback()]] - code - backend/tests/test_bank_registry_service.py
- [[test_get_bank_metadata_no_domain()]] - code - backend/tests/test_bank_registry_service.py
- [[test_get_bank_metadata_returns_full_dict()]] - code - backend/tests/test_bank_registry_service.py
- [[test_get_bank_name_no_domain()]] - code - backend/tests/test_bank_registry_service.py
- [[test_get_bank_name_returns_display_name()]] - code - backend/tests/test_bank_registry_service.py
- [[test_get_bank_name_unknown_returns_unknown()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_bank_sender_no_domain()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_bank_sender_push_only_returns_false()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_bank_sender_redis_cache_hit_active()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_bank_sender_subdomain_db_lookup()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_bank_sender_unknown_domain_false()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_financial_email_english_keywords()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_financial_email_portuguese_keywords()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_financial_email_rejects_non_financial()]] - code - backend/tests/test_bank_registry_service.py
- [[test_is_financial_email_spanish_keywords()]] - code - backend/tests/test_bank_registry_service.py
- [[test_matches_atm_withdrawal()]] - code - backend/tests/test_email_filter.py
- [[test_matches_credit_card_payment()]] - code - backend/tests/test_email_filter.py
- [[test_matches_credit_card_purchase()]] - code - backend/tests/test_email_filter.py
- [[test_matches_deposit()]] - code - backend/tests/test_email_filter.py
- [[test_matches_keyword_in_sender_only()]] - code - backend/tests/test_email_filter.py
- [[test_matches_pac_pat()]] - code - backend/tests/test_email_filter.py
- [[test_matches_transfer_email()]] - code - backend/tests/test_email_filter.py
- [[test_process_email_filter.py]] - code - backend/tests/test_process_email_filter.py
- [[test_rejects_newsletter()]] - code - backend/tests/test_email_filter.py
- [[test_rejects_personal_email()]] - code - backend/tests/test_email_filter.py
- [[test_rejects_promotional_bank_email_without_keywords()]] - code - backend/tests/test_email_filter.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Email_Filter_&_Bank_Registry
SORT file.name ASC
```

## Connections to other communities
- 5 edges to [[_COMMUNITY_Backend Core & Infra]]
- 2 edges to [[_COMMUNITY_Email Parser Pipeline]]

## Top bridge nodes
- [[is_financial_email()_1]] - degree 22, connects to 2 communities
- [[get_bank_name()_1]] - degree 8, connects to 1 community
- [[get_bank_metadata()]] - degree 7, connects to 1 community
- [[_lookup_domain()]] - degree 5, connects to 1 community
- [[DB-backed bank registry with Redis cache — replaces hardcoded BANK_SENDER_DOMAIN]] - degree 2, connects to 1 community