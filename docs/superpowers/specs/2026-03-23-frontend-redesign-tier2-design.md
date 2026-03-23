# Frontend Redesign — Tier 2 (Settings + Login/Onboarding Polish)

**Date:** 2026-03-23
**Status:** Draft
**Scope:** Settings page (full redesign + backend), Login page (visual polish), Onboarding flow (visual polish)

## Context

Tier 1 shipped the transactions, dashboard, and budgets redesign with DM Sans typography, card-based layouts, bottom sheets, and mobile-first patterns. Tier 2 extends that design language to the remaining user-facing pages: Settings (full redesign with new backend features) and Login/Onboarding (visual polish only).

## Design Direction

Same as Tier 1: Modern Bright, serious finance tone, light mode. DM Sans typography. No emojis in general UI. All Tier 1 patterns (card shadows, border-radius-12, bottom sheets on mobile, no horizontal scrolling) apply here.

## Login Page

**Current:** Split layout — form left, hero/background image right on desktop. Stacked on mobile. OAuth buttons for Google and Microsoft.

**Changes (visual polish only, no structural changes):**
- Swap font to DM Sans (already applied globally via Tier 1, verify it propagates to auth pages)
- Button styles: rounded-12, proper shadows matching dashboard buttons
- Polish copy/descriptions for clarity
- Ensure consistent focus states on interactive elements

## Onboarding Flow

**Current:** 3-step flow (Hogar → WhatsApp → Banco) with glassmorphism container and step indicator.

**Changes (visual polish only, no structural changes):**
- DM Sans typography (verify propagation)
- Input styling: border-radius-12, focus ring matching primary blue (#2563EB), consistent padding
- Button styling: match dashboard primary/secondary button styles
- Step indicator: subtle shadow upgrade, match Tier 1 card shadow standard (`0 1px 3px rgba(0,0,0,0.03)`)
- Form spacing: consistent vertical rhythm

## Settings Page — Frontend

Complete redesign. Single scrollable page with card sections (white bg, rounded-12, shadow `0 1px 3px rgba(0,0,0,0.03)`).

### Section 1: Perfil

- User avatar (from OAuth provider, read-only display)
- **Name** — editable text input, pre-populated from OAuth profile
- **Email** — read-only, muted text styling
- **WhatsApp number** — editable text input with Chilean format, pre-populated from onboarding step 2
- Save button for the section
- Calls `PATCH /auth/me` on save

### Section 2: Cuentas Bancarias

- Keep current Fintoc account cards functionality
- Polish visually: match Tier 1 card shadows, DM Sans typography, consistent spacing
- Connect button stays
- Account type toggle, delete, active/inactive — all keep current behavior

### Section 3: Hogar

- Shows household type (Individual / Pareja)
- If couple: partner name, email, status (Activo / Pendiente)
- If no partner yet: "Invitar pareja" button that generates/shows invite link
- Uses existing household endpoints — no new backend needed

### Section 4: Notificaciones

- Single toggle switch: "Notificaciones por WhatsApp" (on/off)
- Toggle minimum 44px touch target
- Calls `PATCH /notifications/preferences` on toggle
- Fetches initial state from `GET /notifications/preferences`

### Section 5: Categorías

- List of all categories with:
  - Drag handle icon (left) for reorder
  - Category name (center)
  - Eye/eye-off icon (right) to hide/show
- Drag-and-drop reorder via `@dnd-kit/sortable` (touch-friendly)
- Hidden categories shown grayed out at the bottom
- On any change (reorder or hide/show), calls `PUT /categories/preferences` with the full list
- Fetches initial state from `GET /categories/preferences`

### Section 6: Privacidad de Datos

- Current disclosure text, polished typography
- No functional changes

### Section 7: Eliminar Cuenta

- Red text button at the bottom of the page, visually separated (danger zone)
- Tapping opens a confirmation:
  - **Mobile:** Bottom sheet (consistent with Tier 1 pattern)
  - **Desktop:** Modal dialog
- Confirmation message: "Esto es irreversible. Se eliminarán todos tus datos."
- Text input requiring user to type "ELIMINAR" to confirm
- Red "Eliminar cuenta" button, disabled until input matches
- Calls `DELETE /auth/me` with header `X-Confirm-Delete: ELIMINAR`

### Mobile Considerations

- All sections stack vertically, full-width cards
- No horizontal scrolling
- Category drag-and-drop uses touch events via `@dnd-kit`
- Delete confirmation uses bottom sheet
- All toggle switches and buttons meet 44px minimum touch target
- Form inputs full-width on mobile

## Settings Page — Backend

### New Tables

**`notification_preferences`**
| Column | Type | Notes |
|--------|------|-------|
| user_id | UUID (PK, FK → users) | One row per user |
| whatsapp_enabled | boolean | Default: true |
| created_at | timestamptz | Default: now() |
| updated_at | timestamptz | Default: now() |

RLS: users can only read/write their own row.

**`user_category_preferences`**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | Default: gen_random_uuid() |
| user_id | UUID (FK → users) | |
| category | text | Matches existing category enum values |
| sort_order | integer | 0-based ordering |
| hidden | boolean | Default: false |
| created_at | timestamptz | Default: now() |
| updated_at | timestamptz | Default: now() |

Unique constraint: (user_id, category)
RLS: users can only read/write their own rows.

### New Endpoints

**Profile:**
- `PATCH /auth/me` — Update name and/or WhatsApp number
  - Body: `{ "full_name"?: string, "whatsapp_number"?: string }`
  - Auth: JWT required, updates own user row only
  - Returns: updated user object

**Notifications:**
- `GET /notifications/preferences` — Returns current preferences
  - Creates default row (whatsapp_enabled=true) if none exists
  - Auth: JWT required
  - Returns: `{ "whatsapp_enabled": boolean }`

- `PATCH /notifications/preferences` — Update preferences
  - Body: `{ "whatsapp_enabled": boolean }`
  - Auth: JWT required
  - Returns: updated preferences object

**Categories:**
- `GET /categories/preferences` — Returns user's category list
  - If no preferences exist, returns all categories with default order and hidden=false
  - Auth: JWT required
  - Returns: `{ "categories": [{ "category": string, "sort_order": int, "hidden": bool }] }`

- `PUT /categories/preferences` — Replace all category preferences
  - Body: `{ "categories": [{ "category": string, "sort_order": int, "hidden": bool }] }`
  - Auth: JWT required
  - Upserts all rows in a single transaction
  - Returns: updated categories list

**Delete Account:**
- `DELETE /auth/me` — Permanently delete user account
  - Requires header: `X-Confirm-Delete: ELIMINAR`
  - Cascading delete order: transaction_splits → transactions → bank_accounts → household_members → notification_preferences → user_category_preferences → user record
  - If user is last member of household: delete household, household_budgets
  - Deletes Supabase auth user via admin API (`supabase.auth.admin.deleteUser()`)
  - Auth: JWT required
  - Returns: 204 No Content

### Migrations

Two Alembic migrations:
1. **Create notification_preferences table** — table + RLS policies
2. **Create user_category_preferences table** — table + unique constraint + RLS policies

## Out of Scope

- Household page redesign
- Dark mode
- Custom categories (create new)
- Chart library upgrade
- Any changes to transaction/dashboard/budgets pages (completed in Tier 1)

## Technical Notes

- DM Sans already loaded globally from Tier 1 — verify it applies to (auth) route group pages
- Bottom sheet component already exists from Tier 1 — reuse for delete confirmation on mobile
- `@dnd-kit/sortable` needs to be added as a dependency for category reorder
- Existing React Query hooks and Zustand store patterns apply for new endpoints
- All new endpoints follow existing FastAPI router/service/schema pattern in backend
- RLS policies follow the same pattern as existing tables (user_id = auth.uid())
