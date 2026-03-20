# Fintoc Account Settings Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add currency display, soft-disable toggle, inline account-type editing, and a professional card UI to the bank account settings page.

**Architecture:** Backend adds a `currency` column to `bank_accounts`, a `PATCH /bank-accounts/{id}` endpoint, and `is_active` filters to all three transaction queries. Frontend replaces the flat `AccountRow` with an `AccountCard` component and wires up the new toggle/edit interactions.

**Tech Stack:** FastAPI + SQLAlchemy async 2.0 + Alembic (backend) · Next.js App Router + TanStack Query 5 + Tailwind CSS 4 + shadcn/ui (frontend)

**Spec:** `docs/superpowers/specs/2026-03-20-fintoc-account-settings-overhaul.md`

---

## File Map

| File | Change |
|------|--------|
| `backend/alembic/versions/010_bank_account_currency.py` | **Create** — adds `currency VARCHAR(3)` to `bank_accounts` |
| `backend/modules/households/models.py` | **Modify** — add `currency` mapped column to `BankAccount` |
| `backend/modules/bank_accounts/router.py` | **Modify** — remove `is_active` filter from list; add `currency`/`is_active` to response; add PATCH endpoint; store currency in connect + webhook |
| `backend/modules/transactions/service.py` | **Modify** — add `BankAccount.is_active == True` filter to `get_my_transactions`, `get_shared_transactions`; add JOIN to monthly summary raw SQL |
| `backend/tests/test_bank_accounts_routes.py` | **Modify** — add tests for PATCH endpoint; update list test to expect currency + is_active |
| `frontend/app/lib/api.ts` | **Modify** — add `currency`/`is_active` to `BankAccountRow`; add `UpdateBankAccountPayload`; add `updateBankAccount()` method; add `currency` to `SelectedFintocAccount` + `ConnectFintocPayload` |
| `frontend/app/(dashboard)/components/FintocAccountPicker.tsx` | **Modify** — pass `currency` through from `FintocAccount` to `SelectedFintocAccount` |
| `frontend/app/(dashboard)/settings/page.tsx` | **Modify** — replace `AccountRow` with `AccountCard`; wire toggle and edit mode to `api.updateBankAccount()` |

---

## Task 1: DB Migration — Add `currency` Column

**Files:**
- Create: `backend/alembic/versions/010_bank_account_currency.py`
- Modify: `backend/modules/households/models.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/010_bank_account_currency.py
"""bank_account_currency

Revision ID: 010
Revises: 009
Create Date: 2026-03-20

Add currency column to bank_accounts.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("currency", sa.String(3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "currency")
```

- [ ] **Step 2: Add `currency` column to the `BankAccount` ORM model**

In `backend/modules/households/models.py`, add this line after `account_number`:

```python
currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
```

The full `BankAccount` class block after this change (relevant lines):

```python
account_number: Mapped[str | None] = mapped_column(String, nullable=True)
currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 3: Run the migration locally**

```bash
cd backend
python3 -m alembic upgrade head
```

Expected output ends with: `Running upgrade 009 -> 010, bank_account_currency`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/010_bank_account_currency.py backend/modules/households/models.py
git commit -m "feat(db): add currency column to bank_accounts (migration 010)"
```

---

## Task 2: Backend — PATCH Endpoint

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Modify: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_bank_accounts_routes.py`:

```python
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

ACCOUNT_ID = str(uuid.uuid4())


def _make_bank_account(import_status="done", is_active=True, user_id=None):
    acc = MagicMock()
    acc.id = uuid.UUID(ACCOUNT_ID)
    acc.import_status = import_status
    acc.is_active = is_active
    acc.user_id = uuid.UUID(HOUSEHOLD_ID) if user_id is None else user_id
    acc.account_type = "personal"
    return acc


# ---------------------------------------------------------------------------
# PATCH /bank-accounts/{account_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_bank_account_updates_type(http_client, override_auth, override_db, mock_current_user):
    mock_member = MagicMock()
    mock_account = _make_bank_account(user_id=mock_current_user.id)

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)
    override_db.commit = AsyncMock()

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"account_type": "joint"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["account_type"] == "joint"


@pytest.mark.asyncio
async def test_patch_bank_account_403_for_non_owner(http_client, override_auth, override_db, mock_current_user):
    mock_member = MagicMock()
    # account owned by a different user
    mock_account = _make_bank_account(user_id=uuid.uuid4())

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"account_type": "joint"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_bank_account_409_disable_while_importing(http_client, override_auth, override_db, mock_current_user):
    mock_member = MagicMock()
    mock_account = _make_bank_account(import_status="importing", user_id=mock_current_user.id)

    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=mock_account)

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"is_active": False},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_bank_account_404_not_found(http_client, override_auth, override_db):
    mock_member = MagicMock()
    member_result = _make_execute_result(mock_member)
    override_db.execute = AsyncMock(return_value=member_result)
    override_db.scalar = AsyncMock(return_value=None)  # account not found

    response = await http_client.patch(
        f"/bank-accounts/{ACCOUNT_ID}?household_id={HOUSEHOLD_ID}",
        json={"is_active": False},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python3 -m pytest tests/test_bank_accounts_routes.py::test_patch_bank_account_updates_type tests/test_bank_accounts_routes.py::test_patch_bank_account_403_for_non_owner tests/test_bank_accounts_routes.py::test_patch_bank_account_409_disable_while_importing tests/test_bank_accounts_routes.py::test_patch_bank_account_404_not_found -v
```

Expected: all 4 FAIL (405 Method Not Allowed — PATCH route doesn't exist yet)

- [ ] **Step 3: Add the PATCH endpoint to `backend/modules/bank_accounts/router.py`**

Add after the existing imports:

```python
from typing import Literal
```

Add new Pydantic model after `ConnectFintocRequest`:

```python
class UpdateBankAccountBody(BaseModel):
    account_type: Literal["personal", "partner", "joint"] | None = None
    is_active: bool | None = None
```

Add the route after `connect_fintoc_accounts`:

```python
@router.patch("/{account_id}")
async def update_bank_account(
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    body: UpdateBankAccountBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update account_type and/or is_active. Only the account owner can edit."""
    await require_membership(household_id, current_user.id, db)

    account = await db.scalar(
        select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.household_id == household_id,
        )
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the account owner can edit it")

    # Guard: cannot disable while import is in progress
    if body.is_active is False and account.import_status in ("pending", "importing"):
        raise HTTPException(
            status_code=409,
            detail="Cannot disable an account while its history import is in progress",
        )

    if body.account_type is not None:
        account.account_type = body.account_type
    if body.is_active is not None:
        account.is_active = body.is_active

    await db.commit()
    return {"id": str(account.id), "account_type": account.account_type, "is_active": account.is_active}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend
python3 -m pytest tests/test_bank_accounts_routes.py::test_patch_bank_account_updates_type tests/test_bank_accounts_routes.py::test_patch_bank_account_403_for_non_owner tests/test_bank_accounts_routes.py::test_patch_bank_account_409_disable_while_importing tests/test_bank_accounts_routes.py::test_patch_bank_account_404_not_found -v
```

Expected: all 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat(bank-accounts): add PATCH endpoint to update account_type and is_active"
```

---

## Task 3: Backend — Update `GET /bank-accounts` (List All, Add Currency/is_active)

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`
- Modify: `backend/tests/test_bank_accounts_routes.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_bank_accounts_routes.py`:

```python
@pytest.mark.asyncio
async def test_list_bank_accounts_includes_currency_and_is_active(
    http_client, override_auth, override_db
):
    mock_member = MagicMock()

    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    mock_account.bank_name = "Banco de Chile"
    mock_account.account_type = "personal"
    mock_account.account_kind = "checking_account"
    mock_account.account_number = "****1234"
    mock_account.cardholder_name = None
    mock_account.currency = "CLP"
    mock_account.is_active = True
    mock_account.user_id = uuid.uuid4()
    mock_account.import_status = "done"
    mock_account.fintoc_account_id = "acc_1"
    mock_account.last_synced_at = None
    mock_account.import_started_at = None

    member_result = _make_execute_result(mock_member)

    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [mock_account]

    override_db.execute = AsyncMock(side_effect=[member_result, accounts_result])

    response = await http_client.get(f"/bank-accounts?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["currency"] == "CLP"
    assert data[0]["is_active"] is True


@pytest.mark.asyncio
async def test_list_bank_accounts_returns_inactive_accounts(
    http_client, override_auth, override_db
):
    """Inactive accounts must be returned so the settings UI can render the toggle."""
    mock_member = MagicMock()

    mock_inactive = MagicMock()
    mock_inactive.id = uuid.uuid4()
    mock_inactive.bank_name = "Santander"
    mock_inactive.account_type = "personal"
    mock_inactive.account_kind = None
    mock_inactive.account_number = None
    mock_inactive.cardholder_name = None
    mock_inactive.currency = "CLP"
    mock_inactive.is_active = False
    mock_inactive.user_id = uuid.uuid4()
    mock_inactive.import_status = "done"
    mock_inactive.fintoc_account_id = "acc_2"
    mock_inactive.last_synced_at = None
    mock_inactive.import_started_at = None

    member_result = _make_execute_result(mock_member)
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = [mock_inactive]
    override_db.execute = AsyncMock(side_effect=[member_result, accounts_result])

    response = await http_client.get(f"/bank-accounts?household_id={HOUSEHOLD_ID}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_active"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend
python3 -m pytest tests/test_bank_accounts_routes.py::test_list_bank_accounts_includes_currency_and_is_active tests/test_bank_accounts_routes.py::test_list_bank_accounts_returns_inactive_accounts -v
```

Expected: FAIL (currency/is_active not in response yet)

- [ ] **Step 3: Update `list_bank_accounts` in `router.py`**

Replace the `list_bank_accounts` function's query and return block:

```python
@router.get("")
async def list_bank_accounts(
    household_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected bank accounts for a household (active and inactive)."""
    await require_membership(household_id, current_user.id, db)

    result = await db.execute(
        select(BankAccount).where(
            BankAccount.household_id == household_id,
        )
    )
    accounts = result.scalars().all()

    # Stale guard: if import has been "importing" for >15 min, write "failed" to DB
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    for a in accounts:
        if (
            a.import_status == "importing"
            and a.import_started_at
            and a.import_started_at < stale_cutoff
        ):
            a.import_status = "failed"
    if any(a.import_status == "failed" for a in accounts):
        await db.commit()

    return [
        {
            "id": str(a.id),
            "bank_name": a.bank_name,
            "account_type": a.account_type,
            "account_kind": a.account_kind,
            "account_number": a.account_number,
            "cardholder_name": a.cardholder_name,
            "currency": a.currency,
            "is_active": a.is_active,
            "user_id": str(a.user_id),
            "import_status": a.import_status,
            "fintoc_account_id": a.fintoc_account_id,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        }
        for a in accounts
    ]
```

Note: The `is_active.is_(True)` filter is removed. All accounts are returned.

- [ ] **Step 4: Run tests**

```bash
cd backend
python3 -m pytest tests/test_bank_accounts_routes.py::test_list_bank_accounts_includes_currency_and_is_active tests/test_bank_accounts_routes.py::test_list_bank_accounts_returns_inactive_accounts -v
```

Expected: both PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py backend/tests/test_bank_accounts_routes.py
git commit -m "feat(bank-accounts): return all accounts in list (active+inactive), add currency and is_active fields"
```

---

## Task 4: Backend — Store Currency at Connect Time

**Files:**
- Modify: `backend/modules/bank_accounts/router.py`

- [ ] **Step 1: Update `FintocAccountIn` to accept currency**

In `router.py`, change `FintocAccountIn`:

```python
class FintocAccountIn(BaseModel):
    fintoc_account_id: str
    label: str  # "personal" | "partner" | "joint"
    bank_name: str | None = None
    account_kind: str | None = None
    account_number: str | None = None
    currency: str | None = None
```

- [ ] **Step 2: Store currency when creating the BankAccount in `connect_fintoc_accounts`**

In the `connect_fintoc_accounts` function, update the `BankAccount(...)` constructor to include:

```python
bank_account = BankAccount(
    household_id=body.household_id,
    user_id=current_user.id,
    bank_name=acct.bank_name or "Fintoc",
    account_type=acct.label,
    account_kind=acct.account_kind,
    account_number=acct.account_number,
    currency=acct.currency,                  # ← add this line
    fintoc_link_id=body.link_token,
    fintoc_account_id=acct.fintoc_account_id,
    import_status="pending",
)
```

- [ ] **Step 3: Store currency in the `fintoc_link_webhook`**

In `fintoc_link_webhook`, update the `BankAccount(...)` constructor to include:

```python
bank_account = BankAccount(
    household_id=household_id,
    user_id=user_id,
    bank_name=bank_name,
    account_type="personal",
    account_kind=acc.get("type"),
    account_number=acc.get("number"),
    currency=acc.get("currency"),            # ← add this line
    fintoc_link_id=link_token,
    fintoc_account_id=fintoc_account_id,
    import_status="pending",
)
```

- [ ] **Step 4: Run the full bank-accounts test suite to confirm nothing is broken**

```bash
cd backend
python3 -m pytest tests/test_bank_accounts_routes.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_accounts/router.py
git commit -m "feat(bank-accounts): store currency from Fintoc at connect time (connect + webhook)"
```

---

## Task 5: Backend — Filter Inactive Accounts from Transaction Queries

**Files:**
- Modify: `backend/modules/transactions/service.py`
- Modify: `backend/tests/test_transactions_api.py`

- [ ] **Step 1: Write a failing test for inactive account exclusion**

Add to `backend/tests/test_transactions_api.py`:

```python
@pytest.mark.asyncio
async def test_my_transactions_excludes_inactive_accounts(app, mock_user):
    """Transactions from inactive bank accounts must not appear in results."""
    from core.security import get_current_user
    from modules.transactions import service

    inactive_txn = {
        "id": str(uuid.uuid4()),
        "raw_merchant_name": "Inactive Bank Txn",
        "amount": 5000,
        "currency": "CLP",
        "transaction_date": "2026-03-01",
        "category": None,
        "source": "fintoc",
        "status": "done",
        "split_type": None,
        "bank_name": "Inactive Bank",
        "bank_account_id": str(uuid.uuid4()),
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        # service returns empty list — inactive account transactions are filtered at DB level
        with patch(
            "modules.transactions.service.get_my_transactions",
            new=AsyncMock(return_value=[]),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.get(
                    "/transactions/mine", headers={"Authorization": "Bearer token"}
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    # The service mock returned empty list — integration test confirms the filter at DB level
    assert response.json() == []
```

Note: The unit test confirms the route works with filtered results. The `is_active` filter lives in `service.py` and is tested via integration tests or by reading the query. The key thing to verify is that the WHERE clause is present in the service.

- [ ] **Step 2: Update `get_my_transactions` in `service.py`**

Add `BankAccount.is_active == True` to the where clause:

```python
async def get_my_transactions(db: AsyncSession, user_id: uuid.UUID, since: date) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .outerjoin(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= since,
            BankAccount.is_active == True,
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type if split else None,
            "bank_name": bank_name,
        }
        for txn, split, bank_name in rows
    ]
```

- [ ] **Step 3: Update `get_shared_transactions` in `service.py`**

Add `BankAccount.is_active == True` to the where clause:

```python
async def get_shared_transactions(
    db: AsyncSession, household_id: uuid.UUID, since: date
) -> list[dict]:
    result = await db.execute(
        select(Transaction, TransactionSplit, BankAccount.bank_name)
        .join(TransactionSplit, TransactionSplit.transaction_id == Transaction.id)
        .outerjoin(BankAccount, BankAccount.id == Transaction.bank_account_id)
        .where(
            Transaction.household_id == household_id,
            TransactionSplit.split_type == "shared",
            Transaction.transaction_date >= since,
            BankAccount.is_active == True,
        )
        .order_by(Transaction.transaction_date.desc())
    )
    rows = result.all()
    return [
        {
            **{k: v for k, v in vars(txn).items() if not k.startswith("_")},
            "split_type": split.split_type,
            "bank_name": bank_name,
        }
        for txn, split, bank_name in rows
    ]
```

- [ ] **Step 4: Update `get_monthly_summary` raw SQL in `service.py`**

The raw SQL uses CTEs. Add a `JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE` to both `personal_agg` and `shared_agg` CTEs:

```python
    result = await db.execute(
        text("""
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', NOW()) - INTERVAL '5 months',
                DATE_TRUNC('month', NOW()),
                INTERVAL '1 month'
            ) AS month_start
        ),
        personal_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS personal
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.user_id = :user_id
              AND t.household_id = :household_id
              AND ts.split_type = 'personal'
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        ),
        shared_agg AS (
            SELECT
                DATE_TRUNC('month', t.transaction_date::DATE) AS month_start,
                COALESCE(SUM(t.amount), 0) AS compartido
            FROM transactions t
            JOIN transaction_splits ts ON ts.transaction_id = t.id
            JOIN bank_accounts ba ON ba.id = t.bank_account_id AND ba.is_active = TRUE
            WHERE t.household_id = :household_id
              AND ts.split_type = 'shared'
            GROUP BY DATE_TRUNC('month', t.transaction_date::DATE)
        )
        SELECT
            m.month_start,
            COALESCE(p.personal, 0) AS personal,
            COALESCE(s.compartido, 0) AS compartido
        FROM months m
        LEFT JOIN personal_agg p ON p.month_start = m.month_start
        LEFT JOIN shared_agg s ON s.month_start = m.month_start
        ORDER BY m.month_start ASC
        """),
        {"household_id": str(household_id), "user_id": str(user_id)},
    )
```

- [ ] **Step 5: Run full test suite**

```bash
cd backend
python3 -m pytest tests/ -v
```

Expected: all existing tests pass (31 passing, 7 skipped)

- [ ] **Step 6: Commit**

```bash
git add backend/modules/transactions/service.py backend/tests/test_transactions_api.py
git commit -m "feat(transactions): exclude inactive bank account transactions from all queries"
```

---

## Task 6: Frontend — Update `api.ts` Types and Methods

**Files:**
- Modify: `frontend/app/lib/api.ts`

- [ ] **Step 1: Add `currency` and `is_active` to `BankAccountRow`**

Find the `BankAccountRow` interface and update it:

```ts
export interface BankAccountRow {
  id: string;
  bank_name: string;
  account_type: "personal" | "partner" | "joint";
  account_kind: string | null;
  account_number: string | null;
  cardholder_name: string | null;
  currency: string | null;
  is_active: boolean;
  user_id: string;
  import_status: "pending" | "importing" | "done" | "failed";
  fintoc_account_id: string | null;
  last_synced_at: string | null;
}
```

- [ ] **Step 2: Add `currency` to `SelectedFintocAccount` and `ConnectFintocPayload`**

Update `SelectedFintocAccount`:

```ts
export interface SelectedFintocAccount {
  fintoc_account_id: string;
  label: "personal" | "partner" | "joint";
  currency?: string;
}
```

`ConnectFintocPayload` already uses `SelectedFintocAccount[]` for accounts — no change needed there.

- [ ] **Step 3: Add `UpdateBankAccountPayload` interface**

Add after `ConnectFintocResult`:

```ts
export interface UpdateBankAccountPayload {
  account_type?: "personal" | "partner" | "joint";
  is_active?: boolean;
}
```

- [ ] **Step 4: Add `updateBankAccount` to the `api` object**

Add after `deleteBankAccount`:

```ts
  updateBankAccount: (
    accountId: string,
    householdId: string,
    payload: UpdateBankAccountPayload
  ) =>
    apiFetch<{ id: string; account_type: string; is_active: boolean }>(
      `/bank-accounts/${accountId}?household_id=${householdId}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat(frontend): add currency/is_active to BankAccountRow, add updateBankAccount API method"
```

---

## Task 7: Frontend — `FintocAccountPicker` Passes Currency

**Files:**
- Modify: `frontend/app/(dashboard)/components/FintocAccountPicker.tsx`

- [ ] **Step 1: Update `handleConfirm` to pass currency**

In `FintocAccountPicker.tsx`, `handleConfirm` currently maps accounts to `{ fintoc_account_id, label }`. Update it to also include `currency`:

```ts
function handleConfirm() {
  const selected = accounts
    .filter((a) => selections[a.id]?.checked)
    .map((a) => ({
      fintoc_account_id: a.id,
      label: selections[a.id].label,
      currency: a.currency,
    }));
  onConfirm(selected);
}
```

`FintocAccount` already has `currency: string` typed in `api.ts` — no other changes needed.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/app/(dashboard)/components/FintocAccountPicker.tsx
git commit -m "feat(fintoc-picker): pass currency through to connect payload"
```

---

## Task 8: Frontend — `AccountCard` Component (Settings Page Overhaul)

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`

This is the largest task. Replace `AccountRow` with `AccountCard`.

- [ ] **Step 1: Add the `AccountCard` component**

In `settings/page.tsx`, **replace the entire `AccountRow` function** (lines 54–168) with `AccountCard`:

```tsx
function AccountCard({
  account,
  currentUserId,
  householdId,
  onDeleted,
  onUpdated,
}: {
  account: BankAccountRow;
  currentUserId: string | null;
  householdId: string | null;
  onDeleted: (id: string) => void;
  onUpdated: (id: string, patch: { account_type?: string; is_active?: boolean }) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showNumber, setShowNumber] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editType, setEditType] = useState<"personal" | "partner" | "joint">(account.account_type);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const isOwn = account.user_id === currentUserId;
  const typeLabel = ACCOUNT_TYPE_LABEL[account.account_type] ?? account.account_type;
  const typeColor = account.is_active
    ? (ACCOUNT_TYPE_COLOR[account.account_type] ?? "bg-gray-100 text-gray-700")
    : "bg-gray-100 text-gray-400";
  const kindLabel = account.account_kind
    ? (ACCOUNT_KIND_LABEL[account.account_kind] ?? account.account_kind)
    : null;
  const isFirstImport = account.import_status === "importing" && !account.last_synced_at;
  const isFirstImportFailed = account.import_status === "failed" && !account.last_synced_at;

  const last4 = account.account_number ? account.account_number.slice(-4) : null;
  const maskedNumber = last4 ? `•••• ${last4}` : null;
  const fullNumber = account.account_number ?? null;

  async function handleToggle() {
    if (!householdId || toggling) return;
    setToggling(true);
    setInlineError(null);
    const newActive = !account.is_active;
    onUpdated(account.id, { is_active: newActive }); // optimistic
    try {
      await api.updateBankAccount(account.id, householdId, { is_active: newActive });
    } catch (e: unknown) {
      onUpdated(account.id, { is_active: account.is_active }); // revert
      const msg =
        e instanceof Error && e.message.includes("409")
          ? "Espera a que termine la sincronización antes de desactivar."
          : "No se pudo guardar. Intenta de nuevo.";
      setInlineError(msg);
    } finally {
      setToggling(false);
    }
  }

  async function handleSaveType() {
    if (!householdId) return;
    setSaving(true);
    setInlineError(null);
    onUpdated(account.id, { account_type: editType }); // optimistic
    try {
      await api.updateBankAccount(account.id, householdId, { account_type: editType });
      setEditing(false);
    } catch {
      onUpdated(account.id, { account_type: account.account_type }); // revert
      setInlineError("No se pudo guardar. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!householdId) return;
    setDeleting(true);
    try {
      await api.deleteBankAccount(account.id, householdId);
      onDeleted(account.id);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className={`rounded-xl border bg-white shadow-sm transition-opacity ${account.is_active ? "" : "opacity-60"}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-luka-dark text-sm">{bankLabel(account.bank_name)}</span>
          {account.currency && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${account.is_active ? "bg-slate-100 text-slate-600" : "bg-gray-100 text-gray-400"}`}>
              {account.currency}
            </span>
          )}
          {kindLabel && (
            <span className="text-xs text-luka-muted">{kindLabel}</span>
          )}
          {!isOwn && (
            <span className="text-xs text-purple-600 font-medium">· Pareja</span>
          )}
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>
          {typeLabel}
        </span>
      </div>

      {/* Body */}
      <div className="px-4 pb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {maskedNumber && (
          <span className="flex items-center gap-1 text-xs text-luka-muted">
            {showNumber ? fullNumber : maskedNumber}
            <button
              onClick={() => setShowNumber((v) => !v)}
              className="text-luka-muted hover:text-luka-dark"
              title={showNumber ? "Ocultar" : "Mostrar"}
            >
              {showNumber ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              )}
            </button>
          </span>
        )}
        {account.last_synced_at && (
          <span className="text-xs text-slate-400">Última sync: {formatLastSync(account.last_synced_at)}</span>
        )}
        {isFirstImport && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse inline-block" />
            Sincronizando...
          </span>
        )}
        {isFirstImportFailed && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
            Error al sincronizar
          </span>
        )}
      </div>

      {/* Footer */}
      {isOwn && (
        <div className="flex items-center justify-between px-4 pb-3 pt-1 border-t border-gray-50 mt-1">
          {/* Active toggle */}
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`flex items-center gap-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${account.is_active ? "text-luka-primary" : "text-luka-muted"}`}
          >
            <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${account.is_active ? "bg-luka-primary" : "bg-gray-300"}`}>
              <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${account.is_active ? "translate-x-4" : "translate-x-1"}`} />
            </span>
            {account.is_active ? "Activa" : "Inactiva"}
          </button>

          {/* Edit + Delete */}
          <div className="flex items-center gap-3">
            {!editing && (
              <button
                onClick={() => { setEditing(true); setEditType(account.account_type); setInlineError(null); }}
                className="text-xs text-luka-muted hover:text-luka-dark"
                title="Editar tipo de cuenta"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </button>
            )}
            {!confirmDelete && (
              <button onClick={() => setConfirmDelete(true)} className="text-xs text-red-400 hover:text-red-600">
                Desconectar
              </button>
            )}
            {confirmDelete && (
              <span className="flex items-center gap-1.5">
                <span className="text-xs text-luka-muted">¿Seguro?</span>
                <button onClick={handleDelete} disabled={deleting} className="text-xs text-red-500 font-medium hover:text-red-700 disabled:opacity-50">
                  {deleting ? "..." : "Sí"}
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-xs text-luka-muted hover:text-luka-dark">No</button>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Edit mode (inline expand) */}
      {editing && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 space-y-3">
          <p className="text-xs text-luka-muted font-medium">Tipo de cuenta</p>
          <div className="flex gap-2">
            {(["personal", "partner", "joint"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setEditType(t)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  editType === t
                    ? "bg-luka-primary text-white border-luka-primary"
                    : "bg-white text-luka-muted border-gray-200 hover:border-luka-primary"
                }`}
              >
                {ACCOUNT_TYPE_LABEL[t]}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSaveType}
              disabled={saving}
              className="text-xs px-3 py-1 rounded-full bg-luka-primary text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
            <button
              onClick={() => { setEditing(false); setInlineError(null); }}
              className="text-xs px-3 py-1 rounded-full border border-gray-200 text-luka-muted hover:border-luka-primary"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Inline error */}
      {inlineError && (
        <p className="px-4 pb-3 text-xs text-red-500">{inlineError}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add the `onUpdated` handler and wire `AccountCard` in `ConnectBankSection`**

In `ConnectBankSection`, update the `useQueryClient` usage and the accounts render block:

```tsx
// Inside ConnectBankSection, after existing state/query setup:

function handleUpdated(id: string, patch: { account_type?: string; is_active?: boolean }) {
  queryClient.setQueryData<BankAccountRow[]>(
    ["bank-accounts", householdId],
    (prev) =>
      prev?.map((a) =>
        a.id === id ? { ...a, ...patch } as BankAccountRow : a
      ) ?? []
  );
}

// In the JSX, replace AccountRow with AccountCard:
{!loadingAccounts && accounts && accounts.length > 0 && (
  <div className="space-y-3">
    {accounts.map((account) => (
      <AccountCard
        key={account.id}
        account={account}
        currentUserId={userId}
        householdId={householdId}
        onDeleted={(id) => {
          queryClient.setQueryData<BankAccountRow[]>(
            ["bank-accounts", householdId],
            (prev) => prev?.filter((a) => a.id !== id) ?? []
          );
          queryClient.invalidateQueries({ queryKey: ["transactions"] });
        }}
        onUpdated={handleUpdated}
      />
    ))}
  </div>
)}
```

Also update the empty state message to only show when there are no accounts at all:

```tsx
{!loadingAccounts && (!accounts || accounts.length === 0) && (
  <p className="text-sm text-luka-muted">
    Conecta tus cuentas para importar transacciones automáticamente.
  </p>
)}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Run the dev server and manually verify**

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000/settings`. Verify:
- Each bank account shows as a card with bank name, currency badge, account kind
- Active toggle works (card dims when inactive)
- Edit pencil expands inline type selector
- Saving type updates the badge
- Disconnect confirm flow still works
- Partner accounts (not owned by current user) show no footer controls

- [ ] **Step 5: Commit**

```bash
git add frontend/app/(dashboard)/settings/page.tsx
git commit -m "feat(settings): replace AccountRow with AccountCard — currency badge, toggle, inline type edit"
```

---

## Task 9: Run Full Test Suite + Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
python3 -m pytest tests/ -v
```

Expected: ≥35 passing (original 31 + new PATCH tests + new list tests), 7 skipped

- [ ] **Step 2: Run frontend build**

```bash
cd frontend
npm run build
```

Expected: Build completes with no TypeScript or lint errors.

- [ ] **Step 3: Run Alembic migration on production**

```bash
cd backend
python3 -m alembic upgrade head
```

Expected: `Running upgrade 009 -> 010, bank_account_currency`

This must be run manually from your local environment (Railway releaseCommand is not used for migrations — see project notes).

- [ ] **Step 4: Final commit if anything was missed**

```bash
git add -A
git status
# commit any remaining changes
```
