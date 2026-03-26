# Luka Connect — Account Detection, Balances & Transaction Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-create bank accounts from Luka Connect scrape data, store balances, link transactions to accounts, and surface financial position on the frontend with currency toggle.

**Architecture:** Webhook-driven — all account creation, balance updates, and transaction linking happen inside the existing webhook handler before/during movement processing. No new background jobs or tables. Frontend adds a master CLP/USD toggle that filters both balance cards and the transaction list.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Alembic (migrations), Next.js 14 + React Query (frontend), Tailwind CSS + shadcn/ui (styling)

**Spec:** `docs/superpowers/specs/2026-03-26-luka-connect-accounts-balances-design.md`

---

## File Map

### Backend — Create / Modify

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/alembic/versions/018_account_balances.py` | Create | Migration: add `account_name`, `balance_current`, `balance_limit`, `last_synced_at` to `bank_accounts` |
| `backend/modules/households/models.py` | Modify (lines 41-59) | Add 4 new columns to `BankAccount` model |
| `backend/modules/bank_connect/router.py` | Modify (lines 45-51, 163-174, 177-259) | Update `ConnectCallback` model, change webhook guard, integrate `_ensure_accounts()`, update `ba_map` usage |
| `backend/modules/bank_connect/accounts.py` | Create | New module: `_ensure_accounts()` function — account creation, dedup, balance updates |
| `backend/modules/bank_connect/service.py` | Modify (lines 79-112) | Add `days_back` parameter to `trigger_sync()` |
| `backend/modules/bank_accounts/router.py` | Modify (lines 34-47) | Add new fields to GET response |

### Frontend — Modify

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/app/lib/api.ts` | Modify (lines 176-189, 334-335) | Update `BankAccountRow` type, add `days_back` to `manualSync` |
| `frontend/app/(dashboard)/transactions/page.tsx` | Modify (lines 28-140, 242-300) | Rewrite `SummaryBar` with currency toggle + 4 cards, add currency filter |
| `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx` | Modify | Add "Cuentas Detectadas" section with hide/show toggle |

---

## Task 1: Database Migration

**Files:**
- Create: `backend/alembic/versions/018_account_balances.py`
- Modify: `backend/modules/households/models.py:41-59`

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/018_account_balances.py
"""Add account_name, balance columns, and last_synced_at to bank_accounts."""

revision = "018"
down_revision = "017"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("bank_accounts", sa.Column("account_name", sa.String(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_current", sa.BigInteger(), nullable=True))
    op.add_column("bank_accounts", sa.Column("balance_limit", sa.BigInteger(), nullable=True))
    op.add_column(
        "bank_accounts",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "last_synced_at")
    op.drop_column("bank_accounts", "balance_limit")
    op.drop_column("bank_accounts", "balance_current")
    op.drop_column("bank_accounts", "account_name")
```

- [ ] **Step 2: Update BankAccount model**

Add these 4 columns to `backend/modules/households/models.py` inside the `BankAccount` class, after `currency` (line 57) and before `is_active` (line 58):

```python
    account_name: Mapped[str | None] = mapped_column(String, nullable=True)
    balance_current: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    balance_limit: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Note: Add `import sqlalchemy as sa` at the top of the file (or use `from sqlalchemy import BigInteger`).

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: Migration applies cleanly, 4 new columns visible in `bank_accounts` table.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/018_account_balances.py backend/modules/households/models.py
git commit -m "feat: add account_name, balance_current, balance_limit, last_synced_at to bank_accounts (migration 018)"
```

---

## Task 2: Account Auto-Creation Module (`_ensure_accounts`)

**Files:**
- Create: `backend/modules/bank_connect/accounts.py`

- [ ] **Step 1: Create the accounts module**

```python
# backend/modules/bank_connect/accounts.py
"""Auto-create bank accounts from Luka Connect scrape data and update balances."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import BankAccount, HouseholdMember

# Map bank codes to display names
BANK_NAMES = {
    "BANCO_CHILE": "Banco de Chile",
    "BANCO_ESTADO": "BancoEstado",
    "BCI": "BCI",
    "SANTANDER": "Santander",
}

# Map allBalances keys to (account_name, account_kind, currency)
ALL_BALANCES_KEY_MAP = {
    "CUENTA_CORRIENTE_CLP": ("Cuenta Corriente Moneda Local", "checking_account", "CLP"),
    "CUENTA_CORRIENTE_USD": ("Cuenta Corriente M/E", "checking_account", "USD"),
    "LINEA_CREDITO_CLP": ("Línea de Crédito", "line_of_credit", "CLP"),
}


async def ensure_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_code: str,
    movements: list[dict] | None,
    all_balances: dict | None,
    credit_cards: list[dict] | None,
) -> dict[tuple[str, str], uuid.UUID]:
    """
    Auto-create/update bank accounts from scrape data. Returns ba_map:
    dict[(account_name, currency) -> bank_account_id]
    """
    # Resolve household
    hm_result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == user_id)
    )
    household_id = hm_result.scalar_one_or_none()
    if not household_id:
        return {}

    bank_name = BANK_NAMES.get(bank_code, bank_code)
    now = datetime.now(timezone.utc)

    # Collect all accounts to ensure: list of dicts with account fields
    accounts_to_ensure: list[dict] = []

    # --- Step 1: Accounts from movements ---
    if movements:
        seen_movement_accounts: set[tuple[str, str]] = set()
        for mov in movements:
            acct_name = mov.get("accountName")
            currency = mov.get("currency", "CLP")
            if not acct_name or (acct_name, currency) in seen_movement_accounts:
                continue
            seen_movement_accounts.add((acct_name, currency))

            # Only create accounts for source="account" movements
            # CC movements use the checking accountNumber, not a real CC account
            if mov.get("source") == "account":
                accounts_to_ensure.append({
                    "account_name": acct_name,
                    "account_number": mov.get("accountNumber"),
                    "account_kind": "checking_account",
                    "currency": currency,
                })

    # --- Step 2: Accounts from creditCards[] ---
    if credit_cards:
        for card in credit_cards:
            label = card.get("label", "")
            # Extract account number from label (e.g., "Visa Signature ****5032" -> "****5032")
            parts = label.split()
            acct_number = parts[-1] if parts else None

            national = card.get("national")
            if national and isinstance(national, dict) and "total" in national:
                accounts_to_ensure.append({
                    "account_name": f"{label} Nacional",
                    "account_number": acct_number,
                    "account_kind": "credit_card",
                    "currency": "CLP",
                    "balance_current": -(national["total"] - national.get("available", 0)),
                    "balance_limit": national["total"],
                })

            international = card.get("international")
            if international and isinstance(international, dict) and "total" in international:
                accounts_to_ensure.append({
                    "account_name": f"{label} Internacional",
                    "account_number": acct_number,
                    "account_kind": "credit_card",
                    "currency": international.get("currency", "USD"),
                    "balance_current": -(international["total"] - international.get("available", 0)),
                    "balance_limit": international["total"],
                })

    # --- Step 3: Line of credit from allBalances ---
    if all_balances and "LINEA_CREDITO_CLP" in all_balances:
        val = all_balances["LINEA_CREDITO_CLP"]
        accounts_to_ensure.append({
            "account_name": "Línea de Crédito",
            "account_number": None,
            "account_kind": "line_of_credit",
            "currency": "CLP",
            "balance_current": val,
            "balance_limit": val,
        })

    # --- Dedup + create/update ---
    # Fetch existing accounts for this user+bank
    existing_result = await db.execute(
        select(BankAccount).where(
            BankAccount.user_id == user_id,
            BankAccount.bank_name == bank_name,
        )
    )
    existing_accounts = list(existing_result.scalars().all())
    existing_map: dict[tuple[str, str], BankAccount] = {
        (a.account_name, a.currency): a
        for a in existing_accounts
        if a.account_name and a.currency
    }

    ba_map: dict[tuple[str, str], uuid.UUID] = {}

    for acct_data in accounts_to_ensure:
        key = (acct_data["account_name"], acct_data["currency"])
        existing = existing_map.get(key)

        if existing:
            # Update balance if we have fresh data
            if "balance_current" in acct_data:
                existing.balance_current = acct_data["balance_current"]
                existing.balance_limit = acct_data.get("balance_limit")
                existing.last_synced_at = now
            ba_map[key] = existing.id
        else:
            # Create new account
            new_account = BankAccount(
                household_id=household_id,
                user_id=user_id,
                bank_name=bank_name,
                account_name=acct_data["account_name"],
                account_number=acct_data.get("account_number"),
                account_kind=acct_data["account_kind"],
                currency=acct_data["currency"],
                account_type="personal",
                balance_current=acct_data.get("balance_current"),
                balance_limit=acct_data.get("balance_limit"),
                last_synced_at=now if "balance_current" in acct_data else None,
            )
            db.add(new_account)
            await db.flush()  # Get the ID without committing
            ba_map[key] = new_account.id
            existing_map[key] = new_account

    # --- Update checking account balances from allBalances ---
    if all_balances:
        for bal_key, (acct_name, _, currency) in ALL_BALANCES_KEY_MAP.items():
            if bal_key in all_balances and bal_key != "LINEA_CREDITO_CLP":
                key = (acct_name, currency)
                acct = existing_map.get(key)
                if acct:
                    acct.balance_current = all_balances[bal_key]
                    acct.balance_limit = None
                    acct.last_synced_at = now

    # Also add any existing accounts (from previous syncs) to ba_map
    for (name, curr), acct in existing_map.items():
        if (name, curr) not in ba_map:
            ba_map[(name, curr)] = acct.id

    return ba_map
```

- [ ] **Step 2: Verify the module loads**

```bash
cd backend && python -c "from modules.bank_connect.accounts import ensure_accounts; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/modules/bank_connect/accounts.py
git commit -m "feat: add _ensure_accounts() for auto-creating bank accounts from scrape data"
```

---

## Task 3: Update Webhook Handler

**Files:**
- Modify: `backend/modules/bank_connect/router.py:45-51, 163-174, 177-259`

- [ ] **Step 1: Update ConnectCallback model (line 45-51)**

Replace the `ConnectCallback` class:

```python
class ConnectCallback(BaseModel):
    jobId: str
    status: str
    movements: list[dict] | None = None
    allBalances: dict | None = None  # Was "balances" — matches scraper field name
    creditCards: list[dict] | None = None
    error: str | None = None
```

- [ ] **Step 2: Update webhook handler (lines 163-174)**

Add import at top of file:
```python
from modules.bank_connect.accounts import ensure_accounts
```

Replace the `if body.status == "completed" and body.movements:` block (lines 163-174) with:

```python
    if body.status == "completed":
        # Always run account creation/balance updates, even with no movements
        ba_map = await ensure_accounts(
            db=db,
            user_id=cred.user_id,
            bank_code=cred.bank_code,
            movements=body.movements,
            all_balances=body.allBalances,
            credit_cards=body.creditCards,
        )

        created, enriched, skipped = 0, 0, 0
        if body.movements:
            created, enriched, skipped = await _process_movements(
                db=db, cred=cred, movements=body.movements, ba_map=ba_map
            )

        cred.last_sync_at = datetime.now(timezone.utc)
        cred.last_sync_status = "success"
        cred.current_job_id = None
        cred.next_sync_at = _random_next_sync()
        await db.commit()
        return {"status": "ok", "created": created, "enriched": enriched, "skipped": skipped}
```

- [ ] **Step 3: Update `_process_movements()` signature and body (lines 177-259)**

Change the function signature to accept `ba_map`:

```python
async def _process_movements(
    db: AsyncSession, cred: BankCredential, movements: list[dict],
    ba_map: dict[tuple[str, str], uuid.UUID],
) -> tuple[int, int, int]:
```

Remove the old `ba_map` construction (lines 193-198 — the `ba_result` query and `ba_map = {row[1]: row[0]...}` block). The household_id lookup (lines 186-191) stays.

Update the `ba_id` lookup (line 246) and email enrichment (lines 242-244):

```python
        if email_txn:
            email_txn.transaction_date = mov_date
            # Also link to bank account
            email_txn.bank_account_id = ba_map.get(
                (mov.get("accountName", ""), mov.get("currency", "CLP"))
            )
            enriched += 1
        else:
            # For CC movements, fall back to first CC account for that currency
            acct_name = mov.get("accountName", "")
            currency = mov.get("currency", "CLP")
            source = mov.get("source", "")

            if source in ("credit_card_billed", "credit_card_unbilled"):
                ba_id = _find_cc_account(ba_map, currency)
            else:
                ba_id = ba_map.get((acct_name, currency))

            txn_data = map_movement_to_transaction(
                movement=mov,
                user_id=str(cred.user_id),
                household_id=str(household_id),
                bank_account_id=str(ba_id) if ba_id else None,
            )
            txn = Transaction(**txn_data)
            db.add(txn)
            created += 1
```

Remove the final `await db.commit()` at line 258 — the caller (webhook handler) now commits.

Add a helper function before `_process_movements`:

```python
def _find_cc_account(
    ba_map: dict[tuple[str, str], uuid.UUID], currency: str
) -> uuid.UUID | None:
    """Find the first credit card account for a given currency."""
    for (name, curr), acct_id in ba_map.items():
        if curr == currency and ("Nacional" in name or "Internacional" in name):
            return acct_id
    return None
```

- [ ] **Step 4: Verify backend starts**

```bash
cd backend && python -c "from modules.bank_connect.router import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/bank_connect/router.py
git commit -m "feat: integrate account auto-creation + balance updates into webhook handler"
```

---

## Task 4: Update `trigger_sync` with `days_back`

**Files:**
- Modify: `backend/modules/bank_connect/service.py:79-112`
- Modify: `backend/modules/bank_connect/router.py:85-97`

- [ ] **Step 1: Update `trigger_sync` in service.py**

Change function signature (line 79-84):

```python
async def trigger_sync(
    db: AsyncSession,
    cred: BankCredential,
    days_back: int = 4,
    callback_url: str | None = None,
) -> dict:
```

Update the payload construction (lines 96-104):

```python
    payload = {
        "bank": cred.bank_code,
        "rut": rut,
        "password": password,
        "days_back": days_back,
        "jobId": job_id,
    }
```

(Remove the `mode` key from the payload.)

- [ ] **Step 2: Update callers in router.py**

In `connect_bank` (line 70), change to:
```python
    await trigger_sync(db=db, cred=cred, days_back=90, callback_url=callback_url)
```

In `manual_sync` (line 96), add `days_back` query param and pass it:
```python
@router.post("/sync")
async def manual_sync(
    bank_code: str,
    days_back: int = 4,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync (async with webhook callback)."""
    cred = await get_connection_status(db=db, user_id=str(user.id), bank_code=bank_code)
    if not cred:
        raise HTTPException(status_code=404, detail="No connection found for this bank")
    callback_url = f"{settings.backend_public_url}/bank-connect/webhooks/luka-connect"
    result = await trigger_sync(db=db, cred=cred, days_back=days_back, callback_url=callback_url)
    return result
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/bank_connect/service.py backend/modules/bank_connect/router.py
git commit -m "feat: add days_back parameter to trigger_sync, replace mode"
```

---

## Task 5: Update Bank Accounts API Response

**Files:**
- Modify: `backend/modules/bank_accounts/router.py:34-47`

- [ ] **Step 1: Add new fields to GET response**

Update the return dict in `list_bank_accounts` (lines 34-46):

```python
    return [
        {
            "id": str(a.id),
            "bank_name": a.bank_name,
            "account_type": a.account_type,
            "account_kind": a.account_kind,
            "account_name": a.account_name,
            "account_number": a.account_number,
            "cardholder_name": a.cardholder_name,
            "currency": a.currency,
            "is_active": a.is_active,
            "user_id": str(a.user_id),
            "balance_current": a.balance_current,
            "balance_limit": a.balance_limit,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        }
        for a in accounts
    ]
```

- [ ] **Step 2: Commit**

```bash
git add backend/modules/bank_accounts/router.py
git commit -m "feat: include account_name, balance_current, balance_limit, last_synced_at in bank accounts API"
```

---

## Task 6: Frontend — Update API Types

**Files:**
- Modify: `frontend/app/lib/api.ts:176-189, 334-335`

- [ ] **Step 1: Update BankAccountRow interface (lines 176-189)**

```typescript
export interface BankAccountRow {
  id: string;
  bank_name: string;
  account_type: "personal" | "partner" | "joint";
  account_kind: string | null;
  account_name: string | null;
  account_number: string | null;
  cardholder_name: string | null;
  currency: string | null;
  is_active: boolean;
  user_id: string;
  last_synced_at: string | null;
  balance_current: number | null;
  balance_limit: number | null;
}
```

- [ ] **Step 2: Update manualSync to accept days_back (line 334-335)**

```typescript
  manualSync: (bankCode: string, daysBack: number = 4) =>
    apiFetch(`/bank-connect/sync?bank_code=${bankCode}&days_back=${daysBack}`, { method: "POST" }),
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add app/lib/api.ts
git commit -m "feat: update BankAccountRow type with balance fields, add days_back to manualSync"
```

---

## Task 7: Frontend — Transactions Page Balance Cards + Currency Toggle

**Files:**
- Modify: `frontend/app/(dashboard)/transactions/page.tsx:13-140, 242-300`

- [ ] **Step 1: Add currency formatter for USD**

After the existing `formatCLP` function (line 13-15), add:

```typescript
function formatAmount(n: number, currency: string) {
  if (currency === "USD") return `US$${Math.round(n).toLocaleString("en-US")}`;
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}
```

- [ ] **Step 2: Rewrite SummaryBar with currency toggle and 4 cards**

Replace the entire `SummaryBar` component (lines 28-140) with:

```typescript
const CHECKING_KINDS = new Set(["checking_account", "savings_account", "sight_account"]);
const CC_KIND = "credit_card";
const LOC_KIND = "line_of_credit";

interface SummaryBarProps {
  accounts: BankAccountRow[];
  selectedCurrency: string;
  onCurrencyChange: (c: string) => void;
}

function SummaryBar({ accounts, selectedCurrency, onCurrencyChange }: SummaryBarProps) {
  const currencies = useMemo(() => {
    const set = new Set<string>();
    accounts.forEach((a) => { if (a.currency) set.add(a.currency); });
    return Array.from(set).sort();
  }, [accounts]);

  const hasUSD = currencies.includes("USD");

  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === selectedCurrency
  );

  const checkingBalance = filtered
    .filter((a) => a.account_kind && CHECKING_KINDS.has(a.account_kind))
    .reduce((s, a) => s + (a.balance_current ?? 0), 0);

  const ccUsed = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + (a.balance_current ?? 0), 0); // Already negative

  const ccLimit = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + (a.balance_limit ?? 0), 0);

  const locBalance = filtered
    .filter((a) => a.account_kind === LOC_KIND)
    .reduce((s, a) => s + (a.balance_current ?? 0), 0);

  const hasLOC = filtered.some((a) => a.account_kind === LOC_KIND);
  const hasCC = filtered.some((a) => a.account_kind === CC_KIND);

  const netPosition = checkingBalance + locBalance + ccUsed;

  const hasAnyBalance = filtered.some((a) => a.balance_current !== null);

  const cards: Array<{
    label: string;
    value: string;
    sublabel: string;
    bg: string;
    textColor: string;
    show: boolean;
  }> = [
    {
      label: "Cuenta Corriente",
      value: hasAnyBalance ? formatAmount(checkingBalance, selectedCurrency) : "—",
      sublabel: "",
      bg: "bg-blue-50 border-blue-100",
      textColor: "text-luka-dark",
      show: true,
    },
    {
      label: "Tarjeta de Crédito",
      value: hasAnyBalance ? formatAmount(ccUsed, selectedCurrency) : "—",
      sublabel: hasAnyBalance && ccLimit > 0
        ? `gastado de ${formatAmount(ccLimit, selectedCurrency)}`
        : "",
      bg: "bg-red-50 border-red-100",
      textColor: ccUsed < 0 ? "text-red-600" : "text-luka-dark",
      show: hasCC,
    },
    {
      label: "Línea de Crédito",
      value: hasAnyBalance ? formatAmount(locBalance, selectedCurrency) : "—",
      sublabel: "disponible",
      bg: "bg-emerald-50 border-emerald-100",
      textColor: "text-luka-dark",
      show: hasLOC,
    },
    {
      label: "Posición Neta",
      value: hasAnyBalance ? formatAmount(netPosition, selectedCurrency) : "—",
      sublabel: "líquido - deuda TC",
      bg: netPosition >= 0
        ? "bg-emerald-50 border-emerald-200"
        : "bg-red-50 border-red-200",
      textColor: netPosition >= 0 ? "text-emerald-700" : "text-red-600",
      show: hasCC, // Only show if there are credit cards to compare against
    },
  ];

  const visibleCards = cards.filter((c) => c.show);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Saldos disponibles
        </span>
        <div className="flex gap-1">
          {["CLP", ...(hasUSD ? ["USD"] : [])].map((c) => (
            <button
              key={c}
              onClick={() => onCurrencyChange(c)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                selectedCurrency === c
                  ? "bg-luka-primary text-white"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
      <div className={`grid grid-cols-1 ${{ 1: "lg:grid-cols-1", 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4" }[visibleCards.length] ?? "lg:grid-cols-4"} gap-3`}>
        {visibleCards.map(({ label, value, sublabel, bg, textColor }) => (
          <div
            key={label}
            className={`rounded-xl border p-4 ${bg}`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 leading-tight">
              {label}
            </p>
            <p className={`text-lg font-bold tabular-nums truncate ${textColor}`}>
              {value}
            </p>
            {sublabel && (
              <p className="text-[10px] text-slate-400 mt-0.5">{sublabel}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add currency state and filter to TransactionsPage**

In the `TransactionsPage` component, add state (after line 248):

```typescript
  const [selectedCurrency, setSelectedCurrency] = useState<string>("CLP");
```

Update `applyFilters` (line 281) to include currency filter:

```typescript
  const applyFilters = (txns: Transaction[]) => {
    let result = txns;
    // Currency filter
    result = result.filter((t) => (t.currency ?? "CLP") === selectedCurrency);
    if (selectedMonth !== "all") result = result.filter((t) => getMonthKey(t.transaction_date) === selectedMonth);
    // ... rest unchanged
  };
```

Add `selectedCurrency` to the dependency arrays of `filteredMine`, `filteredShared`, `filteredAll` useMemos, and to the `useEffect` that resets page.

Replace the `<SummaryBar>` usage (lines 419-425):

```tsx
      <SummaryBar
        accounts={accounts}
        selectedCurrency={selectedCurrency}
        onCurrencyChange={setSelectedCurrency}
      />
```

Remove the old `periodLabel`, `summaryShared`, `isChecking`, `isCredit` helpers that are no longer used.

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: No type errors or build failures.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add app/\(dashboard\)/transactions/page.tsx
git commit -m "feat: add currency toggle + 4 balance cards (Posición Neta) to transactions page"
```

---

## Task 8: Frontend — Settings Detected Accounts

**Files:**
- Modify: `frontend/app/(dashboard)/settings/components/BankAccountsSection.tsx`

- [ ] **Step 1: Add DetectedAccountCard component**

Add a new component inside `BankAccountsSection.tsx` — a simple row for each auto-detected account:

```typescript
function DetectedAccountCard({
  account,
  householdId,
}: {
  account: BankAccountRow;
  householdId: string;
}) {
  const queryClient = useQueryClient();
  const [updating, setUpdating] = useState(false);

  const kindLabels: Record<string, string> = {
    checking_account: "Cta. Corriente",
    credit_card: "Tarjeta de Crédito",
    line_of_credit: "Línea de Crédito",
    savings_account: "Cuenta Ahorro",
  };

  async function toggleActive() {
    setUpdating(true);
    try {
      await api.updateBankAccount(account.id, householdId, {
        is_active: !account.is_active,
      });
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
    } finally {
      setUpdating(false);
    }
  }

  async function toggleType() {
    const newType = account.account_type === "joint" ? "personal" : "joint";
    setUpdating(true);
    try {
      await api.updateBankAccount(account.id, householdId, {
        account_type: newType,
      });
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
    } finally {
      setUpdating(false);
    }
  }

  const formatBalance = (val: number | null, currency: string | null) => {
    if (val === null) return "—";
    if (currency === "USD") return `US$${Math.round(val).toLocaleString("en-US")}`;
    return `$${Math.round(val).toLocaleString("es-CL")}`;
  };

  return (
    <div
      className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
        account.is_active
          ? "bg-white border-slate-100"
          : "bg-slate-50 border-slate-100 opacity-60"
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">
            {account.account_name ?? account.bank_name}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-medium text-slate-400">
              {kindLabels[account.account_kind ?? ""] ?? account.account_kind}
            </span>
            {account.currency && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                {account.currency}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right">
          <p className="text-sm font-bold tabular-nums text-slate-800">
            {formatBalance(account.balance_current, account.currency)}
          </p>
          {account.last_synced_at && (
            <p className="text-[9px] text-slate-400">
              {new Date(account.last_synced_at).toLocaleDateString("es-CL")}
            </p>
          )}
        </div>

        <button
          onClick={toggleType}
          disabled={updating}
          className={`text-[10px] font-medium px-2 py-1 rounded-md border transition-colors ${
            account.account_type === "joint"
              ? "bg-emerald-50 border-emerald-200 text-emerald-700"
              : "bg-blue-50 border-blue-200 text-blue-700"
          }`}
        >
          {account.account_type === "joint" ? "Compartida" : "Personal"}
        </button>

        <button
          onClick={toggleActive}
          disabled={updating}
          className="text-[10px] font-medium text-slate-400 hover:text-slate-600 transition-colors"
        >
          {account.is_active ? "Ocultar" : "Mostrar"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add detected accounts section to the main component**

In the main `BankAccountsSection` component, after the email-linked accounts section, add:

```tsx
      {/* Detected accounts from Luka Connect */}
      {(() => {
        // Connect-created accounts have account_name set; email-linked ones don't
        const detectedAccounts = accounts.filter((a) => a.account_name !== null);
        if (detectedAccounts.length === 0) return null;

        // Group by bank
        const byBank = new Map<string, BankAccountRow[]>();
        detectedAccounts.forEach((a) => {
          const list = byBank.get(a.bank_name) ?? [];
          list.push(a);
          byBank.set(a.bank_name, list);
        });

        return (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-700">Cuentas Detectadas</h3>
            <p className="text-xs text-slate-400">
              Cuentas creadas automáticamente al sincronizar con tu banco.
            </p>
            {Array.from(byBank.entries()).map(([bankName, bankAccounts]) => (
              <div key={bankName} className="space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                  {bankName}
                </p>
                {bankAccounts.map((a) => (
                  <DetectedAccountCard
                    key={a.id}
                    account={a}
                    householdId={householdId!}
                  />
                ))}
              </div>
            ))}
          </div>
        );
      })()}
```

Note: The exact placement depends on the current component structure. Add it after the existing email-linked accounts list, inside the same card container.

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd frontend && git add app/\(dashboard\)/settings/components/BankAccountsSection.tsx
git commit -m "feat: add Cuentas Detectadas section in settings with hide/show toggle"
```

---

## Task 9: End-to-End Verification

- [ ] **Step 1: Run backend locally**

```bash
cd backend && uvicorn main:app --reload --port 8000
```

- [ ] **Step 2: Run frontend locally**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Simulate a webhook callback**

Use the test data from `test-scraper/last_result.json` to send a POST to the webhook:

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/Finanzas Personales"
python -c "
import json, requests

with open('test-scraper/last_result.json') as f:
    data = json.load(f)

# You'll need a valid jobId from a real sync — check the DB for a current_job_id
# For manual testing, temporarily insert a test credential
print(f'Movements: {len(data.get(\"movements\", []))}')
print(f'Balances: {list(data.get(\"allBalances\", {}).keys())}')
print(f'Credit cards: {len(data.get(\"creditCards\", []))}')
"
```

- [ ] **Step 4: Verify in the browser**

1. Open the transactions page — check that the CLP/USD toggle appears
2. Check balance cards show real data (Cuenta Corriente, TC, Posición Neta)
3. Toggle to USD — verify transactions filter and balances update
4. Open settings — check "Cuentas Detectadas" section shows auto-created accounts
5. Toggle an account to "Compartida" — verify it works
6. Click "Ocultar" on an account — verify it disappears from balance cards

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Luka Connect account detection, balances, and transaction enrichment"
```

---

## Summary

| Task | Description | Estimated Steps |
|------|-------------|-----------------|
| 1 | Database migration (4 columns) | 4 |
| 2 | `_ensure_accounts()` module | 3 |
| 3 | Webhook handler integration | 5 |
| 4 | `days_back` parameter | 3 |
| 5 | Bank accounts API response | 2 |
| 6 | Frontend API types | 3 |
| 7 | Transactions page balance cards + currency toggle | 5 |
| 8 | Settings detected accounts | 4 |
| 9 | End-to-end verification | 5 |
| **Total** | | **34 steps** |
