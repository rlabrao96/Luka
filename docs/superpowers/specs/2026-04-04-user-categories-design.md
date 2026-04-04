# User-Editable Categories Design

## Goal

Give each user a fully personal category list (up to 19 expense + 19 income) they can add to, delete from, and reorder. Deleting a category prompts reclassification of existing transactions. Per-user merchant-category counters replace the current global ones, so the WhatsApp category suggestions are personalized.

## Architecture

Two DB changes drive everything:

1. `user_category_preferences` — drop `hidden`, add `category_type` and `is_custom`; seed defaults for all users; remove hardcoded-list validation so custom names are allowed.
2. `merchant_category_selections` — add `user_id` so counters are per-user instead of global.

A new `DELETE /categories/preferences/{category}` endpoint handles atomic delete + reclassify. The frontend `CategoriesSection` gains an add-row, type pills, and a delete-confirmation modal; the hide toggle is removed everywhere.

## Tech Stack

Python 3.12, FastAPI, SQLAlchemy async, Alembic, Next.js 14, React Query, @dnd-kit

---

## Section 1 — DB Schema

### `user_category_preferences` (modified)

| Column | Type | Change |
|--------|------|--------|
| `id` | UUID PK | unchanged |
| `user_id` | UUID FK users | unchanged |
| `category` | String NOT NULL | unchanged |
| `category_type` | String NOT NULL | **NEW** — `"expense"` \| `"income"` |
| `is_custom` | Boolean default false | **NEW** — true = user-created |
| `sort_order` | Integer default 0 | unchanged — scoped per `(user_id, category_type)`, i.e. each type has its own 0-based sequence |
| `created_at` | Timestamp | unchanged |
| `updated_at` | Timestamp | unchanged |
| `hidden` | Boolean | **REMOVED** |

Unique constraint: `(user_id, category)` — unchanged.

Business rules enforced in service layer:
- Max 19 rows per `(user_id, category_type)` combination.
- `category` trimmed, non-empty, max 40 chars.
- `category_type` must be `"expense"` or `"income"`.

### `merchant_category_selections` (modified)

| Column | Type | Change |
|--------|------|--------|
| `id` | UUID PK | unchanged |
| `merchant_id` | UUID FK merchants | unchanged |
| `user_id` | UUID FK users | **NEW** — nullable (NULL = legacy global row) |
| `category` | String | unchanged |
| `count` | Integer | unchanged |
| `last_used_at` | Timestamp | unchanged |

**Unique constraint strategy:** The existing table has no named unique constraint on `(merchant_id, category)` (only an implicit index). The migration creates two partial unique indexes instead of a single constraint, avoiding any `NULLS NOT DISTINCT` PostgreSQL 15+ dependency:

```sql
-- For new per-user rows (user_id IS NOT NULL)
CREATE UNIQUE INDEX uq_merchant_category_user
  ON merchant_category_selections (merchant_id, user_id, category)
  WHERE user_id IS NOT NULL;

-- For legacy global rows (user_id IS NULL) — optional, low cardinality
CREATE UNIQUE INDEX uq_merchant_category_global
  ON merchant_category_selections (merchant_id, category)
  WHERE user_id IS NULL;
```

This approach works on PostgreSQL 12+ (Supabase-safe).

---

## Section 2 — Migration (Alembic `024`)

Steps in a single migration:

1. Add `category_type` (String, **nullable initially**) to `user_category_preferences`.
2. Add `is_custom` (Boolean, default false, NOT NULL) to `user_category_preferences`.
3. Drop `hidden` column from `user_category_preferences`.
4. Backfill `category_type` on existing rows:
   ```sql
   UPDATE user_category_preferences
   SET category_type = 'expense'
   WHERE category IN ('Alimentación','Supermercado','Transporte','Combustible',
                      'Entretenimiento','Salud','Farmacia','Hogar','Ropa',
                      'Tecnología','Educación','Viajes','Servicios','Otros');

   -- Unknown categories (including custom ones added before this migration)
   -- default to 'expense'. This is intentional: expenses are the common case.
   UPDATE user_category_preferences
   SET category_type = 'expense'
   WHERE category_type IS NULL;
   ```
5. Set `category_type` NOT NULL.
6. Seed default rows for every user that currently has **zero** rows in the table:
   ```sql
   INSERT INTO user_category_preferences (id, user_id, category, category_type, is_custom, sort_order)
   SELECT gen_random_uuid(), u.id, defaults.category, defaults.category_type, false, defaults.sort_order
   FROM users u
   CROSS JOIN (VALUES
     ('Alimentación','expense',0), ('Supermercado','expense',1),
     ('Transporte','expense',2), ('Combustible','expense',3),
     ('Entretenimiento','expense',4), ('Salud','expense',5),
     ('Farmacia','expense',6), ('Hogar','expense',7),
     ('Ropa','expense',8), ('Tecnología','expense',9),
     ('Educación','expense',10), ('Viajes','expense',11),
     ('Servicios','expense',12), ('Otros','expense',13),
     ('Sueldo','income',0), ('Freelance','income',1),
     ('Inversiones','income',2), ('Arriendo','income',3),
     ('Bono','income',4), ('Transferencia de terceros','income',5),
     ('Deuda pendiente','income',6), ('Otros ingresos','income',7)
   ) AS defaults(category, category_type, sort_order)
   WHERE NOT EXISTS (
     SELECT 1 FROM user_category_preferences ucp WHERE ucp.user_id = u.id
   );
   ```
7. Add `user_id` (UUID, nullable, FK users) to `merchant_category_selections`.
8. Create the two partial unique indexes described in Section 1 (no constraint to drop — none existed by name).

---

## Section 3 — Backend

### `backend/modules/settings/models.py`

- Remove `hidden: Mapped[bool]`.
- Add `category_type: Mapped[str]` (NOT NULL).
- Add `is_custom: Mapped[bool]` (default False, NOT NULL).

### `backend/modules/settings/schemas.py`

- `CategoryPreferenceItem`: remove `hidden`, add `category_type: str`, `is_custom: bool`.
- `CategoryReorderItem`: `{category: str, sort_order: int}` — used by `PUT` (reorder only, no type/custom fields).
- `CategoryAddRequest`: `{category: str, category_type: Literal["expense", "income"]}`.
- `CategoryDeleteRequest`: `{reclassify_to: str | None}`.
- `CategoryUsageResponse`: `{count: int}`.

### `backend/modules/settings/service.py`

- Remove `ALL_CATEGORIES` / `EXPENSE_CATEGORIES` / `INCOME_CATEGORIES` constants and the validation that checks against them.
- Remove `hidden` from all reads and writes.
- `get_category_preferences(db, user_id)`: if user has no rows, run the default seed INSERT (same as migration step 6 but for a single user) and return them.
- `add_category(db, user_id, category, category_type)`:
  - Strip + validate non-empty, max 40 chars.
  - Check count for that type ≤ 18 (i.e. adding would make it ≤ 19). Raise `ValueError` if at limit.
  - Check no duplicate name for this user. Raise `ValueError` if duplicate.
  - Assign `sort_order = max(existing sort_order for this type) + 1`.
  - Insert row with `is_custom=True`.
- `reorder_categories(db, user_id, items: list[{category, sort_order}])`:
  - Validate submitted categories exactly match the user's existing set (no additions/deletions).
  - Update `sort_order` only; preserve `is_custom` and `category_type` from existing rows.
  - `sort_order` is type-scoped: the frontend sends separate 0-based sequences per type; service stores them as-is.
- `get_category_usage(db, user_id, category) -> int`:
  - Count `TransactionSplit` rows where `category = category` and `transaction_id` IN `(SELECT id FROM transactions WHERE user_id = user_id)`.
  - Note: `TransactionSplit` has no `user_id` column — the join through `Transaction` is required.
- `delete_category(db, user_id, category, reclassify_to: str | None)`: all steps run within the same SQLAlchemy session without intermediate commits — the final `commit()` in step 5 makes the entire operation atomic.
  1. If `reclassify_to` is provided, verify it exists in the user's preferences (case-sensitive match). Raise `ValueError` if not.
  2. If `reclassify_to` provided:
     ```python
     txn_ids = select(Transaction.id).where(Transaction.user_id == user_id)
     await db.execute(
         update(TransactionSplit)
         .where(TransactionSplit.transaction_id.in_(txn_ids),
                TransactionSplit.category == category)
         .values(category=reclassify_to)
     )
     await db.execute(
         update(Transaction)
         .where(Transaction.user_id == user_id,
                Transaction.category == category)
         .values(category=reclassify_to)
     )
     ```
  3. Delete `MerchantCategorySelection` rows where `user_id = user_id AND category = category`.
  4. Delete the `UserCategoryPreference` row for this user + category.
  5. Commit.

### `backend/modules/settings/router.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/categories/preferences` | List all user categories — flat list ordered `expense` rows first (sort_order asc), then `income` rows (sort_order asc) |
| `PUT` | `/categories/preferences` | Reorder only — body is list of `CategoryReorderItem`; validates no additions/removals (case-sensitive); raises 422 on mismatch |
| `POST` | `/categories/preferences` | Add one category — body is `CategoryAddRequest` |
| `POST` | `/categories/preferences/{category}/delete` | Delete + reclassify — body is `CategoryDeleteRequest`. Uses POST (not HTTP DELETE) to avoid intermediaries stripping the request body. |
| `GET` | `/categories/preferences/{category}/usage` | Count transactions with this category — response `CategoryUsageResponse` |

### `backend/modules/merchants/models.py`

- Add `user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)` to `MerchantCategorySelection`.

### `backend/modules/merchants/service.py`

- `record_category_selection(raw_name, category, db, redis, user_id: uuid.UUID)`: add `user_id` parameter. Upsert on `(merchant_id, user_id, category)` partial index path.
- `lookup_merchant`: add a temporary `WHERE user_id IS NULL` filter to the `MerchantCategorySelection` query so it only reads legacy global rows until the follow-on per-user ranked lookup spec ships. Without this guard, after this migration the query would return rows from any user's selections mixed with legacy global rows, producing incorrect suggestions.
- Both call sites must pass `user_id`:
  - `backend/modules/whatsapp/handler.py` — `handle_list_selection` does not have `user_id` in scope. Fix: change `_save_split` return type from `None` to `Transaction | None` (return the `txn` object at the end, or `None` if not found). In `handle_list_selection`, capture the return value and call `record_category_selection` only when `txn is not None` (silently skip recording if the transaction was not found — this mirrors the existing early-return guard in `_save_split`).
  - `backend/modules/transactions/service.py` — already has `user_id` in scope; straightforward update.

---

## Section 4 — Frontend

### `frontend/app/(dashboard)/settings/components/CategoriesSection.tsx`

**Remove:**
- `EXPENSE_CATEGORIES` and `INCOME_CATEGORIES` hardcoded sets.
- Hide/show toggle button and all `hidden` state.
- `hidden` field from `CatPref` type.

**Add to `CatPref` type:**
```ts
type CatPref = { category: string; sort_order: number; category_type: "expense" | "income"; is_custom: boolean };
```

**Add-category row** (above the columns):
- Text input (max 40 chars) + type pills (Gasto / Ingreso, Gasto selected by default) + "Agregar" button.
- On submit: `POST /categories/preferences`, invalidate `["category-preferences"]`.
- Disable "Agregar" if input empty, duplicate, or type is at limit (19).
- Show inline error message on API 422/409.

**Counter line** (below add-row):
- `Gastos: N/19 · Ingresos: N/19` — computed from `localCats`.

**Columns** split by `category_type` field (not hardcoded set).

**`sort_order` for reorder:** When calling `PUT /categories/preferences`, send each group with its own 0-based sort_order sequence (expense items: 0..N, income items: 0..M — independent sequences).

**Delete button:** Red × on every row. On click → open `DeleteConfirmModal`.

### `DeleteConfirmModal` (new component, same file or separate)

1. On open: call `GET /categories/preferences/{category}/usage` to get transaction count.
2. If `count > 0`: show radio list of the user's other categories of the **same type** as the deleted one. Confirm button text: "Eliminar y reclasificar". Confirm disabled until a target is selected.
3. If `count === 0`: show simple "Esta categoría se eliminará de tu lista." No radio list. Confirm button text: "Eliminar".
4. On confirm: call `DELETE /categories/preferences/{category}` with `{ reclassify_to }` (null if count = 0).
5. On success: invalidate `["category-preferences"]` and `["transactions"]` (transaction categories may have changed).

---

## Section 5 — Error Handling

| Scenario | API Response | Frontend Behaviour |
|----------|-------------|-------------------|
| Add at limit (19) | 422 | Disable "Agregar" + "Límite de 19 categorías alcanzado" |
| Add duplicate name | 409 | Inline "Ya tienes una categoría con ese nombre" |
| Add empty/whitespace | — | Client-side: button stays disabled |
| Add name > 40 chars | 422 | Client-side: input maxlength=40 |
| Delete with invalid `reclassify_to` | 422 | Show generic error in modal |
| Reorder with added/removed categories | 422 | Should not happen (reorder-only PUT) |

---

## Section 6 — Out of Scope

- WhatsApp category display using per-user ranked list — separate spec/plan after this ships.
- Bulk import/export of categories.
- Sharing a category list between household members.
- Restoring deleted default categories (user can re-add manually).
