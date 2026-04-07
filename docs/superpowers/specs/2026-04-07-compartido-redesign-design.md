# Compartido Redesign — Design Spec

_2026-04-07_

## Overview

Redesign the "Hogar" (household) page into **"Compartido"** — Luka's core shared expense feature. Positions Luka as "automated Splitwise for shared homes." Supports up to 5 members (roommates, couples, families), pool-based settlement with optional disable, currency filtering, and in-page member management.

## Goals

1. Rename "Hogar" → "Compartido" throughout the app (nav, page, onboarding, empty states)
2. Support up to 5 members per group (not just couples)
3. Pool-based settlement with simplified transfer suggestions
4. Optional settlement toggle — groups that don't want debt pressure can disable it
5. Currency toggle (CLP/USD) — no mixing currencies in the view
6. Invite members directly from the Compartido page via shareable link
7. Pending invites appear as ghost cards in the UI

## Data Model Changes

### `households` table

| Column | Change | Details |
|--------|--------|---------|
| `type` | Modify | Remove "couple" concept. Values: `individual` (no group), `group` (has members). Auto-transitions to `group` when first invite is created |
| `split_ratio` | Modify | Change from fixed 2-element `[50, 50]` to dynamic N-element array. Default: equal parts (e.g., `[33, 33, 34]` for 3 members). Must sum to 100 |
| `settlement_enabled` | **New** | Boolean, default `true`. When `false`, no settlement calculations shown |

### `household_members` table

| Column | Change | Details |
|--------|--------|---------|
| `role` | Keep | `owner` / `member`. Multiple owners allowed |
| `left_at` | **New** | Nullable timestamp. Soft delete — member leaves but historical data preserved |
| Max members | **New validation** | Backend enforces max 5 active members per household |

### `household_invites` table

| Column | Change | Details |
|--------|--------|---------|
| `invited_email` | Modify | Change from `NOT NULL` to nullable. Link-based invites don't require email upfront — email is populated when the invited user accepts. Requires Alembic migration |

### Split types

The existing `partner` split type is already deprecated (WhatsApp flow uses Personal / Compartido). This spec does not change split type behavior — transactions are either `personal` or `compartido` (shared). Existing `partner` transactions in the DB should be migrated to `compartido` via data migration.

### Settlement algorithm (pool-based)

1. Sum all shared transactions for the period → `grand_total`
2. For each member: `expected[i] = grand_total * (ratio[i] / 100)`
3. For each member: `balance[i] = actual[i] - expected[i]` (positive = overpaid/creditor, negative = underpaid/debtor)
4. Minimize transfers: greedy algorithm — match largest creditor with largest debtor, transfer the minimum of the two absolute values, repeat until all balanced
5. Return list of `{ from_member, to_member, amount }` transfers

### Settlement response schema (breaking change)

Current `SettlementResponse` is a flat object with `from_user_id`, `to_user_id`, `amount` (single transfer, 2-person only). New schema:

```python
class SettlementTransfer(BaseModel):
    from_user_id: UUID
    from_user_name: str
    to_user_id: UUID
    to_user_name: str
    amount: Decimal

class SettlementResponse(BaseModel):
    settlement_enabled: bool
    transfers: list[SettlementTransfer]  # empty list when disabled or balanced
    split_ratio: list[int]
```

Frontend must be updated to consume the new list-based response.

### Historical data

- Removed members (`left_at IS NOT NULL`) keep their transaction data
- Past months show removed members in the breakdown
- Current/future months exclude removed members
- Split ratio auto-adjusts to equal parts when a member leaves (owner can customize)

### Member removal effects

- Bank accounts linked to the removed member are **unlinked** from the household
- New transactions from their email/bank sync **stop routing** to this household
- The removed member **cannot see** the Compartido page after leaving (no historical access)
- A new `individual` household is auto-created for them so they have a clean slate
- At least one owner must remain — cannot remove the last owner

## Frontend: Page Layout

### Empty State (no household)

Centered content:
- Message: "No tienes un grupo compartido"
- CTA button: "Agregar mi primer miembro"
- Clicking opens the invite modal, which auto-creates the household

### Active State — Top to Bottom

**1. Header row**
- Left: Title "Compartido" + subtitle "Gastos compartidos y balance del grupo"
- Right: Month selector → Currency toggle (CLP/USD) → "+ Agregar miembro" button

**2. Member cards row** (horizontal, scrollable on mobile for 5 members)
- Each active member card:
  - Avatar (initials, colored)
  - Name
  - Amount contributed this period
  - Percentage of total
  - When settlement enabled: green "+$X a favor" or red "-$X debe" badge
  - When settlement disabled: amount + percentage only, no badges
- Pending invite card (ghost):
  - Dashed border, muted opacity
  - "?" avatar
  - Shows email (from accepted user) or "Invitación pendiente"
  - "Reenviar invitación" action

**3. Total summary bar**
- "TOTAL COMPARTIDO — [MONTH] [YEAR]"
- Total amount for the period

**4. Transferencias sugeridas** (only when `settlement_enabled = true`)
- Light blue card
- List of simplified transfers: "[Avatar] Name → [Avatar] Name: $amount"
- "⚙ Ratios" button opens ratio/settlement config modal
- Entire section hidden when settlement disabled

**5. Category breakdown table**
- Dynamic columns: one per active member (pending members excluded)
- Rows: category name, per-member amount + percentage, total
- Footer: total row with per-member totals

### Responsive Behavior

- Mobile: member cards scroll horizontally, table columns may require horizontal scroll for 4-5 members
- The "⚙ Ratios" button: when settlement section is hidden (disabled), the button moves to the header row (right side, before "+ Agregar miembro")

## Frontend: Modals

### Invite Modal

- Triggered by: "+ Agregar miembro" button or empty state CTA
- If no household exists: auto-creates one, user becomes owner
- Generates a shareable invite link
- "Copiar enlace" button to copy to clipboard
- Validation: disabled if group already has 5 active members

### Ratio Settings Modal

- Triggered by: "⚙ Ratios" button
- Content:
  - List of active members, each with a percentage input field
  - Real-time validation: must sum to 100%
  - "Repartir equitativamente" button — resets all to equal parts
  - Toggle: "Activar liquidación" (on/off for `settlement_enabled`)
  - Save button

### Member Management

- Triggered by: click/long-press on a member card (owners only)
- Options:
  - "Hacer administrador" — promotes member to owner role
  - "Eliminar miembro" — confirmation dialog: "Se eliminará a [name] del grupo. Los datos históricos se mantendrán."
- Only visible to users with `role = owner`

## Invite Link Flow

### Happy path — existing user

1. Recipient opens invite link → `/invite/[token]`
2. Landing page shows two options: "Ya tengo cuenta" / "Crear cuenta"
3. "Ya tengo cuenta" → login (Google/Microsoft OAuth)
4. After auth → auto-accept invite → redirect to Compartido page

### Happy path — new user

1. Recipient opens invite link → `/invite/[token]`
2. "Crear cuenta" → signup via OAuth
3. Invite token preserved through auth flow (URL param / localStorage)
4. Onboarding: skip the "compartido" question (they came from an invite, intent is clear)
5. Complete account setup → auto-accept invite → redirect to Compartido page

### Edge cases

| Scenario | Behavior |
|----------|----------|
| Already a member of this group | "Ya eres parte de este grupo" |
| Already in another group | "Ya perteneces a un grupo compartido. Debes salir del grupo actual para unirte a otro." + option to leave current group |
| Expired link | "Este enlace ha expirado, pide uno nuevo" |
| Group full (5 members) | "Este grupo ya tiene el máximo de miembros" |
| Already logged in | Skip login step, auto-accept, redirect |
| Self-invite | "No puedes unirte a tu propio grupo" (existing behavior) |

## Navigation & Naming Changes

| Location | Current | New |
|----------|---------|-----|
| Sidebar (`Sidebar.tsx`) | "Hogar" | "Compartido" |
| Bottom nav (`BottomNav.tsx`) | "Hogar" | "Compartido" |
| Page title | "Mi Hogar" | "Compartido" |
| Page subtitle | "Contribuciones y resumen del grupo" | "Gastos compartidos y balance del grupo" |
| Onboarding question | "individual / couple" | "¿Vas a compartir gastos?" yes/no |
| Empty state | "Invita a tu pareja desde Configuración" | "No tienes un grupo compartido" + CTA |
| Settings section | "HogarSection" | "CompartidoSection" |
| URL path | `/household` | `/household` (keep existing path) |

## Backend API Changes

### Modified endpoints

| Endpoint | Change |
|----------|--------|
| `PATCH /households/{id}/split-ratio` | Accept N-element ratio array, validate sum = 100, validate length = active member count |
| `GET /households/{id}/settlement` | Return list of `{ from_user_id, to_user_id, amount }` transfers (N-member pool-based algorithm) |
| `GET /households/{id}/summary` | No change needed — already returns N members |
| `GET /households/{id}/category-breakdown` | No change needed — already handles N members |
| `POST /households/{id}/invite` | Remove email requirement, generate link-only invite |

### New endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /households/create-and-invite` | Atomically create household (if none) + generate invite link. Used by empty state CTA and onboarding |
| `PATCH /households/{id}/settlement-enabled` | Toggle `settlement_enabled` boolean |
| `PATCH /households/{id}/members/{member_id}/role` | Change member role (owner/member). Validate at least one owner remains |
| `DELETE /households/{id}/members/{member_id}` | Soft-remove member (set `left_at`). Auto-create individual household for removed member. Unlink their bank accounts |

### Modified validations

- Split ratio: accept any length 2-5, must sum to 100
- Member count: max 5 active members per household
- Role checks: multiple owners allowed, at least one owner must remain

## Onboarding Changes

### Current flow
1. "individual" or "couple" selection
2. If couple: enter partner email

### New flow
1. "¿Vas a compartir gastos?" — Sí / No
2. If Sí: show invite modal (generate shareable link)
3. If No: skip, Compartido page shows empty state later

### Invite-originated signup
- Token detected in URL → skip compartido question entirely
- Complete account setup → auto-accept → redirect to Compartido

## Migration Strategy

### Data migrations (Alembic)

1. **`households.type`**: `UPDATE households SET type = 'group' WHERE type = 'couple'`
2. **`households.settlement_enabled`**: Add column, default `true`
3. **`household_members.left_at`**: Add nullable timestamp column
4. **`household_invites.invited_email`**: `ALTER COLUMN invited_email DROP NOT NULL`
5. **`transaction_splits`**: `UPDATE transaction_splits SET split_type = 'compartido' WHERE split_type = 'partner'` (if any remain)
6. **`split_ratio`**: No migration needed — existing `[50, 50]` arrays are valid N-element arrays

### Budget system

The personal budget service checks `household.type` to determine mode (`single` vs `waterfall`). Update to use `group` instead of `couple`. Waterfall logic works for N members — it already computes based on the household's total, not member count.

### RLS & database functions

- `get_partner_stats` RPC: rename to `get_member_stats`, update to return aggregates for all N members (not just the partner)
- RLS policies on `parsed_email_log` and other tables: no changes needed (they filter by `user_id`, not member count)

## Out of Scope

- Per-category split ratios (always use the group-level ratio)
- In-app debt tracking / payment recording
- Multiple compartido groups per user
- WhatsApp integration for settlements
- Email-based invites (link-only for now)
