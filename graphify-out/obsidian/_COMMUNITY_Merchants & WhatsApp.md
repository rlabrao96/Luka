---
type: community
cohesion: 0.03
members: 150
---

# Merchants & WhatsApp

**Cohesion:** 0.03 - loosely connected
**Members:** 150 nodes

## Members
- [[Called when a user selects a final category via WhatsApp. Trains the dataset.]] - rationale - backend/modules/merchants/service.py
- [[Format transaction amount for WhatsApp display using per-currency rules.]] - rationale - backend/modules/whatsapp/sender.py
- [[If no active_edit key exists and message is unparseable, handler silently return]] - rationale - backend/tests/test_whatsapp_handler.py
- [[Known merchant with user selections returns only top 1 category.]] - rationale - backend/tests/test_merchant_service.py
- [[Look up merchant categories Redis L1 → DB L2 → LLM fallback.     Returns 1 cate]] - rationale - backend/modules/merchants/service.py
- [[Look up transaction ID from a WhatsApp message ID. Returns None if expiredunkno]] - rationale - backend/modules/whatsapp/session.py
- [[Map a WhatsApp message ID to a transaction ID so replies can find the right sess]] - rationale - backend/modules/whatsapp/session.py
- [[Mark a phone as being in free-text edit mode for a given transaction.]] - rationale - backend/modules/whatsapp/session.py
- [[Merchant in DB with only LLM suggestions returns top 1 suggestion.]] - rationale - backend/tests/test_merchant_service.py
- [[MerchantCategorySelection]] - code - backend/modules/merchants/models.py
- [[Non-numeric amount reply sends error text and returns without DB update.]] - rationale - backend/tests/test_whatsapp_handler.py
- [[Normalize a raw merchant name from a Chilean bank email.     COMPRA LIDER PROVI]] - rationale - backend/modules/merchants/normalizer.py
- [[Remove active-edit marker after the edit is processed.]] - rationale - backend/modules/whatsapp/session.py
- [[Return the transaction_id currently awaiting a free-text edit reply, or None.]] - rationale - backend/modules/whatsapp/session.py
- [[Return the user's category list ranked for this specific merchant       1. Cate]] - rationale - backend/modules/merchants/service.py
- [[Send a 2-button message for editing merchant name or amount. Returns message ID.]] - rationale - backend/modules/whatsapp/sender.py
- [[Send a simple text message. Returns message ID.]] - rationale - backend/modules/whatsapp/sender.py
- [[Send a text message with a verification PIN. Raises on failure.]] - rationale - backend/modules/whatsapp/sender.py
- [[Send expense alert with split buttons (personalsharededit). Returns message ID]] - rationale - backend/modules/whatsapp/sender.py
- [[Send informational transfer alert (no split buttons). Returns message ID.]] - rationale - backend/modules/whatsapp/sender.py
- [[Send list message with category options. Returns WhatsApp message ID.]] - rationale - backend/modules/whatsapp/sender.py
- [[Strip leading + so session keys are consistent regardless of format.]] - rationale - backend/modules/whatsapp/session.py
- [[Valid 'gasto N merchant' with no active edit creates a transaction and sends ale]] - rationale - backend/tests/test_whatsapp_handler.py
- [[Valid trigger but phone not found in DB — silently returns without creating anyt]] - rationale - backend/tests/test_whatsapp_handler.py
- [[When step is awaiting_new_amount, parses int and updates txn.amount.]] - rationale - backend/tests/test_whatsapp_handler.py
- [[When step is awaiting_new_merchant, updates raw_merchant_name and re-sends alert]] - rationale - backend/tests/test_whatsapp_handler.py
- [[_active_edit_key()]] - code - backend/modules/whatsapp/session.py
- [[_detect_currency()]] - code - backend/modules/whatsapp/handler.py
- [[_format_amount()]] - code - backend/modules/whatsapp/sender.py
- [[_get_user_and_household_by_phone()]] - code - backend/modules/whatsapp/handler.py
- [[_handle_manual_expense_trigger()]] - code - backend/modules/whatsapp/handler.py
- [[_headers()]] - code - backend/modules/whatsapp/sender.py
- [[_make_redis()]] - code - backend/tests/test_whatsapp_handler.py
- [[_normalize_phone()]] - code - backend/modules/whatsapp/session.py
- [[_parse_amount()_1]] - code - backend/modules/whatsapp/handler.py
- [[_save_split()]] - code - backend/modules/whatsapp/handler.py
- [[_session_key()]] - code - backend/modules/whatsapp/session.py
- [[_url()]] - code - backend/modules/whatsapp/sender.py
- [[_verify_signature()]] - code - backend/modules/whatsapp/router.py
- [[clear_active_edit()]] - code - backend/modules/whatsapp/session.py
- [[clear_session()]] - code - backend/modules/whatsapp/session.py
- [[get_active_edit_transaction_id()]] - code - backend/modules/whatsapp/session.py
- [[get_session()]] - code - backend/modules/whatsapp/session.py
- [[get_transaction_id_by_msgid()]] - code - backend/modules/whatsapp/session.py
- [[get_user_ranked_categories()]] - code - backend/modules/merchants/service.py
- [[handle_button_click()]] - code - backend/modules/whatsapp/handler.py
- [[handle_list_selection()]] - code - backend/modules/whatsapp/handler.py
- [[handle_text_message()]] - code - backend/modules/whatsapp/handler.py
- [[handler.py]] - code - backend/modules/whatsapp/handler.py
- [[lookup_merchant()]] - code - backend/modules/merchants/service.py
- [[main()_6]] - code - backend/scripts/seed_fake_transactions.py
- [[main()_7]] - code - backend/scripts/test_whatsapp_flow.py
- [[models.py_4]] - code - backend/modules/merchants/models.py
- [[normalize_merchant()]] - code - backend/modules/merchants/normalizer.py
- [[normalizer.py]] - code - backend/modules/merchants/normalizer.py
- [[parse_manual_expense()]] - code - backend/modules/whatsapp/handler.py
- [[record_category_selection()]] - code - backend/modules/merchants/service.py
- [[router.py_13]] - code - backend/modules/whatsapp/router.py
- [[save_active_edit()]] - code - backend/modules/whatsapp/session.py
- [[save_msgid()]] - code - backend/modules/whatsapp/session.py
- [[save_session()]] - code - backend/modules/whatsapp/session.py
- [[seed_fake_transactions.py]] - code - backend/scripts/seed_fake_transactions.py
- [[send_category_list()]] - code - backend/modules/whatsapp/sender.py
- [[send_edit_options must produce a button message with edit_merchant and edit_amou]] - rationale - backend/tests/test_whatsapp_sender.py
- [[send_edit_options()]] - code - backend/modules/whatsapp/sender.py
- [[send_expense_alert()]] - code - backend/modules/whatsapp/sender.py
- [[send_test_transaction()]] - code - backend/scripts/test_whatsapp_flow.py
- [[send_text()]] - code - backend/modules/whatsapp/sender.py
- [[send_transfer_alert()]] - code - backend/modules/whatsapp/sender.py
- [[send_verification_pin()]] - code - backend/modules/whatsapp/sender.py
- [[sender.py]] - code - backend/modules/whatsapp/sender.py
- [[service.py_4]] - code - backend/modules/merchants/service.py
- [[session.py]] - code - backend/modules/whatsapp/session.py
- [[test_calls_llm_on_cache_and_db_miss()]] - code - backend/tests/test_merchant_service.py
- [[test_clear_active_edit_deletes_correct_key()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_clear_session_deletes_correct_key()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_collapses_whitespace()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_format_ars()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_brl()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_clp()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_cop()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_crc()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_mxn()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_pen()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_pyg()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_unknown_falls_back()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_format_usd()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_get_active_edit_returns_none_when_missing()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_get_msgid_returns_none_when_missing()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_get_session_returns_none_when_missing()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_handle_text_message_invalid_amount_sends_error()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handle_text_message_manual_trigger_creates_transaction()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handle_text_message_manual_trigger_unknown_phone_ignores()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handle_text_message_no_active_edit_ignores()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handle_text_message_updates_amount()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handle_text_message_updates_merchant()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_handles_no_prefix()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_merchant_normalizer.py]] - code - backend/tests/test_merchant_normalizer.py
- [[test_merchant_service.py]] - code - backend/tests/test_merchant_service.py
- [[test_parse_amount_clp_comma_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_clp_dot_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_clp_million()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_clp_small()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_clp_whole()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_dollar_sign_stripped()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_invalid()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_comma_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_decimal_one()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_decimal_two()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_dot_three_digits_is_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_large()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_amount_usd_whole()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_chile_keyword_override()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_comma_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_dot_thousands()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_multi_word()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_override_from_usd()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_with_gasto()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_clp_without_keyword()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_dolares_keyword_override()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_empty_returns_none()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_expense_of_in()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_gaste_en()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_gasto_de_en()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_no_amount_returns_none()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_no_merchant_returns_none()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_pesos_keyword_override()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_spent_at()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_usd_decimal()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_usd_fractional()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_usd_override_from_clp()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_parse_manual_expense_usd_whole()]] - code - backend/tests/test_whatsapp_handler.py
- [[test_returns_cached_categories_on_redis_hit()]] - code - backend/tests/test_merchant_service.py
- [[test_returns_single_category_for_known_merchant()]] - code - backend/tests/test_merchant_service.py
- [[test_returns_single_llm_suggestion_for_merchant_without_selections()]] - code - backend/tests/test_merchant_service.py
- [[test_same_result_for_location_variants()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_save_and_retrieve_active_edit()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_save_and_retrieve_msgid()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_save_and_retrieve_session()]] - code - backend/tests/test_whatsapp_webhook.py
- [[test_send_category_list_calls_meta_api()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_send_edit_options_sends_two_buttons()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_send_personal_expense_alert_calls_meta_api()]] - code - backend/tests/test_whatsapp_sender.py
- [[test_strips_compra_prefix()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_strips_location_suffix()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_strips_pago_prefix()]] - code - backend/tests/test_merchant_normalizer.py
- [[test_whatsapp_flow.py]] - code - backend/scripts/test_whatsapp_flow.py
- [[test_whatsapp_handler.py]] - code - backend/tests/test_whatsapp_handler.py
- [[test_whatsapp_sender.py]] - code - backend/tests/test_whatsapp_sender.py
- [[test_whatsapp_webhook.py]] - code - backend/tests/test_whatsapp_webhook.py
- [[whatsapp_webhook()]] - code - backend/modules/whatsapp/router.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Merchants_&_WhatsApp
SORT file.name ASC
```

## Connections to other communities
- 27 edges to [[_COMMUNITY_Backend Core & Infra]]
- 15 edges to [[_COMMUNITY_DB, Accounts & Allocation]]
- 15 edges to [[_COMMUNITY_Luka Connect & Merchant Review]]
- 3 edges to [[_COMMUNITY_Email Parser Pipeline]]
- 3 edges to [[_COMMUNITY_User Settings & Notifications]]
- 1 edge to [[_COMMUNITY_Transactions API]]
- 1 edge to [[_COMMUNITY_Plaid & Subscriptions]]

## Top bridge nodes
- [[lookup_merchant()]] - degree 16, connects to 3 communities
- [[_parse_amount()_1]] - degree 18, connects to 2 communities
- [[handle_button_click()]] - degree 14, connects to 2 communities
- [[normalize_merchant()]] - degree 13, connects to 2 communities
- [[_handle_manual_expense_trigger()]] - degree 11, connects to 2 communities