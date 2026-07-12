# Luka Ultrareview — Full Tech-Debt & Money-Math Audit
**Date:** 2026-07-11
**Agents:** Logic-A (personal ledger math), Logic-B (trips/budgets/household math), Security, Performance, Style/Debt, Frontend — all six completed.
**Scope:** ~60 files / ~22k lines across `backend/modules/{transactions,trips,budgets,households,reconciliation,plaid,bank_connect,currencies,auth}`, `backend/jobs/`, and the money-facing frontend (dashboard, budgets, viajes, pending/reconciliation components).

---

## Executive summary

1. **The settlement math for couples is broken in the most common case.** If one partner paid everything this month, `get_settlement` returns *no settlement at all* (members built from a GROUP BY over spenders only). And with custom ratios, the 70/30 split is assigned by who-spent-more, not by member identity — the direction of who owes whom can flip month to month. (LB-1, LB-2 — both critical)
2. **Two silent double/vanish-money bugs in the ledger core.** Every Plaid pending→settled rotation can leave a transaction with two split rows, double-counting it in the monthly summary (LA-1). Every wallet-funded purchase (Venmo/PayPal) vanishes from spend totals because the "canonical expense" leg gets stamped with `transfer_pair_id` (LA-2).
3. **There is no single answer to "which rows count toward totals."** Dashboard summary, budgets v2, household contributions, and the frontend each exclude a *different* subset of transfer/refund/reimbursement pairs — so the app's own screens disagree with each other on income and spend. This is the single biggest structural math debt. (LA-2, LB-4/5/6, FE-1, plus agent cross-notes)
4. **Minor-units vs major-units convention is enforced by convention, not code.** Plaid and email scale to integer minor units; the bank-connect mapper doesn't (LA-7); trip suggestions emit raw stored units while trip expenses validate major units (LB-16); the frontend renders the same budget fields with two conflicting ÷100 conventions (FE-3). Any drift is a silent 100× error.
5. **Zero-decimal LATAM currencies (CLP/COP) are second-class in trips/budgets math:** 2-decimal hardcoded rounding produces un-payable fractional-peso shares and settlements (LB-8/9/17), and the duplicated `_ZERO_DECIMAL_CURRENCIES` set is wrong for CLF (4 dp) and questionable for COP (ST-4, LB-19).
6. **Ops-level risks:** the Luka Connect webhook is fully unauthenticated — fabricated bank movements can be injected (SEC-1); removed trip attendees retain full write access to the ledger (SEC-2); the subscriptions-cache cron outgrows its 60s fast-worker budget and silently strands users on stale data (PF-1); email dedup keys are set *before* processing, so a crash mid-batch permanently drops transactions (PF-10, LA-8).

**Verified-correct highlights (from Logic-B):** trip balance netting, smart-settle termination and n−1 bound, split remainder allocation (2-dp currencies), trip-stub isolation from budgets, Sankey flow conservation, forecast guards. The core trips design is sound — the bugs are at the edges.

---

## Findings by severity

Tags: **[LA]** Logic ledger · **[LB]** Logic group-math · **[SEC]** Security · **[PF]** Performance · **[ST]** Style/debt · **[FE]** Frontend

### CRITICAL

**C1 [LA-1] Plaid pending→settled swap creates duplicate split rows → double-counted money**
`modules/plaid/sync.py:317-323`. The removed path re-links the old transaction's splits onto the replacement, which already got its own default split in the added path of the same run. No unique constraint on `transaction_splits.transaction_id`. `get_monthly_summary` JOINs splits then SUMs amounts — the transaction counts twice. Fires on every pending rotation. Fix: delete the replacement's existing split before re-linking; add a unique constraint (see also C-adjacent LB-21).

**C2 [LA-2] Wallet-funded purchases vanish from spend totals**
`modules/reconciliation/wallets.py:133-146`. On a wallet-funding match, `transfer_pair_id` is stamped on **both** legs but only the bank leg is re-typed `transfer`; every aggregator excludes rows with `transfer_pair_id IS NOT NULL`, so the wallet leg — the documented canonical expense — disappears from summary/category totals. Budgets v2 still counts it → views disagree. Fix: separate link column, or exclude by pair-id only when `transaction_type='transfer'`.

**C3 [LB-1] Couple settlement returns nothing when one partner paid everything**
`modules/households/service.py:553-570` + `:477`. Member list is built from a GROUP BY over shared-expense transactions, so zero-spend members are missing; `len(members) <= 1` → `[]`. "A paid 300.000 CLP, B paid nothing" yields no settlement. Tests hand-build member lists the SQL can never produce. Fix: source members from `household_members` (active, joined_at ASC) with LEFT JOIN totals COALESCEd to 0.

**C4 [LB-2] Custom split-ratio assigned by spend order, not member identity**
`modules/households/service.py:567` (ORDER BY total DESC) vs `budgets/v2_service.py:159-199` (joined_at ASC). With ratio [70,30], whoever spent more this month gets the 70% obligation; settlement direction/amount flips month to month and disagrees with the budget's share math. Fix: canonicalize on `joined_at ASC` everywhere (falls out of the C3 rewrite).

**C5 [PF-1] Subscriptions-cache cron exceeds fast-worker timeout → stale data forever**
`jobs/tasks.py:694`, `worker.py:47`. Recomputes all users in one 60s-capped job with `sleep(2)` between batches; at ~300 users ARQ kills it mid-run and users after the cutoff keep a stale cache (~10-day cron). Fix: fan out one job per user on the slow worker.

### HIGH

**H1 [SEC-1] Luka Connect webhook is unauthenticated** — `bank_connect/router.py:178`. Anyone with a leaked job UUID can inject fabricated bank movements (creates real transactions, deletes matched email rows). Fix: require `X-API-Key`/HMAC on the inbound callback; 400 on malformed UUID.

**H2 [SEC-2] Removed/departed trip attendees retain full write access** — `trips/service.py:90` (used by router.py:420-474). `_is_any_member` never filters `left_at`; a kicked attendee can still edit/delete expenses and insert settlements. Fix: gate all mutations on `_is_active_member`; also validate the payer's `left_at` in `create_expense`.

**H3 [LB-3 = SEC-4] `update_expense` accepts a currency change with no base-currency validation** — `trips/service.py:764-765`. Found independently by two agents. PATCH `{currency:"USD"}` on a CLP trip corrupts everyone's balances (CLP+USD summed as one unit). Fix: re-apply the `currency_must_match_trip_base` 422 in update.

**H4 [LB-4] Budgets/income/contributions never exclude `refund_pair_id`** — `budgets/v2_service.py:214-228, 255-284, 317-352, 408-448, 1168-1182`; `budgets/service.py:40-53`; `households/contribution_service.py:103-113, 203-217`. A charged-then-refunded purchase inflates mtd_spent, risk stats, burn, AND income — budget page disagrees with dashboard on both sides. Fix: add `refund_pair_id IS NULL` everywhere reimbursements are already excluded.

**H5 [LB-5] Household contribution summary mixes income into "paid" totals** — `households/service.py:374-395`. Sums raw signed amounts with no `transaction_type` filter; any member income makes shared_paid nonsense. Fix: filter `transaction_type='expense'`, sum ABS, exclude refund/reimbursement pairs.

**H6 [LB-6] Reimbursement inflows count as household income** — `households/contribution_service.py:103-110, 203-216`. Personal-view income excludes reimbursements (v2_service.py:1177) but household view doesn't — same user, two different income totals. Fix: same exclusions in both queries.

**H7 [LA-3] Plaid "modified" path overwrites user edits and skips enrichment** — `plaid/sync.py:280-282`. User renames revert on any tip adjustment; Zelle-person extraction bypassed; `transaction_type` not re-derived on sign flip. Fix: honor `user_edited_fields`, route through `map_plaid_transaction`'s name resolution.

**H8 [LA-4] Credit-suggestion notifications show minor units as major** — `reconciliation/credit_suggestions.py:293-298`. A $27.43 credit renders "USD 2743.00". Fix: currency-aware formatting via a shared minor-units helper.

**H9 [LA-5] Tier-2 email dedup drops legitimate transactions** — `transactions/service.py:1075-1089`. Same abs(amount)+currency from a *different bank* within 24h = "duplicate", no merchant check. Two distinct 10.000 CLP purchases same day → second one permanently lost for email-only users. Fix: require merchant similarity (reuse dedup.py helpers).

**H10 [LA-6] Connect-sync email match has no currency or sign filter** — `bank_connect/router.py:392-404`. USD 50.00 (stored 5000) collides with CLP 5.000 (stored 5000); income can consolidate into an expense. Fix: match signed amount + currency, mirroring `dedup._find_single_match`.

**H11 [LA-7] Bank-connect mapper stores raw amounts, no minor-unit scaling, hardcoded CLP fallback** — `bank_connect/mapper.py:65-93`. MXN 123.45 would store as 123.45 (not 12345) → breaks cross-source matching, renders as 1.23. Latent but violates never-Chile-only. Fix: shared `to_minor_units(amount, currency)`; make currency required.

**H12 [PF-2] Sync Plaid SDK calls block the slow-worker event loop** — `plaid/sync.py:114` → `plaid/service.py:61`. One slow institution stalls all 5 concurrent slow jobs. Fix: `asyncio.to_thread(...)` on all Plaid SDK call sites.

**H13 [PF-3] Plaid initial sync issues 4,000–7,000 sequential queries** — `plaid/sync.py:183-267`. Per-row dedup SELECT + flush + split + email-match queries. Fix: batch `IN` pre-loads, flush per page, pre-check for pending emails once.

**H14 [PF-4] Trip suggestions load every trip expense platform-wide** — `trips/service.py:1196-1201`. Unscoped `linked_q` = full-table scan into a Python set per request. Fix: correlated NOT EXISTS scoped to caller.

**H15 [PF-5] Budget dashboard loads full ORM rows twice for what are GROUP BY sums** — `budgets/v2_service.py:234-286, 396-448, 1228-1248`. ~1,600 wide rows per load on the primary screen. Fix: SQL aggregation (~20 rows).

**H16 [ST-1] `budgets/v2_service.py` is a 1,825-line god-module** — four 220–350-line functions mixing SQL, allocation math, Sankey building, drilldown. Fix: split into `v2_queries.py` / `v2_sankey.py` / thin orchestrators — imports only, no behavior change.

**H17 [ST-2] 16+ one-off debug/repair scripts, 9 untracked, violating hygiene rules** — `backend/scripts/`. User-specific one-time fixes that will rot; re-running one against prod is a real risk. Fix: delete the 16 listed one-offs; keep the operational set (backfills, seeds, training, webhook listener).

**H18 [ST-3] `service.list_trips` is dead in production but still tested** — `trips/service.py:185-210` vs `router.py:174-205`. Router reimplements it; the dead copy hardcodes balance $0 and the tests exercise the copy users never hit. Fix: delete the service version, single implementation, retarget tests.

**H19 [FE-1] Dashboard client totals don't exclude reimbursement groups** — `app/(dashboard)/page.tsx:92`. A reimbursed $500 dinner shows +$500 income, $500 expense, $500 in Restaurantes — disagreeing with server totals. Fix: `&& !t.reimbursement_group_id`.

**H20 [FE-2] Category caps compared across currencies** — `BudgetBars.tsx:50` + `useBudget.ts:26-33`. `budgetMap` keyed by category only; USD 200 cap vs CLP 195.000 spend = 97.500% bar. Fix: filter budgets by selected currency.

**H21 [FE-3] Budget fields rendered with two conflicting unit conventions** — `BudgetBars.tsx:19-24,62,90` vs `RiskAlertBand.tsx:27-28` + `CategoryCapsEditor.tsx:111,202`. For USD/BRL/MXN/PEN one surface is off by exactly 100×; CLP masks it. Fix: pick one wire convention (recommend stored/minor units), convert on save, `formatStoredAmount` everywhere. **Verify backend serializer first.**

**H22 [FE-4] Cap edits never refresh the dashboard** — `CategoryCapsEditor.tsx:118` invalidates `["category-budgets"]` but the dashboard reads `["categoryBudgets"]`. Fix: one exported query-key constant.

**H23 [FE-5] Trip mutations never invalidate the trips-list balance** — `useTrips.ts:369-373, 439, 462-465, 505, 645-648`. After adding an expense, the trips index shows a stale `your_net_balance` for up to 5 min. Fix: also invalidate the exact `["trips"]` key in `onSettled`.

### MEDIUM

**M1 [LA-8] Email idempotency marker committed before enqueue** — `transactions/idempotency.py:20-22` + `email/router.py:46-57`. Redis blip after marking = email dropped forever (permanent on Outlook). Fix: mark only after successful enqueue; `ON CONFLICT DO NOTHING` for the race.

**M2 [PF-10, related] Email batch job sets Redis dedup key before parsing** — `jobs/tasks.py:176-534` (worker fast, 60s). A 4–5-email Gemini-waterfall batch exceeds 60s; ARQ kills it; keys already set → transactions lost. Fix: fan out one job per email; set key after success.

**M3 [LA-9] Plaid removed-path replacement requires exact amount** — `plaid/sync.py:299-315`. Tip adjustments break the link; enrichment/splits/trip-links dropped. Fix: use Plaid's `pending_transaction_id` first, then ±20% window.

**M4 [LA-10] Reimbursement netting tolerance is 1/100 of a cent, not 1¢** — `transactions/service.py:845-851`. `Decimal("0.01")` against integer minor units = exact-zero. Fix: `Decimal("1")` (one minor unit). *(Pairs with FE-6 below — frontend has the same unit bug.)*

**M5 [LA-11] Manual transfer link never compares amounts** — `transactions/service.py:709-715`. −500.00 can pair with +3.00; both drop from totals. Fix: enforce the candidates endpoint's ±2% server-side.

**M6 [LA-12] Refund detection can consume email echoes and reimbursement rows** — `reconciliation/refunds.py:40-51`. Fix: restrict to bank source types and `reimbursement_group_id IS NULL` (also in `repair_refund_pairs`).

**M7 [LA-13 + LB-13] `currency=None` sums across currencies (and scales)** — `transactions/service.py:129-135` + router:63; `households/router.py:305,327,340`; `budgets/service.py:28-29`; `get_member_stats` has no currency param at all. Fix: make currency required or default to user's primary server-side.

**M8 [LB-7] Same-transaction PATCH bypasses amount re-validation** — `trips/service.py:750-757`. PATCH `{amount:999, transaction_id:<same>}` diverges expense from `abs(transaction.amount)`. Fix: re-validate whenever linked and amount changed.

**M9 [LB-8] Trip split/settle rounding hardcoded to 2 decimals** — `trips/service.py:386-388,411-412,450`; `balances.py:37,130`. 10.000 CLP ÷ 3 → 3333.33 CLP shares; un-payable. Fix: currency-aware quantum (1 for zero-decimal), same step for `_EPS`.

**M10 [LB-9] Cuota installments never reconcile to the total** — `cuota_service.py:163, 90-93`. 1000/3 → 3×333.33 = 999.99; drift compounds in `future_total`; fractional pesos for CLP. Fix: last installment absorbs remainder; derive future_total from total_amount.

**M11 [LB-10] Duplicate attendee_ids in splits pass validation** — `trips/service.py:524,661` + `_normalize_splits:409-420`. `[A,A,B]` charges A double. Fix: reject duplicates; unique constraint on `(trip_expense_id, attendee_id)`.

**M12 [LB-11] Negative custom shares/percents accepted** — `trips/service.py:421-454`, `schemas.py:69-81`. `[150,-50]` sums fine but corrupts netting semantics. Fix: `ge=0` on the schema.

**M13 [LB-12] Trip-linked transactions count at FULL amount in personal budget** — `budgets/v2_service.py:255-284` (tracked Task 6.4 gap, xfail'd test). Fronting a $900 group dinner shows $900 personal spend instead of your $300 share. Known — but live wrong-money on the dashboard today; prioritize the v1.1 share-carving join.

**M14 [LB-14 + FE-12 + ST-11] Month boundaries and "today" computed in UTC everywhere** — `budgets/v2_service.py:87-96,115-121`; `households/service.py:388,446,546`; `trips/service.py:101-107`; frontend `useTrips.ts:46-49`. Evening purchases on the 31st land in next month for all LATAM timezones. Fix: per-user timezone for month bounds; consolidate the 4 duplicated `_month_bounds` implementations into `core/dates.py`.

**M15 [LB-15] Legacy budget service does money math in float** — `budgets/service.py:31,55,62-63,72`. Fix: Decimal end-to-end.

**M16 [LB-16] Trip suggestions emit raw stored units; expense create validates major units** — `trips/service.py:1241` vs `auto_detect.py:215-217`. Prefilling from a suggestion 422s or inflates 100×. Fix: emit `_txn_amount_to_major(abs(amount), currency)`.

**M17 [LB-21] No unique constraint on `transaction_splits.transaction_id`** — `alembic/versions/001:242-264` + `_ensure_split` check-then-insert race. One race silently doubles a transaction in every total (see C1). Fix: unique index + `ON CONFLICT DO NOTHING`.

**M18 [SEC-3] Household members can mutate a partner's personal transactions** — `transactions/service.py:234,378,434,476,546,599`. Gated on household membership, not ownership/shared-ness; flipping a partner's personal tx to `shared` pierces partner privacy. Fix: non-owners restricted to already-shared rows.

**M19 [SEC-5] WhatsApp PIN send has no rate limit** — `auth/router.py:209`. Pumping/harassment/denial-of-verification. Fix: 3/hour per user+phone + Redis cooldown.

**M20 [PF-6] `get_budget_v2` = ~18–22 sequential round trips** — `v2_service.py:1087-1343`. 200ms+ pure latency on the primary screen. Fix: merge the 3 history months into one GROUP BY, fold per-member loops into grouped queries.

**M21 [PF-7] Bulk category/merchant updates emit one UPDATE per row** — `transactions/service.py:342-365, 523-543`. 400-row merchant = 400 UPDATEs per click. Fix: single `UPDATE ... WHERE match_clause`.

**M22 [PF-8] Merchant review does per-name SELECTs before the LLM phase** — `jobs/tasks.py:945-986`. Fix: one `IN` query into a dict.

**M23 [PF-9] New Redis pool per `enqueue_job` call** — `jobs/queue.py:14-20`. Handshake per enqueue on hot paths. Fix: module-level lazy singleton.

**M24 [PF-11] No composite indexes for user/household + date queries** — `alembic/versions/008:24-30`. Every hot query filters id + date range. Fix: `(user_id, transaction_date DESC)`, `(household_id, transaction_date DESC)`.

**M25 [PF-12] Reconciliation tick N+1s** — `reconciliation/tick.py:109-124, 68-80`. Fix: single UPDATE...FROM for aging; pre-fetch PlaidItem map.

**M26 [PF-13] Daily reconciliation safety net loops all households in one job** — `jobs/tasks.py:1128-1142`. Exceeds 600s at scale; later households never processed. Fix: fan-out per household. **Related dead-code bug:** `run_reconciliation_tick` (the full tick) is registered in NO worker — the 6am job only runs transfer detection, contradicting its docstring.

**M27 [ST-4] `_ZERO_DECIMAL_CURRENCIES` duplicated in two modules** — `trips/service.py:370`, `plaid/mapper.py:53`. Drift = 100× money divergence. Also wrong: CLF is 4-decimal (LB-19: up to ~CLP 19.500 lost per UF transaction), and COP is ISO-2-decimal (verify intended behavior). Fix: single source in `modules/currencies/` with corrected contents.

**M28 [ST-5] Five test files mock the DB, violating the no-mocks convention** — `tests/conftest.py:103-115` + test_bank_accounts_routes, test_auth, test_email_webhooks, test_merchant_review_api, test_notifications_api. Fix: migrate to real-DB fixtures; delete `mock_db_session`.

**M29 [ST-6] Silent `except Exception: pass` on merchant-training writes** — `transactions/service.py:261,372` (duplicated verbatim); also `trips/service.py:1176`. Fix: shared helper with `logger.warning`.

**M30 [ST-7] Sankey drilldown (242 lines of money queries) has zero tests** — `v2_service.py:1583`. Fix: `test_budget_v2_drilldown.py` per node kind.

**M31 [ST-8] `transactions/service.py` god-module; `ServiceError` defined at line 1110** — Fix: move errors to top/own file; extract the ~800-line linking cluster to `linking.py`.

**M32 [ST-9] Trips raises HTTPException from service; transactions uses ServiceError** — Pick one (ServiceError), document in ARCHITECTURE.md, migrate opportunistically.

**M33 [ST-10] `budgets/service.py` looks legacy but is live** — frontend still calls `/budgets/monthly` + `/budgets/categories` (`api.ts:539-562`). Fix: rename or docstring each of the 5 budget service files with which screen it backs.

**M34 [FE-6] Reimbursement dialog tolerance is 0.005 of a *cent*** — `ReimbursementLinkDialog.tsx:91-93`. Blocks combos the server would accept (backend counterpart: M4). Fix: tolerance in stored units, zero-decimal-aware.

**M35 [FE-7] Reimbursement dialog sums candidates across currencies** — `ReimbursementLinkDialog.tsx:85-93`. Fix: filter/disable non-anchor-currency candidates.

**M36 [FE-8] Hardcoded `es-CL` date locale** — `PendingBlock.tsx:669`, `ReimbursementLinkDialog.tsx:249-252`. Fix: `resolveAppLocale()`.

**M37 [FE-9] Hardcoded `$0` net-zero chip** — `PairedTransactionCard.tsx:317`. Fix: `formatStoredAmount(0, currency)`.

**M38 [FE-10] Trip expense/settlement dialogs allow double-submit** — `AddExpenseSheet.tsx:243,460-467`, `MarkSettledDialog.tsx:131,204-211`. `isPending` hardcoded false; two fast taps = duplicate expense (real trip-ledger money duplication); errors via `window.alert`. Fix: wire the mutation's real `isPending`; toast for rollback errors.

### LOW

**L1 [LA-14]** `plaid/sync.py:409-414,427-431` — balance `int(x*100)` truncates; off by a cent half the time. Use `round()`.
**L2 [LA-15]** `transfers.py:179`, `wallets.py:129` — `abs((a-b).days)` makes the ±2-day window asymmetric by row order. Compare full timedelta.
**L3 [LA-16]** `bank_connect/mapper.py:28-31` — dedup hash uses raw numeric repr; `1050` vs `1050.0` re-inserts duplicates. Canonicalize.
**L4 [LB-17]** `households/service.py:514-524` — settlement transfers never quantized; fractional-cent instructions. Quantize per currency, last member absorbs residual.
**L5 [LB-18]** `trips/service.py:976-1024` — creator force-removing self → `from==to` CHECK violation → 500. Early-guard 422.
**L6 [LB-20]** `auto_detect.py:127-128,169` — 5.00 absolute tolerance floor is microscopic in CLP/COP; settlement suggestions never fire. Scale per currency.
**L7 [SEC-6]** `plaid/router.py:60,84,113,164` — raw exception text in 500s; unhandled UUID ValueError. Generic details; typed params.
**L8 [SEC-7]** `auth/router.py:217` — PIN via `random.randint`; use `secrets.randbelow`.
**L9 [SEC-8]** `core/rate_limit.py:23` — limiter keys on proxy IP behind Railway; verify proxy-header config or key per-user.
**L10 [PF-14]** `v2_service.py:1767-1783` — drilldown re-fetches full month rows for a top-5 list. GROUP BY LIMIT 5.
**L11 [PF-15]** `transactions/service.py:76-106,200-231` — no pagination on transaction lists. Keyset pagination.
**L12 [ST-12]** `trips/service.py:1145-1177` — trips re-parses the subscriptions cache schema via raw SQL. Expose a subscriptions-module function.
**L13 [FE-11]** Trip amount inputs assume 2 decimals (`step="0.01"`, `toFixed(2)`, unformatted "Suma:" line) for CLP/COP trips. Derive from `isZeroDecimalCurrency`.
**L14 [FE-13]** `Field` labels have no `htmlFor`/id association on money-entry forms (WCAG 1.3.1). `useId()`.
**L15 [FE-14]** `budgets/page.tsx:358-371` — `sameAsHogar` heuristic hides the Personal view when both are all-zero (day 1 of month). Compare member count, not value equality.

### NIT

**N1 [LA-17]** `plaid/mapper.py:83` — $0.00 tx classified as income; `unofficial_currency_code` ignored.
**N2 [LA-18]** `transactions/models.py:20` — `amount: Mapped[float]` on a Numeric column returning Decimal; annotate `Mapped[Decimal]` and document the minor-units convention at the model.
**N3 [LB-22]** `v2_service.py:1263,1358` — Decimal→float→Decimal round-trip for a percentage; `quantize`.
**N4 [PF-16]** `dedup.py:449-451` — redundant bank-name lookup per call; pass `known_bank` from callers.
**N5 [ST-13]** Stale comments referencing deleted `_build_sankey` (`v2_service.py:621`, `test_budget_v2_endpoint.py:336`).
**N6 [FE-15]** `PendingBlock.tsx:661-692` — inflow transfer legs rendered with parens + aria "menos".

### Promoted from agents' out-of-scope notes (verify + fix)

- **User-cache blob omits `feature_trips_enabled`** (`core/security.py`) — trips-enabled users likely get 403 on cached requests. Fails closed, but it breaks the feature intermittently. *(Security agent)*
- **`plaid/sync.py:369` deletes removed transactions without clearing `transfer_pair_id`/`refund_pair_id` on surviving partners** — orphaned pair-ids exclude survivors from totals. *(Performance agent)*
- **`bank_connect/service.store_credentials` never dedups per (user, bank)** — second connect → `MultipleResultsFound` 500. *(Security agent)*
- **Budgets v2 excludes by different rules than the dashboard summary** — adopt one shared `exclude_from_totals` predicate (see theme 3). *(Logic-A)*
- **Trips `accept_invite` sliding 30-day refresh extends invite links indefinitely.** *(Logic-B)*
- **`get_member_stats` LEFT JOIN has no date bound** — "total_spent" is all-time; check the UI label. *(Logic-B)*
- **`jobs/tasks.py` (1,142 lines) trending toward god-module; jobs use `print()` instead of logger.** *(Style, Performance)*

---

## Cross-cutting observations (parent synthesis)

1. **One `counts_toward_totals` predicate.** Five different subsystems implement "which transactions count" with five different exclusion sets (transfer pairs, refund pairs, reimbursement groups, wallet legs, trip shares). Extract a single SQLAlchemy filter helper (and mirror it in one frontend util) and make every aggregator use it. This one refactor resolves C2, H4, H19, and the budget-vs-dashboard disagreement class.
2. **One currency-units module.** `_ZERO_DECIMAL_CURRENCIES` + `to_minor_units` + `to_major_units` + per-currency quantum, living in `modules/currencies/`, imported everywhere (plaid, bank_connect, trips, budgets, credit suggestions, frontend equivalent in `lib/currency.ts`). Resolves H8, H11, M9, M10, M27, L13 and prevents the whole 100×-drift class.
3. **Missing DB constraints are letting application bugs become money bugs.** Unique on `transaction_splits.transaction_id`, unique on `(trip_expense_id, attendee_id)`, and the composite date indexes. Constraints turn silent double-counting into loud errors.
4. **Ordering as an implicit contract.** C4 exists because `split_ratio` is a bare array whose meaning depends on query ORDER BY. Consider storing ratios keyed by user_id instead of positionally.
5. **Fan-out, not batching, for crons.** Three separate jobs (subscriptions cache, email batches, reconciliation safety net) share the same failure shape: one job iterating all users/households until a timeout kills it silently. The fix is the same pattern each time.
6. **Test suite blind spots are exactly where the critical bugs are.** `run_plaid_sync` has no tests (C1 lives there); settlement tests feed impossible inputs (C3); the dead `list_trips` is tested while the live one isn't (H18). Post-fix, each critical gets a regression test against the real DB per project convention.

## What looked good

JWT/JWKS validation with alg allowlisting; invite tokens hashed with 256-bit entropy; Plaid tokens Fernet-encrypted and never serialized; trip balance netting and smart-settle math verified correct; split remainder allocation exact for 2-dp currencies; trip stubs correctly isolated from budgets; Sankey flows conservation-correct; real-DB test convention mostly upheld with strong coverage of dedup/transfers/refunds/wallets/trips.
