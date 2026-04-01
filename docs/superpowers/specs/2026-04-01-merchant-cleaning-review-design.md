# Merchant Cleaning & Review Pipeline — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Scope:** Backend pipeline, frontend review UI, notification center, CLI training script

---

## Problem

When users connect a bank via luka-connect, 90 days of historical transactions are imported with raw merchant names (e.g., `LIDER PROVIDENCIA`, `COMPRA NETFLIX.COM`, `TRASPASO De:nieves Del Pilar Labra`). These names are unclean, uncategorized, and ungrouped. The WhatsApp flow handles ongoing email-sourced transactions, but bulk imports bypass it entirely.

Users see a wall of ALL CAPS gibberish with no categories — a bad first impression that undermines trust in the product.

## Solution

A three-part system:

1. **Backend pipeline** — LLM-powered batch job that groups raw merchant variants into canonical merchants, generates clean display names, and assigns categories.
2. **Frontend review UI** — Tinder-style card swipe experience where users can approve, edit, or skip LLM proposals grouped by merchant.
3. **CLI training script** — Developer/admin tool to seed, review, and curate the global merchant database.

---

## 1. Data Model

### New table: `canonical_merchants`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| display_name | TEXT NOT NULL UNIQUE | Clean name: "Lider", "Netflix", "Uber Eats". Unique to prevent duplicate canonicals from concurrent LLM calls. |
| default_category | TEXT | Most common category across all users |
| logo_url | TEXT | Future: merchant logos |
| is_verified | BOOLEAN DEFAULT FALSE | true = human-confirmed (review UI or CLI) |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

**RLS:** Permissive read policy (all authenticated users). Write restricted to backend service role only.

### Modified table: `merchants`

Add column:
- `canonical_merchant_id` UUID FK → `canonical_merchants.id` (nullable)

Multiple `merchants` rows (raw variants) point to one `canonical_merchants` row. Example:
- `merchants.raw_name = "LIDER PROVIDENCIA"` → `canonical_merchant_id` → `canonical_merchants.display_name = "Lider"`
- `merchants.raw_name = "LIDER LAS CONDES"` → same `canonical_merchant_id`
- `merchants.raw_name = "SUPERMERCADO LIDER"` → same `canonical_merchant_id`

### New table: `notifications`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| type | TEXT NOT NULL | `'merchant_review'`, future: `'budget_alert'`, `'sync_error'` |
| title | TEXT NOT NULL | "47 merchants ready for review" |
| payload | JSONB | `{bank_name, sync_job_id, merchant_count, ...}` |
| status | TEXT DEFAULT 'unread' | `'unread'`, `'read'`, `'dismissed'`, `'actioned'` |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| read_at | TIMESTAMP | |

**Indexes:** `(user_id, status)` for badge count queries. **RLS:** Standard user-scoped policies.

### New table: `merchant_review_jobs`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users.id | |
| bank_credential_id | UUID FK → bank_credentials.id | Which bank connection triggered this |
| status | TEXT DEFAULT 'processing' | `'processing'`, `'ready'`, `'completed'`, `'skipped'`, `'failed'` |
| total_merchants | INT | |
| reviewed_count | INT DEFAULT 0 | |
| notification_id | UUID FK → notifications.id | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

---

## 2. Backend Pipeline

### Trigger

Inside `_process_movements()` in `bank_connect/router.py`, after all movements are processed:

```
If created > 0:
  1. Create merchant_review_job (status='processing')
  2. Create notification (type='merchant_review', status='unread')
  3. Enqueue ARQ job: process_merchant_review(job_id)
```

This fires on **every luka-connect sync that creates new transactions** — first bank connection, additional banks, re-syncs after downtime.

### Transactions are visible immediately

The webhook creates transactions and they appear in the dashboard right away with `raw_merchant_name` displayed. The LLM pipeline runs in the background. When it completes, transactions are upgraded in-place with categories. If the user never reviews, LLM results are auto-applied.

**Display name resolution:** No new column on `transactions`. The frontend resolves the clean name by following the join chain: `transaction.merchant_id → merchants.canonical_merchant_id → canonical_merchants.display_name`. If no canonical merchant is linked yet, fall back to `transaction.raw_merchant_name`. The backend transaction list endpoint includes `display_name` in the response by joining at query time.

### Concurrent sync handling

If a user connects two banks in quick succession, each sync creates its own `merchant_review_job` and `notification`. They are reviewed independently (separate card stacks). The processing banner shows the most recent active job. Multiple notifications are fine — the badge count reflects all unread.

### ARQ Job: `process_merchant_review`

**Phase 1 — Group & Name** (single LLM call):

1. Collect all unique `raw_merchant_name` values from the new transactions.
2. Deduplicate against existing `canonical_merchants` — if a `merchants` row already has a `canonical_merchant_id`, skip it.
3. Send remaining names to Gemini in one call.
4. For each LLM-proposed group, check if a `canonical_merchants` row with the same `display_name` already exists (UNIQUE constraint). If so, link to the existing one instead of creating a duplicate.
5. Create new `canonical_merchants` rows (`is_verified=false`) for genuinely new merchants.
6. Link `merchants` rows → `canonical_merchant_id`.
6. Update `transactions` with category from `canonical_merchants.default_category`.

**Phase 1 LLM Prompt:**

```
You are a banking data specialist. Given a list of raw merchant names 
from bank statements, group them by BUSINESS ENTITY.

Rules:
- Group ONLY when the same company/brand (different branches OK)
- NEVER group by business type (two different restaurants = separate)
- NEVER group different services from same company (e.g., Uber Trips ≠ Uber Eats)
- NEVER group different businesses that share a category (e.g., "Estacionamiento PR" ≠ "Estacionamiento Vita")
- When in doubt, keep separate
- Generate a clean display name for each group
- Fix casing (ALL CAPS → proper case)
- Remove bank transaction prefixes (COMPRA, PAGO, CARGO, PURCHASE, etc.)
- Keep the business name recognizable

Input: ["LIDER PROVIDENCIA", "LIDER LAS CONDES", "NETFLIX.COM", "ESTACIONAMIENTO PR", "ESTACIONAMIENTO VITA", "UBER *TRIP", "UBER *EATS"]

Output format (JSON):
[
  {"display_name": "Lider", "raw_names": ["LIDER PROVIDENCIA", "LIDER LAS CONDES"]},
  {"display_name": "Netflix", "raw_names": ["NETFLIX.COM"]},
  {"display_name": "Estacionamiento PR", "raw_names": ["ESTACIONAMIENTO PR"]},
  {"display_name": "Estacionamiento Vita", "raw_names": ["ESTACIONAMIENTO VITA"]},
  {"display_name": "Uber Trip", "raw_names": ["UBER *TRIP"]},
  {"display_name": "Uber Eats", "raw_names": ["UBER *EATS"]}
]
```

**Phase 2 — Categorize** (reuse existing flow):

6. For each new `canonical_merchant`, call `lookup_merchant()` with one of the raw variant names (the first in the group). This hits the existing 3-tier flow: Redis cache → DB → LLM. The raw name is used (not the display name) because `lookup_merchant()` expects bank-format strings and normalizes them internally.
7. Set `canonical_merchant.default_category` = top suggestion from `lookup_merchant()`.

**Finalize:**

9. Update `merchant_review_job.status = 'ready'`, `total_merchants = count`.
10. Update `notification.title = "47 merchants ready for review"`.
11. Update `transactions.category` and link `transactions.merchant_id` for all affected transactions. Display names are resolved via join (no write needed).

**Error handling:**

If the LLM call fails or times out:
- Set `merchant_review_job.status = 'failed'`.
- Update notification: "Could not process merchants — transactions available with original names."
- Processing banner changes to a neutral message with a "Retry" option.
- Transactions remain visible with raw names and no categories (same as pre-pipeline behavior).

### New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications` | List user's notifications (supports badge count) |
| PATCH | `/notifications/{id}` | Mark read/dismissed/actioned |
| GET | `/merchant-review/{job_id}` | Get all review cards for the job (single response, not paginated — typically 40-80 merchants) |
| PATCH | `/merchant-review/{job_id}/merchants/{canonical_id}` | Approve/edit a merchant |
| POST | `/merchant-review/{job_id}/skip` | Skip entire review (auto-accept all) |
| GET | `/merchant-review/{job_id}/status` | Poll processing status (for banner) |

### Dismiss = Auto-Accept

When the user dismisses the notification or skips the review:
- All `canonical_merchants` from that job keep `is_verified=false` (LLM-assigned).
- Display names and categories are already applied to transactions (done at end of ARQ job).
- No user action needed — the data is live.

When the user reviews:
- Approved merchants get `is_verified=true` (human-confirmed).
- Edited merchants get the user's corrections applied.
- The `is_verified` flag is for data quality tracking only — both work identically for end users.

---

## 3. Frontend

### Notification Center

**Sidebar menu item** below the existing menu:

```
──────────────
🔔 Notificaciones  (1)
──────────────
```

- Yellow/amber background highlight when unread notifications exist.
- Badge count shows number of unread notifications.
- Clicking navigates to `/notifications`.

**Notifications page** (`/notifications`):

- List of all notifications, newest first.
- Active notifications (unread) show with blue highlight, action buttons.
- Merchant review notifications show:
  - Title: "47 merchants ready for review"
  - Subtitle: "Banco de Chile — 156 transactions imported"
  - Timestamp: "hace 2 minutos"
  - Buttons: "Revisar merchants" (primary) | "Omitir" (secondary)
- Past/completed notifications show greyed out with completion status.
- "Marcar todas leídas" link at top.

### Processing Banner

Shown on the transactions page while `merchant_review_job.status = 'processing'`:

- Light green card (`#F0FDF4` background, `#86efac` border).
- No emoji. Text only.
- Content: "Clasificando tus merchants" (bold title) + "Estamos organizando {count} transacciones de {bank_name}. Estarán listas para revisión en unos momentos." (subtitle).
- Animated indeterminate progress bar (green).
- Disappears when job status changes to `'ready'` (poll via `/merchant-review/{job_id}/status`).
- Transactions are fully visible and usable below the banner.

### Merchant Review UI

**Route:** `/transactions/review/{job_id}`

**Layout:** Tinder-style centered card stack.

**Top:** Progress bar with "Reviewing merchants — 12 / 47".

**Card contents:**
- Merchant icon (category-based).
- Clean display name (large, bold).
- Proposed category (blue chip).
- "Grouped from" section showing raw variant names as tags + transaction count + total amount.
- Stacked card behind showing the next merchant for visual continuity.

**Actions (circular buttons below card):**
- **Skip** (left) — leave for later, stays unverified.
- **Edit** (center) — inline edit mode on the same card.
- **Approve** (right, large green) — confirm LLM proposal as-is.

**Edit mode:**
- Card gets blue border + "EDITING" badge.
- Display name becomes an editable input field.
- Category becomes tappable chips: top 3 LLM suggestions + "Otra..." which expands full category dropdown.
- Buttons: "Cancel" | "Save & Approve".

**Completion:**
- When all cards reviewed (or user exits): redirect to `/transactions`.
- `merchant_review_job.status` updated to `'completed'`.
- `notification.status` updated to `'actioned'`.

**Skip All:**
- Available via notification dismiss or a "Skip All" link in the review header.
- All merchants auto-accepted with LLM values.
- `merchant_review_job.status = 'skipped'`.

### Mobile Considerations

- Swipe gestures: right = approve, left = skip (in addition to buttons).
- Cards sized to viewport width with padding.
- Edit mode: same inline approach, keyboard pushes card up.
- Progress bar and action buttons always visible.

---

## 4. CLI Training Script

**Path:** `backend/scripts/train_merchants.py`

### Commands

**`seed --from-db`**
Pull all uncategorized transactions (no `canonical_merchant_id`), extract unique `raw_merchant_name` values, run Phase 1 + Phase 2 LLM pipeline, create verified canonical merchants.

```bash
python scripts/train_merchants.py seed --from-db            # creates as is_verified=false
python scripts/train_merchants.py seed --from-db --verify   # creates as is_verified=true (developer vouches)
python scripts/train_merchants.py seed --from-db --dry-run  # preview only
```

**`seed --from-file <path>`**
Load merchants from a JSON file:
```json
[
  {"raw_names": ["NETFLIX.COM", "NETFLIX"], "display_name": "Netflix", "category": "Entretenimiento"}
]
```

**`review`**
Interactive one-by-one review of unverified canonical merchants:
```
Display name: Lider                    [edit or Enter to keep]
Category: Supermercado                 [edit or Enter to keep]
Grouped from: LIDER PROVIDENCIA, LIDER LAS CONDES
Transactions: 23 (total: $387.450)
→ (a)pprove  (e)dit  (s)kip  (m)erge into another  (q)uit
```

**`merge <source> <target>`**
Merge two canonical merchants. Moves all `merchants` links from source to target, deletes source.
```bash
python scripts/train_merchants.py merge "Supermercado Lider" "Lider"
```

**`stats`**
Show global merchant database statistics:
```
Total canonical: 342 | Verified: 128 | Unverified: 214
Top uncategorized | Most variants | Recent additions
```

**`regroup`**
Re-run LLM grouping on all unverified merchants. Useful after prompt improvements.

---

## 5. Global Merchant Learning

The `canonical_merchants` table is shared across all users. Learning flow:

1. **User A** connects Banco de Chile. LLM creates `canonical_merchants` entry for "Lider" with `is_verified=false`.
2. **User A** reviews and approves → `is_verified=true`, `default_category = "Supermercado"`.
3. **User B** connects their bank. Phase 1 deduplication finds `LIDER LAS CONDES` already linked to canonical "Lider" → **skipped**. User B gets clean name + category for free.
4. **Developer** runs `train_merchants.py seed --from-db` → bulk-verifies merchants, improving quality for all future users.

The more users connect, the fewer merchants need LLM processing or human review. The dataset grows organically into a curated Chilean (and international) merchant directory.

---

## 6. Complete Data Flow

```
USER CONNECTS BANK
        │
        ▼
Luka Connect scrapes history
        │
        ▼
Webhook: _process_movements()
  ├── Create transactions (visible immediately, raw names)
  ├── Create/link bank accounts
  └── Count new transactions created
        │
        ▼
  If created > 0:
  ├── Create merchant_review_job (status='processing')
  ├── Create notification (status='unread')
  └── Enqueue ARQ job: process_merchant_review
        │
        ▼
  [Transactions page shows green processing banner]
        │
        ▼
ARQ JOB: process_merchant_review
  ├── Phase 1: Group & Name (single LLM call)
  ├── Phase 2: Categorize (reuse lookup_merchant)
  ├── Apply display names + categories to transactions
  ├── merchant_review_job.status = 'ready'
  └── notification.title = "47 merchants ready for review"
        │
        ▼
  [Processing banner disappears]
  [Notification badge appears: 🔔 (1)]
        │
        ├─── User taps "Revisar" ──────────────┐
        │                                       ▼
        │                        /transactions/review/{job_id}
        │                        Tinder-style card stack
        │                          ├── Approve → is_verified=true
        │                          ├── Edit → correct + approve
        │                          └── Skip → stays unverified
        │                                       │
        │                                       ▼
        │                        job.status = 'completed'
        │                        Redirect to /transactions
        │
        └─── User taps "Omitir" ───────────────┐
                                                ▼
                                 Auto-accept all LLM values
                                 job.status = 'skipped'
                                 (data already applied)
```

---

## Non-Goals (Out of Scope)

- Merchant logo fetching/display (future enhancement).
- Full admin web UI for merchant management (CLI covers this).
- Automatic re-review when LLM prompt improves (use CLI `regroup` manually).
- Merge action in the swipe UI (available in CLI only for v1).
- Transaction-level review (review is per-merchant, not per-transaction).
