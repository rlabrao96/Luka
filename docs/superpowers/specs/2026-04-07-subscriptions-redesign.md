# Subscriptions Page Redesign

**Date:** 2026-04-07
**Status:** Draft

## Problem

The subscriptions page has several issues:
1. Currencies are mixed — CLP and USD amounts shown together without distinction
2. USD amounts display in cents (e.g., $500 instead of US$5.00)
3. The "Próximos Cobros" timeline shows past dates instead of a forward-looking view
4. No way to edit, dismiss, or mark subscriptions as inactive
5. Price change alerts use yellow boxes that clash with the app's blue design system
6. Subscription detection runs on every page load — expensive for data that rarely changes

## Solution

Redesign the subscriptions page with currency awareness, a generic-month timeline, a summary table with edit capabilities, and pre-computed analysis stored in the database.

---

## Backend

### New Table: `subscription_overrides`

Stores user edits to detected subscriptions. One row per user+merchant pair.

```sql
CREATE TABLE subscription_overrides (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    merchant_key    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'inactive' | 'dismissed'
    category        TEXT,                             -- overrides detected category, NULL = use detected
    next_charge_day INTEGER,                          -- day-of-month override (1-31), NULL = use predicted
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, merchant_key)
);
```

Constraints: `status IN ('active', 'inactive', 'dismissed')`, `next_charge_day BETWEEN 1 AND 31`.

### New Table: `detected_subscriptions_cache`

Stores pre-computed subscription analysis per user. Replaces the Redis cache.

```sql
CREATE TABLE detected_subscriptions_cache (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    result_json     JSONB NOT NULL,       -- raw detected items (before override merging)
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

The cache stores **raw detected items only** — overrides are merged at read time. This means `PUT /subscriptions/override` does NOT invalidate the cache; it only updates the override row and the next GET merges fresh overrides over the cached detection result.

Both tables are accessed exclusively through the backend (service role), no RLS policies needed.

### SQL Query Change

Add `t.currency` to the detection query so each subscription item carries its currency:

```sql
SELECT
    COALESCE(m.normalized_name, t.raw_merchant_name) AS merchant_key,
    t.category,
    ABS(t.amount) AS amount,
    t.transaction_date AS tx_date,
    TO_CHAR(t.transaction_date, 'YYYY-MM') AS month,
    COALESCE(ts.split_type, 'personal') AS split_type,
    t.currency                                          -- NEW
FROM transactions t
LEFT JOIN merchants m ON m.id = t.merchant_id
LEFT JOIN transaction_splits ts ON ts.transaction_id = t.id
WHERE t.user_id = :user_id
  AND t.transaction_type = 'expense'
  AND t.transaction_date >= (NOW() - :months_back * INTERVAL '1 month')::DATE
ORDER BY t.transaction_date DESC
```

### Service Changes

`detect_from_rows()` changes:
- Include `currency` in each result item (taken from the latest transaction for that merchant).
- For USD amounts: the raw amount is already in cents from Plaid. Keep as-is in the backend; the frontend handles the cents→dollars conversion (same pattern as transactions page).

`get_detected_subscriptions()` changes:
- Read from `detected_subscriptions_cache` table instead of Redis.
- If no cached result exists, compute and store (first-time fallback).
- Merge `subscription_overrides` into the result: apply status, category override, next_charge_day override.
- Return `status` field per item ('active' | 'inactive'). Dismissed items are excluded entirely.

`_compute_and_cache()` changes:
- Write to `detected_subscriptions_cache` instead of Redis.
- Include `computed_at` timestamp so the frontend can show "last updated".
- Delete old Redis cache key (`subscriptions:v2:{user_id}`) — no longer used.

### New Endpoint: `PUT /subscriptions/override`

```python
class SubscriptionOverrideRequest(BaseModel):
    merchant_key: str
    status: str | None = None          # 'active' | 'inactive' | 'dismissed'
    category: str | None = None        # category name or None to clear
    next_charge_day: int | None = None  # 1-31 or None to clear

@router.put("/override")
async def upsert_override(body: SubscriptionOverrideRequest, ...):
    # Upsert into subscription_overrides
    # Does NOT invalidate the cache — overrides are merged at read time
    # Return updated override
```

### New Endpoint: `POST /subscriptions/refresh`

```python
@router.post("/refresh")
async def refresh_subscriptions(db, current_user):
    # Re-run _compute_and_cache() for this user
    # Merge overrides
    # Return fresh SubscriptionsResponse
```

### Schema Changes

`RecurringExpenseItem` adds:
- `currency: str` — "CLP" or "USD"
- `status: str` — "active" or "inactive"
- `next_charge_day: int` — day-of-month (from override or predicted)
- `recent_charges: list[dict]` — last 2-3 charges with `date` and `amount` for the expandable table rows

`RecurringExpenseItem` removes:
- `predicted_next_date` — replaced by `next_charge_day` (integer day-of-month)

`SubscriptionsResponse` adds:
- `computed_at: datetime` — when the analysis was last run

`SubscriptionsResponse` changes:
- `summary` becomes `summary_by_currency: dict[str, SubscriptionsSummary]` — keyed by "CLP", "USD". Each contains `total_recurring`, `monthly_total`, `pct_of_total`, `count` for that currency. Computed server-side since `pct_of_total` requires a separate query for total monthly expenses per currency.

### Computation Triggers (ARQ)

1. **New bank account linked** — enqueue recomputation 30 minutes after `bank_accounts` insert (delay lets transactions sync first).
2. **Periodic cron** — ARQ cron job runs every 10 days, iterates all users with at least one bank account, recomputes their subscriptions.
3. **Manual refresh** — `POST /subscriptions/refresh` endpoint, called from the refresh button on the page.

No transaction-based triggers. The periodic job and manual refresh are sufficient.

ARQ cron job should batch users (e.g., 50 at a time with a small delay between batches) to avoid overloading the database as the user base grows.

### Migration

Single Alembic migration creates both tables. Also cleans up old Redis cache keys (`subscriptions:v2:*`) in the first ARQ cron run. No data migration needed — the cache populates on first access or next cron run.

### Known Limitations

- **merchant_key stability:** `merchant_key` is `COALESCE(m.normalized_name, t.raw_merchant_name)`. If a merchant gets normalized later, the key changes and existing overrides become orphaned. Acceptable for now — orphaned overrides are harmless (they just don't match anything). Can be addressed later with a cleanup job if needed.
- **Override validation:** `PUT /override` does not validate that the `merchant_key` exists in the current detection results. Orphan overrides are harmless and will be ignored.

---

## Frontend

### Currency Toggle

- Add `CurrencyToggle` component to the page header (same component used in transactions).
- Initialize from `me.preferred_currency`.
- All displayed amounts, KPIs, and alerts filter by the selected currency.
- Format function matches transactions page: CLP → `$388.880` (es-CL locale, no decimals), USD → `US$5.00` (en-US locale, 2 decimals, divide cents by 100).

### KPI Cards

Same layout. Display `summary_by_currency[selectedCurrency]`. Only count active subscriptions. If selected currency has no subscriptions, show a currency-specific empty state: "No tienes suscripciones en USD".

### Price Change Alerts

Replace yellow alert boxes with white cards matching the app's design system:
- White background, 1px slate border, colored left border (3px).
- **Increase:** red left border, red `↑` icon in light-red circle, red percentage.
- **Decrease:** green left border, green `↓` icon in light-green circle, green percentage.
- Merchant name as title, "old amount → new amount" as subtitle.
- Section header: "Cambios de precio".
- Only show for active subscriptions in the selected currency.

### Generic Month Timeline

Replace the "next month" timeline with a generic month view:
- Section header: "Calendario de cobros".
- Items sorted by `next_charge_day` (day-of-month).
- Labels show "Día 2", "Día 5", etc.
- **"Hoy" marker** — a horizontal line with a blue circle showing today's date number, cutting across the timeline at the current day position.
- Items above the marker: already charged this cycle. Dots use `bg-blue-600`.
- Items below the marker: upcoming. Dots use `bg-blue-400` (lighter).
- Only show active subscriptions in the selected currency.
- Amounts formatted per currency.

### Summary Table

Positioned below the timeline. Columns: Servicio, Monto, Último cobro, Categoría, Editar.

- **Servicio:** merchant name + "{N} meses · mensual" subtitle.
- **Monto:** last_amount formatted per currency.
- **Último cobro:** last_charge_date formatted.
- **Categoría:** pill/badge with category name.
- **Editar:** blue text button, opens edit modal.
- **Expandable rows:** click a row to show last 2-3 charges (date + amount) in a sub-section with a left border.
- **Inactive rows:** shown with reduced opacity (0.55) and an amber "Inactiva" badge. Still editable.
- **Dismissed rows:** hidden entirely.
- Filtered by selected currency.

### Edit Modal

Opens when clicking "Editar" on a table row. Contains:

1. **Categoría** — dropdown with all available categories (from `/categories/preferences` or similar).
2. **Estado** — toggle group with three options: Activa (blue active), Inactiva (slate), No es suscripción (slate).
3. **Próximo cobro** — optional date picker for day-of-month (1-31). Label: "Día del mes (opcional)". If empty, uses auto-predicted day.
4. **Actions:** "Guardar" (blue primary button) → calls `PUT /subscriptions/override`. "Cancelar" (slate outline button) → closes modal.

After save, refetch subscriptions data to update the page.

### Refresh Button

Small icon button (RefreshCw icon from lucide) near the page header, next to the currency toggle.
- Click triggers `POST /subscriptions/refresh`.
- Shows loading spinner while running.
- Tooltip or subtitle shows "Última actualización: {relative time}" based on `computed_at`.

### Hook Changes

`useSubscriptions()` — same query key, same endpoint. No changes needed since the backend now reads from the cache table.

Add `useRefreshSubscriptions()` — mutation hook for `POST /subscriptions/refresh`, invalidates the subscriptions query on success.

Add `useSubscriptionOverride()` — mutation hook for `PUT /subscriptions/override`, invalidates the subscriptions query on success.

---

## What This Does NOT Include

- Subscription-based notifications or reminders (future feature).
- Annual/quarterly frequency detection (only monthly for now).
- Shared/household-level subscription views (personal only for now).
- Automatic inactive detection (user must manually mark; detection algo only finds active patterns).
