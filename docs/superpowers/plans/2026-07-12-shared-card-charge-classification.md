# Shared-Card Charge Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A card flagged `shared_card` pends every charge (counts for nobody) and shows it in both partners' Luka; either partner sorts each — first wins — into owner/partner × personal/shared. Personal never touches the other or the balance; shared credits the actual payer. A daily notification nudges pending charges.

**Architecture:** Extends the shipped attribution feature. New `transactions.needs_classification` boolean (orthogonal to bank `status`) marks unsorted shared-card charges, excluded from the one totals rule. A classify action writes `split_type` + (for the partner) a `transaction_attributions` row; the attribution's meaning is disambiguated by `split_type` (`partner`=partner's personal → effective owner; `shared`=partner paid → effective payer). Settlement gains an `effective_payer_id` mirror of `effective_owner_id`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, Alembic, pytest (real DB), Next.js 16 + React 19 + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-07-12-shared-card-charge-classification-design.md`

**Conventions (from CLAUDE.md + prior feature):**
- Integer minor units; `modules/currencies/units.py`. One totals rule: `modules/transactions/totals.py`. `mark_user_edited(txn,"split_type")` protects manual edits.
- Real-DB savepoint `db` fixture; register models with `import x.models  # noqa: F401`. Lint `uv run ruff check/format`; commit `--no-verify`. Frontend `npx tsc --noEmit`.
- Alembic head is `055`. Migrations are applied to the prod-pointed test DB to run tests (additive only; confirmed acceptable for this session). Commit trailers on every commit:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01KTzzogYq2HwKtDuvJttYFa
  ```
- Attribution primitives already exist in `modules/transactions/attribution.py`: `effective_owner_id`, `_attributed_away`, `attributed_to_clause`, `owned_by_caller_clause`, `list_visible_clause`, `personal_scope_clause`, `hand_off`, `reject`, `un_tag`, `AttributionNotFound/Forbidden`, `account_person_balances`.

---

## File Structure
- `backend/alembic/versions/056_shared_card_needs_classification.py` — Create: `needs_classification` column.
- `backend/modules/transactions/models.py` — Modify: add `needs_classification`.
- `backend/modules/transactions/totals.py` — Modify: exclude `needs_classification IS NOT TRUE`.
- `backend/modules/transactions/classification.py` — Create: shared-card domain (is-shared-card check, four-way `classify`, `effective_payer_id`, "por clasificar" query). Kept separate from `attribution.py` so neither file sprawls.
- `backend/modules/transactions/attribution.py` — Modify: `account_person_balances` excludes `needs_classification`; `personal_scope_clause` attributed-shared guard.
- `backend/modules/households/models.py` — Modify: `shared_card` in the account_type doc/Literal sites.
- `backend/modules/households/service.py` — Modify: the ~5 raw-SQL shared-payer blocks → effective-payer.
- `backend/modules/bank_accounts/router.py` — Modify: PATCH accepts `shared_card`; backfill on switch.
- `backend/modules/plaid/sync.py`, `backend/modules/bank_connect/router.py` — Modify: set `needs_classification` on ingest.
- `backend/modules/transactions/router.py` — Modify: `GET /transactions/por-clasificar` + `POST /transactions/{id}/classify`.
- `backend/jobs/` — Modify/Create: daily `pending_card_classification` notification cron.
- `frontend`: `app/lib/api.ts`, `app/(dashboard)/settings/components/BankAccountsSection.tsx` (type option), a new "Por clasificar" surface + four-way control, `app/(dashboard)/notifications/page.tsx`.
- Tests: `backend/tests/test_shared_card_classification.py`.

---

### Task 1: `needs_classification` column + `shared_card` type

**Files:** Create `backend/alembic/versions/056_shared_card_needs_classification.py`; Modify `backend/modules/transactions/models.py`, `backend/modules/households/models.py`; Test `backend/tests/test_shared_card_classification.py`.

- [ ] **Step 1: Failing test** — create the test file with a couple/household/shared_card helper and assert a `Transaction` persists with `needs_classification=True`, and that `BankAccount(account_type="shared_card")` persists. (Model the couple/account helpers on `tests/test_transaction_attribution.py`.)
- [ ] **Step 2: Run → fail** (`needs_classification` missing).
- [ ] **Step 3:** Add to `Transaction` model:
```python
needs_classification: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default=text("false")
)
```
(ensure `Boolean`, `text` imported). Migration:
```python
"""056 — transactions.needs_classification (shared-card charge sort)

Revision ID: 056
Revises: 055
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, Sequence[str], None] = "055"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("transactions", sa.Column(
        "needs_classification", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_transactions_needs_classification", "transactions",
                    ["needs_classification"], postgresql_where=sa.text("needs_classification"))

def downgrade() -> None:
    op.drop_index("ix_transactions_needs_classification", table_name="transactions")
    op.drop_column("transactions", "needs_classification")
```
Add `"shared_card"` everywhere `account_type` is a `Literal[...]` (households/models doc comment + `bank_accounts/router.py` `Create/UpdateBankAccountBody`).
- [ ] **Step 4:** `uv run alembic upgrade head` (prod-pointed; additive index is partial on `needs_classification=true` — cheap). Run the test → pass.
- [ ] **Step 5:** Lint + commit `feat(shared-card): needs_classification column + shared_card type`.

---

### Task 2: Totals exclusion + per-person balance exclusion

**Files:** Modify `backend/modules/transactions/totals.py`, `backend/modules/transactions/attribution.py`; Test append.

- [ ] **Step 1: Failing test** — a `needs_classification=True` expense on a shared_card must be excluded by `counts_toward_totals_clauses()`/`exclude_from_totals` AND not appear in `account_person_balances`.
- [ ] **Step 2: fail.**
- [ ] **Step 3:** In `totals.py` add to BOTH `totals_exclusion_sql` (`AND {alias}.needs_classification IS NOT TRUE`) and `counts_toward_totals_clauses` (`Transaction.needs_classification.isnot(True)`). In `attribution.account_person_balances`, add `Transaction.needs_classification.isnot(True)` to its WHERE. (Use `IS NOT TRUE`/`isnot(True)` for NULL-safety.)
- [ ] **Step 4: pass** + run `tests/test_transaction_attribution.py` (no regression).
- [ ] **Step 5:** Commit `feat(shared-card): exclude needs_classification from all money totals`.

---

### Task 3: Ingestion sets `needs_classification` for shared-card charges

**Files:** Create `backend/modules/transactions/classification.py`; Modify `backend/modules/plaid/sync.py`, `backend/modules/bank_connect/router.py`; Test append.

- [ ] **Step 1: Failing tests** — (a) a Plaid-path charge on a `shared_card` account is created with `needs_classification=True`; a charge on a normal account is `False`. (b) same for the Connect `_process_movements` path. (c) a **transfer** on a shared_card is `False` (never pending).
- [ ] **Step 2: fail.**
- [ ] **Step 3:** In `classification.py` add a helper `def should_pend(account_type: str | None, transaction_type: str | None) -> bool: return account_type == "shared_card" and transaction_type != "transfer"`. Both sync sites already build an `account_type_map`/have the account type; after creating the `Transaction` (before/at flush) set `new_tx.needs_classification = should_pend(account_type, new_tx.transaction_type)`. In Plaid `sync.py` this is where `ensure_default_split` is called (the account type is `account_type_map.get(bank_account_id)`); in `bank_connect/router.py` `_process_movements` the account type is in `account_type_map`. Ensure `transaction_type` is finalized before the check (CC-payment transfer routing may set it — set `needs_classification` AFTER type is decided).
- [ ] **Step 4: pass.**
- [ ] **Step 5:** Commit `feat(shared-card): pend new shared-card charges at ingestion`.

---

### Task 4: "Por clasificar" dual-visibility query + endpoint

**Files:** Modify `backend/modules/transactions/classification.py`, `backend/modules/transactions/router.py`; Test append.

- [ ] **Step 1: Failing test** — `list_pending_for_household(db, household_id, caller_id)` returns the shared-card `needs_classification=True` rows for a household to BOTH members; a non-member gets nothing; normal-account rows never appear.
- [ ] **Step 2: fail.**
- [ ] **Step 3:** In `classification.py`:
```python
async def list_pending_for_household(db, household_id, caller_id):
    # caller must be an active member (enforce in the endpoint via require_membership)
    rows = await db.execute(
        select(Transaction)
        .join(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == household_id,
            Transaction.needs_classification.is_(True),
            BankAccount.account_type == "shared_card",
        )
        .order_by(Transaction.transaction_date.desc())
    )
    return rows.scalars().all()
```
Endpoint `GET /transactions/por-clasificar?household_id=...` → `require_membership` then return serialized rows (merchant, amount, currency, date, bank_name, id). Both members can call it.
- [ ] **Step 4: pass.**
- [ ] **Step 5:** Commit `feat(shared-card): por-clasificar dual-visibility endpoint`.

---

### Task 5: Four-way classify op + endpoint + first-wins

**Files:** Modify `backend/modules/transactions/classification.py`, `backend/modules/transactions/router.py`; Test append.

Outcomes → writes (reuse `attribution._set_split` / `hand_off` internals or replicate the split+attribution upsert):
- `owner_personal`: split `personal`, delete any attribution.
- `partner_personal`: split `partner`, upsert attribution `attributed_to=partner, attributed_by=actor, status=active`.
- `owner_shared`: split `shared`, delete any attribution.
- `partner_shared`: split `shared`, upsert attribution `attributed_to=partner, attributed_by=actor, status=active`.
All set `needs_classification=False` and `mark_user_edited(txn,"split_type")`.

- [ ] **Step 1: Failing tests** — each of the four outcomes writes the right split/attribution and clears the flag. First-wins: a second classify on an already-sorted (`needs_classification=False`) row raises `AlreadyClassified`. Only an active household member may classify; the `partner` in partner-* resolves to the other active member (reuse `attribution.resolve_recipient`) or is passed explicitly.
- [ ] **Step 2: fail.**
- [ ] **Step 3:** Implement `async def classify(db, transaction_id, actor_id, outcome, partner_id=None)`:
  - Load txn; if `needs_classification` is not True → raise `AlreadyClassified` (carry who/when if useful).
  - Resolve `partner_id` for partner-* via `resolve_recipient(db, txn.household_id, actor_id)` when omitted (raise `AmbiguousRecipient` if >1).
  - Apply the split via `_set_split`; upsert/delete attribution accordingly; `txn.needs_classification=False`; `mark_user_edited`.
  Endpoint `POST /transactions/{id}/classify` body `{outcome: 'owner_personal'|'partner_personal'|'owner_shared'|'partner_shared', partner_id?}`; caller must be active member of txn.household; map `AlreadyClassified`→409, `AmbiguousRecipient`→409, not-member→403. Commit.
- [ ] **Step 4: pass.**
- [ ] **Step 5:** Commit `feat(shared-card): four-way classify op + endpoint (first-wins)`.

---

### Task 6: `effective_payer_id` + settlement rewrite (households/service.py)

**Files:** Modify `backend/modules/transactions/attribution.py` (add `effective_payer_id` + a documented SQL snippet), `backend/modules/households/service.py`; Test append. **HIGHEST CORRECTNESS RISK — review hard.**

- [ ] **Step 1: Failing tests** (settlement/contribution level, real DB): build a couple + shared_card, then:
  - `partner_shared` charge → the household settlement/breakdown credits the PARTNER as payer (not the owner).
  - `owner_shared` charge → credits the OWNER.
  - `partner_personal` / `owner_personal` → no settlement effect.
  - A `needs_classification=True` charge → no settlement effect.
  Find the real settlement entry point in `households/service.py` (the function behind `/households/{id}/settlement` or contribution breakdown) and assert on its output.
- [ ] **Step 2: fail.**
- [ ] **Step 3:** Add to `attribution.py`:
```python
def effective_payer_id(owner_user_id, attribution):
    """For a SHARED row: who paid = the active-attributed partner, else the owner."""
    if attribution is not None and attribution.status == "active":
        return attribution.attributed_to_user_id
    return owner_user_id
```
In `households/service.py`, for EACH shared-paid raw-SQL block (~462, 539, 656, 735, 809 — verify exact lines) that does `JOIN users u ON u.id = t.user_id ... GROUP BY t.user_id ... FILTER (WHERE ts.split_type='shared')`: change to
`LEFT JOIN transaction_attributions a ON a.transaction_id = t.id AND a.status = 'active'`
and replace `t.user_id` in the payer JOIN/GROUP BY with `COALESCE(a.attributed_to_user_id, t.user_id)`. Keep the `split_type='shared'` filter and the totals-exclusion (now also excludes `needs_classification`). Do NOT change income/personal blocks.
- [ ] **Step 4: pass** + run `tests/` household/settlement suites (`-k "household or settlement or contribution or equity"`) — investigate any change; a shared expense with no attribution must still credit `t.user_id` (COALESCE handles it).
- [ ] **Step 5:** Commit `feat(shared-card): effective-payer credits the partner who paid a shared charge`.

---

### Task 7: `personal_scope_clause` attributed-shared guard

**Files:** Modify `backend/modules/transactions/attribution.py`; Test append.

- [ ] **Step 1: Failing test** — a `partner_shared` charge (split shared, attributed to partner) must NOT appear in the partner's PERSONAL budget (`personal_scope_clause`), but MUST still appear in their transaction list (`list_visible_clause`) and be creditable in settlement. (Regression-guards the leak.)
- [ ] **Step 2: fail.**
- [ ] **Step 3:** In `personal_scope_clause` only, change the attributed branch from `attributed_to_clause(caller_id)` to `and_(attributed_to_clause(caller_id), TransactionSplit.split_type != "shared")`. Do NOT touch `list_visible_clause` or `owned_by_caller_clause`.
- [ ] **Step 4: pass** + `tests/test_transaction_attribution.py` green.
- [ ] **Step 5:** Commit `fix(shared-card): keep partner-shared out of the partner's personal budget`.

---

### Task 8: Account-type UI (`shared_card`) + backfill

**Files:** Modify `backend/modules/bank_accounts/router.py` (backfill on switch), `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`, `frontend/app/lib/api.ts`.

- [ ] **Step 1 (backend):** In the PATCH `update_bank_account` backfill, when `account_type` becomes `shared_card`: do NOT force a split; instead set `needs_classification=True` on that account's existing **non-transfer** transactions so they enter the queue (owner can sort history). When switching AWAY from `shared_card`, set `needs_classification=False` on its rows (resolve to whatever split they have; unsorted default to owner-personal — set split personal where null). Add a backend test.
- [ ] **Step 2 (frontend):** Add `shared_card` → label "Tarjeta compartida" (purple/distinct) to `ACCOUNT_TYPE_LABEL`/color maps and the `<select>` options in both `AccountCard` and `DetectedAccountCard`; widen the `changeType` unions. Invalidate `["por-clasificar"]` too.
- [ ] **Step 3:** `npx tsc --noEmit`.
- [ ] **Step 4:** Commit `feat(shared-card): shared_card account type option + backfill`.

---

### Task 9: "Por clasificar" surface + four-way control (frontend)

**Files:** Modify `frontend/app/lib/api.ts` (methods + types), a new component (e.g. `app/(dashboard)/components/PorClasificar.tsx`) rendered on the dashboard/transactions when the household has pending shared-card charges; wire the four-way action.

- [ ] **Step 1:** `api.ts`: `getPorClasificar(householdId)`, `classifyTransaction(id, outcome, partnerId?)`; types for the pending row + outcome union.
- [ ] **Step 2:** A compact list card "Por clasificar (N)" showing each pending charge with a four-option control: **Mío / De [pareja] / Compartido — yo pagué / Compartido — [pareja] pagó**. On select → `classifyTransaction`; on `409 already_classified` remove the row and toast "ya lo clasificó {name}"; invalidate `["por-clasificar"]`, `["transactions"]`, `["dashboard-summary"]`. Mobile-first; match existing card styling. Show only when count>0.
- [ ] **Step 3:** `npx tsc --noEmit`.
- [ ] **Step 4:** Commit `feat(shared-card): Por clasificar surface + four-way sort control`.

---

### Task 10: Daily pending-classification notification

**Files:** Modify `backend/jobs/` (find the daily-notification cron registration used by monthly recap / charge guardian), add a `notify_pending_classification` job; `frontend/app/(dashboard)/notifications/page.tsx` rendering.

- [ ] **Step 1 (backend test):** the job creates a `pending_card_classification` notification for each active member of a household that has ≥1 `needs_classification=True` shared-card charge; idempotent per user/day; none when count is 0.
- [ ] **Step 2:** Implement the job (fan out per household with shared_card + pending; per active member; payload `{count, household_id}`), register on the existing daily cron schedule. Reuse `create_notification`.
- [ ] **Step 3 (frontend):** render `pending_card_classification` (icon + "N cargos por clasificar" + deep-link to the Por clasificar surface). Mirror the `new_account_detected` pattern.
- [ ] **Step 4:** backend test green; `npx tsc --noEmit`.
- [ ] **Step 5:** Commit `feat(shared-card): daily pending-classification notification`.

---

### Task 11: Edge cases + leave-household + verification

**Files:** Modify `backend/modules/households/service.py` (`remove_member` / the leave path), tests, docs.

- [ ] **Step 1:** Extend `revert_attributions_for_member` (or the leave path) so a departing member's involvement resolves cleanly: their `partner_*` attributions revert (already handled for personal); any `needs_classification=True` shared-card rows resolve to owner-personal (`needs_classification=False`, split personal) so nothing stays pending against a non-member. Test.
- [ ] **Step 2:** Full suite: `uv run pytest tests/test_shared_card_classification.py tests/test_transaction_attribution.py -q` green; plus a broad `-k "household or settlement or budget or dashboard or contribution"` regression.
- [ ] **Step 3:** `npx tsc --noEmit` clean.
- [ ] **Step 4:** Update `ARCHITECTURE.md` (needs_classification, shared_card, effective-payer invariant), `README.md`, `NEXT-STEPS.md`. Commit.

---

## Notes for the implementer
- **Prod DB:** migrations run against the prod-pointed test DB (additive column + partial index — safe). Do NOT merge/deploy — the branch is left for human review (money-critical settlement changes).
- **Highest risk is Task 6** (effective-payer in the raw-SQL settlement blocks) and Task 7 (predicate guard). Verify exact line numbers before editing `households/service.py`; test every payer case.
- **Reuse, don't re-derive:** split writes via `attribution._set_split` + `mark_user_edited`; totals via `totals.py`; the effective-owner/predicate machinery already exists.
- **Exactly-one-owner + effective-payer:** a sorted charge counts for exactly one person (personal) or the shared pot with exactly one payer (shared); a pending charge counts for nobody. Any new aggregate must reuse the predicates.
</content>
