# Luka Ultrareview — Transaction Consolidation Workflow

**Date:** 2026-04-20
**Reviewer:** 5 parallel subagents (security, logic, performance, style, frontend)

---

## 1. Scope reviewed

**Backend (~2,000 LOC):**
- `backend/modules/reconciliation/dedup.py` (225)
- `backend/modules/reconciliation/transfers.py` (92)
- `backend/modules/transactions/{service,router,models,schemas,idempotency}.py` (599)
- `backend/modules/plaid/{sync,mapper}.py` (392)
- `backend/modules/email/{parser,llm_parser}.py` (535)

**Frontend (~1,400 LOC):**
- `frontend/app/(dashboard)/components/PendingBlock.tsx` (459)
- `frontend/app/(dashboard)/transactions/page.tsx` (644)
- `frontend/app/(dashboard)/components/TransactionCard.tsx`
- `frontend/app/(dashboard)/components/SplitTypeEditor.tsx`

Agents run: security, logic, performance, style, frontend. All returned.

---

## 2. Executive summary — act on these in order

The three symptoms you described are **not random UX glitches — they are caused by specific, identifiable bugs** across the reconciliation pipeline. Fix these 5 things and the entire workflow changes:

1. **`detect_transfers()` is dead code.** It's defined in `reconciliation/transfers.py` but **never called** from `plaid/sync.py` or any cron. This alone explains why the $2,000 AmEx payment pair is never linked. → **[Logic #2, critical]**
2. **Status vocabulary mismatch: `"confirmed"` vs `"settled"`.** `plaid/sync.py` writes `status="confirmed"` on settled Plaid txns, but `service.py` and the rest of the app filter on `status="settled"`. Plaid rows never leave the pending bucket. → **[Logic #8, critical]**
3. **Email→Plaid reconciliation only fires when Plaid arrives *after* email.** If Plaid posts before the email arrives (common with Zelle/BoA alerts), the email pending row is orphaned forever — no periodic retry worker exists. This is the #1 cause of the 14-abr→20-abr backlog. → **[Logic #3, critical]**
4. **CC payment counterpart lookup is inverted.** `plaid/sync.py:94-107` does `bank_name.contains(merchant_name)` (searching the noisy merchant string inside the short bank name) — it should be the reverse. The card last-4 from the email LLM parser is also parsed but **never persisted** to `transfer_to_account_id`. → **[Logic #1 + #12, critical]**
5. **Same-account refunds/reimbursements are explicitly excluded from transfer detection.** `transfers.py` skips `tx_a.bank_account_id == tx_b.bank_account_id` — but the Uber Eats $27.43 ± pair *is* same-account. You need a separate refund detector. → **[Logic #6, high]**

Secondary but important:
- **Cross-user transfer pairing** (Security #2): `detect_transfers` pairs by household without a `user_id` constraint — partner A's salary can be cancelled against partner B's same-amount expense. Money-visibility bug.
- **Currency ignored in dedup and duplicate-detection** (Logic #5, #15): CLP 2,000 and USD 2,000 collide. LATAM invariant violation.
- **No UI to manually match / bulk resolve / dismiss pending** (Frontend #1, #2): users are stuck watching the queue grow.
- **CC payment pair renders as 3 separate cards** (Frontend #3): user sees phantom $4,000 where only $2,000 moved. Trust-killer.

---

## 3. Findings by severity

### CRITICAL

- **[Logic #1]** `backend/modules/plaid/sync.py:94-107` — `is_plaid_transfer` counterpart-lookup is inverted. `bank_name.contains(merchant_name)` should be `merchant_name.contains(bank_name)` + match on last-4. Directly causes symptom #2.
- **[Logic #2]** `backend/modules/reconciliation/transfers.py` — `detect_transfers()` is never invoked anywhere. Wire into `plaid/sync.py` + periodic ARQ job on slow worker.
- **[Logic #3]** `backend/modules/reconciliation/dedup.py:23-85` — no reverse reconciliation for email-after-bank ordering and no periodic retry for aging pending. Root cause of 31-item backlog.
- **[Logic #8]** `backend/modules/plaid/sync.py:132-145` — writes `status="confirmed"`, rest of app expects `"settled"`. Pick one vocabulary and migrate.

### HIGH

- **[Security #1]** `backend/modules/reconciliation/dedup.py:88-118` — `apply_match_and_delete_emails` deletes + re-links by caller-supplied IDs with no `user_id` guard. Defense-in-depth gap.
- **[Security #2]** `backend/modules/reconciliation/transfers.py:20-92` — transfer pairing scoped to household only; same-amount opposite-sign txs from different household members get paired as transfers and silently vanish from income/spend totals. Require `tx_a.user_id == tx_b.user_id`.
- **[Logic #4]** `backend/modules/transactions/service.py:224-271` — `get_pending_transactions` returns `unmatched_email: []` always (never populated); no expiry path for aged pending rows.
- **[Logic #5]** `backend/modules/reconciliation/dedup.py:121-159` — `_find_single_match` ignores currency, sign, and `bank_account_id`. Feeds both symptom #1 and #3.
- **[Logic #6]** `backend/modules/reconciliation/transfers.py:46-90` — explicit `if same_account: continue` excludes same-account refund pairs. Add a separate refund/reversal detector (same account, same merchant, opposite signs, ±3d).
- **[Logic #7]** `backend/modules/reconciliation/dedup.py:139-143` — merchant ILIKE substring filter kills CC-payment matching (email="Pago Tarjeta ****3100", Plaid="American Express"). Skip merchant filter when `transaction_type='transfer'`.
- **[Logic #9]** `backend/modules/plaid/sync.py:140-145` — modified-branch `amount = round(plaid_amount * -100)` assumes USD-cents for all currencies; corrupts CLP amounts on modification.
- **[Logic #10]** `backend/modules/reconciliation/dedup.py:101-107` — `apply_match_and_delete_emails` doesn't consistently propagate `transaction_type='transfer'` from email to bank, and doesn't null out `category` for transfers → hence "Servicios" on the AmEx payment pair.
- **[Style #1]** `backend/modules/transactions/service.py:183` — bare `except Exception: pass` on category training call swallows errors silently.
- **[Perf #1]** `backend/modules/transactions/service.py:13-43, 129-159` — `get_my_transactions` + `get_shared_transactions` unbounded; dashboard loads 6 months fully.
- **[Perf #2]** `backend/modules/reconciliation/dedup.py:139-158` — leading-wildcard `ILIKE '%name%'` runs once per Plaid tx; sequential scan, no index.
- **[Perf #3]** `backend/modules/reconciliation/transfers.py:31-92` — unbounded household fetch, no composite index on `(household_id, transaction_date)`, no partial index on `transfer_pair_id IS NULL`.
- **[Perf #4]** `backend/modules/plaid/sync.py:74-129` — per-tx serial loop with 3+ round-trips each; 500-tx initial sync = 2,000+ sequential Supabase roundtrips.
- **[Frontend #1]** `PendingBlock.tsx:417-455` — no manual-match, bulk-resolve, or force-settle affordances on pending items.
- **[Frontend #2]** `PendingBlock.tsx:335-340` — no "stuck for N days" age indicator. 14-abr and 20-abr items look identical.
- **[Frontend #3]** `TransactionCard.tsx:62-156` + `PendingBlock.tsx:278-366` — CC bill payments render as 3 unlinked cards (pending transfer + settled expense + settled income). No grouping, no pair badge. Phantom $4,000 where $2,000 moved.
- **[Frontend #6]** `PendingBlock.tsx:374-459` — no pagination or virtualization; 31 rows × 72px = 2,200px scroll on mobile.
- **[Frontend #7]** `TransactionCard.tsx:106-108` — negative amounts use parentheses only, no `aria-label`. WCAG 1.3.1 fail + parentheses unfamiliar in LATAM.

### MEDIUM

- **[Logic #11]** `dedup.py:191` — `_find_sum_match` isn't actually subset-sum; only works when *all* candidates sum exactly.
- **[Logic #12]** `email/parser.py:241-252` + `llm_parser.py` — `card_last_four` parsed by LLM but **never written** to `transfer_to_account_id`. This is the missing link that would let CC payments reconcile by card ID.
- **[Logic #13]** `transfers.py:28` — naive `datetime.now(utc)` vs LATAM-local `transaction_date`; 2-day window can miss by one.
- **[Logic #14]** `service.py:237` — `source` vs `source_type` inconsistency; dedup uses the weaker filter.
- **[Logic #15]** `service.py:301-347` — `is_duplicate_transaction` ignores currency. CLP 2,000 and USD 2,000 collide.
- **[Logic #16]** `plaid/mapper.py:87-88` — storing Plaid date at midnight UTC bucketizes end-of-month txs into the wrong month.
- **[Security #3]** `plaid/sync.py:81-87` — Plaid dedup query has no `user_id` / `plaid_item_id` scope; relies on Plaid ID global uniqueness.
- **[Security #4]** `service.py:313-347` — `is_duplicate_transaction` Tier 1 doesn't filter by `source_bank_name`; can silently drop legit cross-bank same-amount txs within 5 min.
- **[Security #5]** `transactions/router.py:64-87` — `update_category`/`update_split_type` use user-only authorization; inconsistent with joint-account UX. Document or fix.
- **[Security #6]** `email/parser.py:37-63` — regex patterns with lazy quantifiers on broad classes over untrusted email bodies → ReDoS risk on fast worker.
- **[Security #7]** `transactions/models.py:34` — `raw_email_text` persists full email body indefinitely. PII blast radius.
- **[Perf #5–9]** Misc: removed-tx loop sequential (sync.py:151-198), `get_pending_transactions` no limit + missing partial indexes, `transfer_pair_id` unindexed, `func.abs(amount)` disables index in `is_duplicate_transaction`, LLM waterfall has no response cache (llm_parser.py:156-198).
- **[Perf #10]** `transactions/page.tsx:474-482` — `filteredAll` concat+dedupe+sort on every keystroke with no debounce.
- **[Perf #11]** `PendingBlock.tsx` + `useTransactions.ts:40-46` — `refetchOnWindowFocus: true` with 30s staleTime on the expensive pending query.
- **[Style #2–4]** Hardcoded Spanish month labels in backend, permanently-empty `unmatched_email` response key, private-API import of `_get_redis`.
- **[Style #10]** `plaid/sync.py:141-144` — Plaid amount conversion duplicated between mapper and sync; load-bearing convention, drift risk.
- **[Style #13]** `email/parser.py` hardcodes CL+US regex only for a 6-country LATAM product.
- **[Style #15]** `llm_parser.py:14,19,144-210` — module-level mutable circuit-breaker globals; not shared across worker processes.
- **[Style #19, #20]** `PendingBlock.tsx:33` + `transactions/page.tsx:17-23` — hardcoded zero-decimal currency list, two different inconsistent `formatAmount` helpers.
- **[Frontend #4]** `TransactionCard.tsx:94-127` — no duplicate/reimbursement hint for same-merchant same-amount repeats.
- **[Frontend #5]** `PendingBlock.tsx:80-90, 232-238` — no AI-confidence indicator on LLM-guessed categories.
- **[Frontend #9]** `PendingBlock.tsx:82, 232` + `SplitTypeEditor.tsx:52-54` — tap targets <24px on category/split pills; WCAG 2.5.5 fail.
- **[Frontend #10]** Pills lack `aria-haspopup`/`aria-expanded`, roll their own dropdown instead of shadcn `Select`. Keyboard + screen reader broken.
- **[Frontend #11]** `PendingBlock.tsx:402-414` — collapsible header missing `aria-expanded`.
- **[Frontend #12]** `PendingBlock.tsx:380-381` — `if (isLoading || !data) return null` — no skeleton, no error state.
- **[Frontend #13]** `SplitTypeEditor.handleSelect` invalidates `["transactions"]` but not `["transactions","pending"]` → stale pending UI after edit elsewhere.
- **[Frontend #14]** Optimistic updates lack `onSettled: invalidateQueries` → UI diverges from server silently.
- **[Frontend #15–17]** Bare spinner (not skeleton), no empty state, no virtualization on 100/page.

### LOW / NIT

- **[Security #8]** Hard delete of pending email txns — no audit trail, no soft-delete.
- **[Security #9]** Raw email body sent to Gemini with no PII redaction — document in privacy policy + redact PAN/RUT.
- **[Security #10]** `dedup.py:139-144` — manual `%/_` escape without passing `escape=` arg to `.ilike()`.
- **[Logic #17–18]** `dedup.py:98-107` no `superseded_by` audit trail; `llm_parser.py:147` uses deprecated `datetime.utcnow()`.
- **[Style #5–9, #11–12, #14, #16–18, #21–25]** Inline imports, LIKE-escape duplication, missing type hints, dead `account_type` enrichment key, missing Plaid account kinds, deprecated `utcnow()`, hardcoded model names, `personal|partner|shared` doc drift, duplicated `formatAmount`, duplicated account-kind constants, missing `useEffect` dep.
- **[Frontend #18–25]** Missing `useEffect` dep, `es-CL` hardcoded locale, raw Tailwind colors instead of tokens, `useIsMobile` duplicated + SSR flash, "Eliminar" without `AlertDialog`, nested interactive elements on currency pill, `toTitleCase` + source badge English strings.

---

## 4. Cross-cutting observations

Patterns that emerged across multiple agents — these are where the architecture itself needs rethinking, not just bug fixes:

1. **Reconciliation is one-shot, not a lifecycle.** Logic, Perf, and Frontend all flagged the same underlying issue: matching only fires on Plaid-sync-insert. There's no retry, no aging, no expiry, no "orphaned email" promotion. The fix is architectural: introduce a periodic `reconciliation_tick` slow-worker job that (a) re-matches aging email pending, (b) runs `detect_transfers`, (c) detects same-account refunds, (d) promotes aged-out rows to a visible "orphan" bucket.

2. **Multi-currency invariant is broken in three places.** Logic #15 (dup-detect ignores currency), Logic #9 (modify-branch 100× scaling), Logic #5 (dedup ignores currency), Style #19 (two different hardcoded zero-decimal currency lists in frontend). The codebase says LATAM-first but treats USD implicitly as default. Needs a single `currency_meta.py` (backend) + `currency.ts` (frontend) with ISO 4217 metadata as source of truth.

3. **Status/source vocabulary is not canonical.** `status` uses `pending | confirmed | settled` interchangeably across modules; `source` vs `source_type` columns overlap. Both Security, Logic, and Style flagged variants of this. Pick one vocabulary, add a DB CHECK constraint, migrate, delete the alternate.

4. **Authorization model is implicit, not explicit.** Security #1, #2, #5 all flag the same class: functions trust caller-supplied IDs without re-checking `user_id`/`household_id` in the query. None are exploitable today, all are one refactor away from being IDORs. Enforce scope in the query, not at the caller layer.

5. **The CC-payment story is broken end-to-end, not in one place.** Logic #1 (inverted counterpart lookup), Logic #10 (type not propagated), Logic #12 (card_last_four parsed but not persisted), Frontend #3 (3-card render) — four agents all found a different facet. Fixing just one won't resolve symptom #2. Needs a coordinated pass: persist card_last_four → match by card → propagate `type=transfer` → null category → render as grouped pair.

6. **Frontend optimistic patterns are ad-hoc.** Frontend #13, #14, Style #25 — three places reinvent `setQueryData` rollback with subtle divergence. Extract one `useOptimisticTxMutation` hook and use it everywhere.

---

## 5. What looked good

- `reconciliation/transfers.py` exists — the data model for `transfer_pair_id` and transfer detection was designed up-front, even if it's not wired.
- `email/llm_parser.py` waterfall architecture (template → 4-model Gemini ladder → regex) is a genuinely good design; just needs a response cache.
- `PendingBlock.tsx` collapsible with per-section optimistic updates shows clear product intent for this workflow.
- Idempotency table + webhook dedup exists and is correct for its scope.

---

## 6. Next steps — pick your attack

**Option A — "Stop the bleeding" (1 day):** Fix the 4 criticals + wire `detect_transfers` into sync. Symptom #1 drops 60-80%, symptom #2 starts resolving.

**Option B — "Fix the story" (3–4 days):** Option A + persist `card_last_four` + add periodic reconciliation tick + add same-account refund detector + render pair-linked CC payments as one card. All three symptoms addressed.

**Option C — "Rebuild reconciliation as a lifecycle" (1–2 weeks):** Option B + canonical status vocabulary migration + currency-meta source of truth + explicit authorization scope + optimistic-hook unification + UI bulk-match/manual-match actions. Ships a solid v2.

Want me to take any of these? Point me at finding numbers (e.g. "Logic #1, #2, #3, #8") or say "all critical", "Option A", "Option B".
