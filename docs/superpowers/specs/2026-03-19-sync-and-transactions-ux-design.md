# Luka — Background Sync & Transactions UX Design

**Date:** 2026-03-19
**Status:** Approved
**Scope:** Fintoc background sync architecture, stuck-import fix, transaction fetching strategy, pagination UX

---

## 1. Problem Statement

Three related issues exist today:

1. **Stuck "Importando..."** — `import_fintoc_history` sets `import_status = "importing"` but if the ARQ worker is killed (Railway timeout, deploy restart), it never reaches `"done"`. No stale guard exists. Frontend polls indefinitely.

2. **Wrong filter totals** — Transactions fetched with `limit=200`. All month/bank/category filtering runs client-side on those 200 rows. Filtering by February returns only February rows within the first 200 fetched — not all February transactions.

3. ~~Nightly sync too slow~~ — **Not a problem.** Real-time transactions are captured via Gmail/Outlook email push. The nightly Fintoc cron at 2am is for reconciliation only and stays as-is.

---

## 2. Data Model

### `bank_accounts` — two new columns

```sql
last_synced_at    TIMESTAMPTZ NULL   -- last SUCCESSFUL sync completion
import_started_at TIMESTAMPTZ NULL   -- when the current/last import began
```

**`last_synced_at`:**
- `NULL` = never successfully completed a sync
- Set to `now()` **only on success**; unchanged on failure
- Used by the 4-hour cron as fetch window: `since = last_synced_at OR now()-7days if NULL`
- Used by frontend badge: first-time import = `import_status = "importing"` AND `last_synced_at IS NULL`

**`import_started_at`:**
- Always overwritten with `now()` at the start of each new import (reset-before-set)
- Used by the stale guard: `import_status = "importing"` AND `import_started_at < now - 15 min`
- Stale guard **writes to DB** (`import_status = "failed"`) so the cron can pick the account up again on the next cycle

**Migration:** `009_bank_account_sync_columns.py`

**Downgrade:** `DROP COLUMN last_synced_at, DROP COLUMN import_started_at` on `bank_accounts`

---

## 3. Backend

### 3.1 `import_fintoc_history` — fixes

**A. Import start — overwrite `import_started_at`:**
```python
account.import_status = "importing"
account.import_started_at = datetime.now(timezone.utc)  # always overwrite
await db.commit()
```

**B. Success path — set `last_synced_at`:**
```python
account.import_status = "done"
account.last_synced_at = datetime.now(timezone.utc)
await db.commit()
```

**C. Failure path — leave `last_synced_at` unchanged:**
```python
account.import_status = "failed"
# last_synced_at intentionally NOT updated
await db.commit()
```

### 3.2 Stale guard — background task on `GET /bank-accounts`

Run as part of `GET /bank-accounts` handler (before serialization):

```python
stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
for account in accounts:
    if account.import_status == "importing" and account.import_started_at < stale_cutoff:
        account.import_status = "failed"
        await db.commit()
```

This is a **DB write**, not just a response override. Guarantees:
- The cron no longer skips the account on the next cycle
- All clients see the correct state regardless of cache

### 3.3 `run_fintoc_sync` — nightly cron unchanged, logic improved

Nightly at 2am stays as-is. Two improvements to the existing function:

1. Skip accounts with `import_status = "importing"` (avoid racing with a first-time import)
2. On success per account: set `last_synced_at = now()`
3. On failure per account: log to `failed_jobs`, `last_synced_at` unchanged — next night retries from same window
4. Does **not** touch `import_status`

No schedule change. No new cron job.

### 3.4 Transaction API — replace `limit` with `since`

`GET /transactions/mine` and `GET /transactions/shared`:
- **Remove:** `?limit=N`
- **Add:** `?since=YYYY-MM-DD` — mandatory in all client calls; server falls back to `date.today() - relativedelta(months=6)` only for direct API usage
- Filters `transaction_date >= since`, returns all matching rows sorted `transaction_date DESC`, no row cap

---

## 4. Frontend

### 4.1 Data fetching — one fetch, client-side filters

```typescript
// Always computed and passed — never omitted to rely on server default
const since = format(subMonths(new Date(), 6), "yyyy-MM-dd");

useMyTransactions(since)       // queryKey: ["transactions", "mine", since]  — staleTime: 5min
useSharedTransactions(since)   // queryKey: ["transactions", "shared", householdId, since]  — staleTime: 5min
```

- Full 6-month dataset fetched once and cached
- All filters (month, bank, category, search) run in `useMemo` on cached data — zero network on filter change
- Prefetch on dashboard layout mount so data is ready before user visits Transactions page:

```typescript
queryClient.prefetchQuery({ queryKey: ["transactions", "mine", since], queryFn: ... })
queryClient.prefetchQuery({ queryKey: ["transactions", "shared", householdId, since], queryFn: ... })
```

### 4.2 Settings page — per-account badge

- **Remove** the blue top banner entirely
- The badge is **first-time import only**: shows when `import_status === "importing"` AND `last_synced_at === null`
- Re-syncs via the 4-hour cron never set `import_status = "importing"` → badge never appears for re-syncs → by design
- Polling: `GET /bank-accounts` every **5 seconds** with `staleTime: 0` (always hits server, never served from cache)
- **Stop polling when** all accounts satisfy: `import_status !== "importing"` OR `last_synced_at !== null`
  - If stopped because all accounts reached `"done"` or `last_synced_at` set → badge disappears
  - If stopped because any account reached `"failed"` with `last_synced_at` still null → show amber `"Error al sincronizar"` badge on that account
- **Hard stop after 10 minutes** → same amber error badge for any account still showing "importing"
- When `last_synced_at` is non-null, show `"Última sync: hace X horas"` as secondary text under account number

### 4.3 Transactions page — pagination

**State:**
```typescript
const [pageSize, setPageSize] = useState<10 | 30 | 100>(30);
const [page, setPage] = useState(1);
```

**Data flow:**
```
fullDataset (6 months, cached)
  → applyFilters() → filteredTxns (e.g. 74 rows for February)
    → SummaryBar receives filteredTxns → totals all 74
    → paginate: filteredTxns.slice((page-1)*pageSize, page*pageSize)
      → RecentTransactions renders current page only
```

**UI controls:**
- Page size selector: `10 | 30 | 100` — resets `page` to 1 on change
- Prev / Next arrows — disabled at boundaries
- Label: `"Mostrando 31–60 de 74 resultados"`
- Any filter change (month, bank, category, search) resets `page` to 1

**Key invariant:** `SummaryBar` always receives the full `filteredTxns` array — never the paginated slice.

---

## 5. Error Handling

| Scenario | Behaviour |
|---|---|
| Worker killed mid-import | `import_started_at` stale check fires at 15 min on next `GET /bank-accounts`; writes `"failed"` to DB; polling detects `"failed"` with `last_synced_at=null`; amber error badge shown |
| Polling 10-min hard stop | Any account still `"importing"` gets amber `"Error al sincronizar"` badge |
| Fintoc API down during cron | Per-account catch, logs to `failed_jobs`, `last_synced_at` unchanged, retries next cycle |
| 6-month fetch fails | TanStack Query retries 3×; transactions page shows error state with retry button |
| Cron skips mid-import account | `import_status = "importing"` excluded from cron query; no race |
| Old accounts with NULL `last_synced_at` | Cron defaults fetch window to `now() - 7 days` |
| First import fails, `last_synced_at` still NULL | Badge shows amber error; `last_synced_at` remains NULL; cron picks up account and does initial 7-day sync |

---

## 6. What Does Not Change

- `import_fintoc_history` still triggered on first account connect (90-day history)
- `fintoc_id` idempotency in reconciler — no duplicate transactions
- WhatsApp classification flow
- Auth and household membership checks
- ARQ worker infrastructure and Redis connection

---

## 7. Migration Plan

1. Run migration `009` (add `last_synced_at`, `import_started_at` with NULL default; `downgrade` drops both columns)
2. Deploy backend (updated job, stale guard with DB write, new cron, updated API endpoint)
3. Deploy frontend (updated hooks with `since` param, pagination, remove banner, polling with error states)
4. No data backfill — existing accounts with `import_status = "done"` keep `last_synced_at = NULL`; first cron cycle populates it
