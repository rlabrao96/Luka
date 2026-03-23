# Frontend Redesign — Tier 1 (Transactions + Dashboard)

**Date:** 2026-03-23
**Status:** Draft
**Scope:** Transactions page, Dashboard page, Budgets page, global patterns (mobile + desktop), typography

## Context

Luka's frontend is functional but generic. Most users access it on mobile where key issues exist: truncated balance values, cramped filters consuming vertical space, transaction rows lacking merchant names, and no way to edit split type. This redesign upgrades the visual quality to a professional, sophisticated level while fixing mobile usability.

## Design Direction

**Aesthetic:** Modern Bright — evolution of current Luka blue identity. Crisp whites, soft shadows, bold weights, rounded cards. Serious finance app tone, light mode only.

**Typography:** Switch from Geist Sans to **DM Sans** (Google Fonts). Geometric, clean, modern fintech feel.

**Emojis:** None in general UI. Only exception: category icons (e.g. in category picker or dashboard breakdown) to aid visual recognition.

**Global rules (all screen sizes):**
- Typography, card shadows, gradient icons, underline tabs, card-based transaction rows apply everywhere
- Color system unchanged but visual polish (shadows, gradients, spacing) upgraded across the board

**Mobile-specific rules (<lg):**
- No horizontal scrolling, ever
- Multi-card sections stack vertically
- Pickers and selectors use bottom sheets
- Touch targets minimum 44px
- Filters collapse behind icon buttons

## Transactions Page

### Balance Cards

**Current:** 3 cards in a horizontal grid (`grid-cols-3`). On mobile, values truncate ("$9...", "$2...").

**New behavior:**
- **Mobile (<lg):** Stack vertically. Each card is a full-width row: icon + label + full amount. Bank name as trailing text.
- **Desktop (lg+):** Keep current 3-column grid, no changes needed.
- Sync button stays as a standalone row above the cards (it refreshes all accounts, not just shared).

### Filters

**Current:** All filters visible at all times in a flex-wrap row. On mobile, 5 elements (search + 3 dropdowns + toggle) consume ~150px of vertical space.

**New behavior:**
- **Mobile (<lg):** Filters collapse behind a single icon button in the page header. Tapping opens a collapsible panel with all filters. A search icon button opens a search input that slides in. Active filters show as a count badge on the filter icon (count includes: non-default month, non-default bank, non-default category, and "Sin categoría" toggle — search text does NOT count). Panel includes a "Limpiar filtros" reset button when any filter is active.
- **Desktop (lg+):** No changes — filters stay visible inline.

### Tabs

**Current:** Pill-style tabs (active = blue filled pill).

**New:** Underline-style tabs. Active tab has blue text + 2px bottom border. Lighter visual weight, more modern. Note: `TabsList` container must also change — remove current `bg-white border rounded-xl p-1` wrapper styling to match the underline pattern. Switching tabs resets pagination to page 1.

### Transaction Rows

**Current:** Each row is a flex div inside a shared container. Shows: direction icon + category dropdown + split badge + amount. No merchant name visible.

**New — card-based layout:**
```
┌─────────────────────────────────────────┐
│ [icon]  Jumbo Kennedy          $45.320  │
│          BCI · Supermercado   Personal  │
└─────────────────────────────────────────┘
```

- Direction icon: gradient background (red for expense, green for income), 38px square, rounded-10
- **Line 1:** Merchant name (14px, font-weight 600) left, amount right (15px, font-weight 700). Income amounts green, expense amounts dark.
- **Line 2:** Bank name (10px, muted) + category badge (10px, slate bg) left, split badge right
- Each transaction is its own card (white bg, border, subtle shadow, rounded-12)
- Cards separated by 6px gap

**Date group headers:** Transactions grouped by day. Formatting rules:
- Today: "Hoy, DD mmm" (e.g. "Hoy, 23 mar")
- Yesterday: "Ayer, DD mmm"
- Same year: "DD mmm" (e.g. "15 feb")
- Previous year: "DD mmm YYYY" (e.g. "10 dic 2025")
- Use date-only parsing (split on "T", no timezone conversion) to match existing codebase pattern.

**Merchant name truncation:** Long names truncate with ellipsis. Amount column has `shrink-0` + `min-width` to always display fully. On 320px screens, merchant name gets ~55% of row width, amount gets ~35%.

### Category Editing

**Current:** Inline dropdown in each row.

**New:**
- **Mobile (<lg):** Tap the category badge to open a **bottom sheet**. Sheet shows full category list, scrollable, with current selection highlighted. "Sin categoría" option at top. Sheet slides up from bottom with backdrop overlay.
- **Desktop (lg+):** Keep current inline dropdown behavior.

### Split Type Editing

**Current:** Split badge is display-only. No way to change Personal/Compartido from the UI.

**New:**
- **Mobile (<lg):** Tap the split badge to open a **bottom sheet** with options: Personal, Compartido, Pareja. Current selection highlighted.
- **Desktop (lg+):** Tap the split badge to open an inline dropdown (same pattern as category).
- On selection, call API to update the transaction's split type with optimistic UI update.

**Business rules:**
- Users can only edit split type on their own transactions (RLS enforced on backend).
- Transactions from joint accounts default to "shared" but CAN be overridden by the user.
- Changing split type updates the `split_type` column on the transaction. No changes to `transaction_splits` table (splits are computed from split_type, not the other way around).

**Backend endpoint (new — does not exist yet):**
- `PATCH /transactions/{transaction_id}/split-type`
- Request body: `{ "split_type": "personal" | "shared" | "partner" }`
- Auth: requires valid JWT, RLS ensures user owns the transaction
- Response: updated transaction object
- Frontend API client: add `updateTransactionSplitType(id, splitType)` method

### Pagination

Keep current pagination controls. On mobile, simplify to just Prev/Next buttons + page indicator (remove First/Last buttons to save horizontal space).

## Dashboard Page

### KPI Cards

- **Mobile (<lg):** Stack vertically (1 column)
- **Desktop (lg+):** Keep 3-column grid

### Charts

- Keep both: SpendingChart (area, 6-month trend) and CategoryDonut (pie, current month)
- **Mobile:** Stack vertically — trend chart on top, donut below. Both full-width.
- **Desktop:** Keep current 2/3 + 1/3 grid layout.

### Recent Transactions

- Use the same card-based transaction row component as Transactions page
- Compact mode: category and split badges shown as non-interactive labels (no tap handlers). Single-line meta row below merchant name.

## Global Changes

### Typography

Replace Geist Sans with DM Sans across the entire app:
- Install via Google Fonts (next/font/google)
- Update root layout font declaration
- Update Tailwind CSS `--font-sans` variable
- Font weights needed: 400 (body), 500 (labels), 600 (merchant names, nav), 700 (headings, amounts)

### Color System

Keep existing Luka palette unchanged:
- Primary: `#2563EB` (blue-600)
- Surface: `#F0F6FF` (light blue page bg)
- Success: `#10B981`, Danger: `#EF4444`, Warning: `#F59E0B`

Add gradient tokens for direction icons:
- Expense icon bg: `linear-gradient(135deg, #fef2f2, #fecaca)`
- Income icon bg: `linear-gradient(135deg, #ecfdf5, #d1fae5)`
- Account icon bgs: blue gradient, purple gradient, emerald gradient

### Bottom Sheet Component

New reusable component for mobile interactions:
- Slides up from bottom of viewport
- Backdrop overlay (semi-transparent black, `rgba(0,0,0,0.4)`)
- Rounded top corners (16px)
- Drag handle indicator at top (32px wide, 4px tall, centered, `bg-slate-300`)
- Scrollable content area
- Closes on: backdrop tap, swipe down, or Escape key
- Animation: 300ms ease-out open, 200ms ease-in close
- Accessibility: `role="dialog"`, `aria-modal="true"`, focus trapped while open
- Rendered via React portal to `document.body`
- Used by: category editor, split type editor, filter panel (mobile)

### Card Shadows

Standardize card shadow treatment:
- Default: `0 1px 3px rgba(0,0,0,0.03)`
- Hover (desktop): `0 2px 8px rgba(0,0,0,0.06)`
- Elevated (bottom sheet): `0 -4px 24px rgba(0,0,0,0.12)`

## Budgets Page

### Month Selector

**Current:** Inline text with `‹` / `›` arrows, small touch targets.

**New:** Proper month navigation with larger tap targets (36px icon buttons), month label centered. Same visual weight as transaction page header.

### Income Display

**Current:** Single-line text "Ingresos: $X" in gray.

**New:** Promote to a card — white bg, rounded-12, subtle shadow. Income amount in 22px font-weight 700. Label "Ingresos del mes" as 11px muted text above. This gives the page a clear anchor number.

### Pace Chart

Keep current Recharts line chart. Visual improvements:
- Card wrapper matches new shadow/border standard (`0 1px 3px rgba(0,0,0,0.03)`, rounded-12)
- Use DM Sans for chart labels/tooltips
- Ensure chart is full-width on mobile with adequate padding (no clipping)

### Allocation Card

**Current:** Sliders for Hogar/Ahorro/Personal with suggestion pills.

**Mobile improvements:**
- Larger slider thumb (24px diameter, currently browser default ~16px)
- Taller track (6px instead of default 4px)
- Snap to 5% increments for easier precision
- Keep suggestion pills but make them full-width buttons on mobile
- CLP values displayed below each slider in 14px font-weight 600

**Desktop:** Same improvements apply, sliders are already usable at desktop size.

### Waterfall Cards

**Current:** Household card + Personal card with progress bars.

**Visual improvements:**
- Match new card shadow/border standard
- Progress bars: 8px height (up from default), rounded-full, gradient fills instead of flat colors
- Available balance: larger text (18px font-weight 700), green if positive, red if exceeded
- On mobile, cards stack vertically (already the case, just polish spacing)

## Out of Scope (Tier 2)

- Household page redesign
- Settings page
- Login/onboarding pages
- Dark mode
- Chart library upgrade (keep Recharts)

## Technical Notes

- Frontend changes + one new backend endpoint (split type update)
- DM Sans loaded via `next/font/google` for optimal performance
- Bottom sheet uses CSS transitions + React portal, no external library needed
- Responsive breakpoint remains `lg` (1024px) for mobile/desktop split
- All existing React Query hooks, Zustand store, and API client unchanged
- Sync button stays above all balance cards (not embedded in shared card) since it refreshes all accounts
