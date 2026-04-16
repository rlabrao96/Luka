# Budget inline config — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 5 budget-related settings sections off `/settings` and into a single accordion modal on `/budgets` triggered by a gear button, with a redesigned empty-by-default category caps editor backed by a top-5-spent picker.

**Architecture:** Frontend-first. One new modal component (`BudgetConfigModal`) composed of a shared `AccordionRow` primitive plus 5 row-specific editor components that port the mutation logic from the old settings sections verbatim. A new `CategoryCapsEditor` replaces the "20 empty rows" UX with a list-of-active-caps + picker popover. Category spend ranking reads from the existing `budget-v2` query already loaded on `/budgets` — zero new frontend API calls. One tiny backend addition (extending `/auth/me` with 3 fields) resolves a pre-existing TODO in `ContributionSection` and lets the new modal hydrate the contribution row correctly.

**Tech Stack:** Next.js 16 App Router · React 19 · TanStack Query 5 · Tailwind CSS 4 · `@radix-ui/react-dialog` (already installed) · `lucide-react` icons · DM Sans + Geist Mono (already loaded).

---

## Scope adjustment vs. spec

The spec (`docs/superpowers/specs/2026-04-15-budget-inline-config-design.md` §4.2) states the Aporte al hogar row is "seeded from `me.contribution_mode / contribution_fixed_amount / contribution_fixed_currency`". Those fields are **not** on `UserMe` today — the pre-existing `ContributionSection` has a known TODO comment about this and currently defaults to `mode="full"` on every mount, losing the real value.

**This plan adds a small backend change** (Task 1) to extend `GET /auth/me` with three fields from the caller's active `HouseholdMember` row. This is the smallest edit that lets the new modal correctly hydrate the contribution row without a new dedicated endpoint, and it fixes a bug the old section was already papering over. The rest of the plan is strictly frontend.

If the reviewer wants to preserve the "frontend-only" scope verbatim, the alternative is to accept the same limitation as today (modal always seeds with `mode="full"` on open). The plan is written for the backend-extension path; collapsing back to the frontend-only path means skipping Task 1 and setting the contribution row's initial state to hardcoded defaults in Task 10.

---

## File structure

### Files to create

| Path | Responsibility |
|------|----------------|
| `frontend/app/lib/categoryIcons.ts` | Emoji + gradient-color mapping for category pills. Default-seed categories get a hand-picked emoji; custom categories fall back to a first-letter pill. Color picked via deterministic hash. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx` | Modal shell: Radix Dialog wrapper, responsive styling (desktop centered / mobile bottom-sheet), header, footer, breadcrumb sections, accordion state machine, auto-expand logic. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/AccordionRow.tsx` | Generic row primitive. Renders icon tile + label + current-value summary + chevron when collapsed, and renders children in an animated grid-rows body when expanded. Owns the per-row auto-collapse timer. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/SavingsTargetRow.tsx` | Meta de ahorro row: amount + currency select. Ports form logic from `BudgetSettingsSection`. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/PersonalAllocationRow.tsx` | Gasto personal row: amount only (currency follows savings target currency). |
| `frontend/app/(dashboard)/components/BudgetConfigModal/PaydayRow.tsx` | Día de pago row: day-of-month select (1–31). |
| `frontend/app/(dashboard)/components/BudgetConfigModal/ContributionRow.tsx` | Aporte al hogar row: segmented control (Completa / Fija / Reembolso) + optional fixed amount input. Ports form logic from `ContributionSection`. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsRow.tsx` | Topes por categoría accordion row wrapper. Reads the active caps + spend data and renders the summary. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsEditor.tsx` | The expanded body for Topes por categoría: list of active cap rows + `+ Agregar tope` button + picker popover mount point + Guardar button + save mutation. |
| `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapPicker.tsx` | Popover-style picker: search bar + "Sugeridas · top 5" section + "Otras" section. Takes `excluded` (already-capped categories) and `categorySpend` (from the live `budget-v2` query) as props. |

### Files to modify

| Path | What changes |
|------|--------------|
| `backend/modules/auth/schemas.py` | Extend `UserResponse` with `contribution_mode`, `fixed_contribution_amount`, `fixed_contribution_currency`. |
| `backend/modules/auth/router.py` | Extend `get_me()` to select + return the new fields from `HouseholdMember`. |
| `backend/tests/test_auth.py` | Add a regression test that `/auth/me` returns contribution fields when the user has an active household membership. |
| `frontend/app/lib/api.ts` | Extend `UserMe` interface with the 3 new fields (matching the backend `UserResponse` change). |
| `frontend/app/(dashboard)/budgets/page.tsx` | Add `<button>` gear icon next to `CurrencyToggle`, local `configOpen` state, mount `<BudgetConfigModal>`. |
| `frontend/app/(dashboard)/settings/page.tsx` | Remove the 3 section imports and render calls. |

### Files to delete (at end of plan)

- `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx`
- `frontend/app/(dashboard)/settings/components/ContributionSection.tsx`
- `frontend/app/(dashboard)/settings/components/CategoryBudgetsSection.tsx`

---

## Testing strategy

**Backend (Task 1):** real pytest coverage with the existing `mock_user` / `override_auth` fixtures. Task 1 ships with a failing test first, then the implementation.

**Frontend (Tasks 2–14):** no unit tests. The frontend has no test infrastructure (confirmed in `NEXT-STEPS.md`). Each frontend task uses this gate instead:

1. Write the code.
2. Run `cd frontend && npm run build` — must pass with zero new TypeScript errors.
3. Commit.

Task 15 is a dedicated manual UAT sweep covering the full spec §7 checklist, including mobile viewport.

---

## Task 1 — Backend: extend `/auth/me` with contribution fields

**Files:**
- Modify: `backend/modules/auth/schemas.py`
- Modify: `backend/modules/auth/router.py:29-52`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing test**

Add this test to `backend/tests/test_auth.py` (append after the existing `test_get_me_returns_user_when_authenticated`):

```python
@pytest.mark.asyncio
async def test_get_me_includes_contribution_fields_for_household_member(
    app, mock_user, mock_partner
):
    """Regression — /auth/me must expose contribution fields for the active membership.

    Previously the frontend ContributionSection defaulted to mode='full' on every mount
    because there was no way to read the current value. Adding the fields here closes
    that gap and lets the budget config modal hydrate the row correctly.
    """
    from decimal import Decimal
    from core.database import get_db
    from core.security import get_current_user
    from modules.auth.models import User
    from modules.households.models import Household, HouseholdMember
    from sqlalchemy.ext.asyncio import AsyncSession

    # Use the real db fixture so the HouseholdMember round-trips through postgres.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # We need a fully wired session, not the mock one. Create a household
        # and attach the contribution fields to mock_user's membership.
        from backend.tests.conftest import db as _  # noqa: F401  (import triggers fixture)
        # Fall back to a direct override — simpler than wiring the real db here:
        hid = uuid.uuid4()
        async def override_get_current_user():
            return mock_user

        captured = {}

        async def override_get_db():
            # Yield a minimal async stub that returns a single HouseholdMember row
            # with the fields populated. This mirrors the pattern in test_auth.py
            # for tests that don't need a real DB.
            from unittest.mock import AsyncMock, MagicMock
            session = AsyncMock()
            result = MagicMock()
            result.first = MagicMock(return_value=(hid, "fixed", Decimal("800000"), "CLP"))
            session.execute = AsyncMock(return_value=result)
            yield session

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = await client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["contribution_mode"] == "fixed"
    assert body["fixed_contribution_amount"] == "800000.00"
    assert body["fixed_contribution_currency"] == "CLP"
    assert body["household_id"] == str(hid)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && pytest tests/test_auth.py::test_get_me_includes_contribution_fields_for_household_member -v
```

Expected: FAIL — the response will be missing the three new fields (KeyError on `body["contribution_mode"]`).

- [ ] **Step 3: Extend the Pydantic schema**

In `backend/modules/auth/schemas.py`, modify `UserResponse`:

```python
import uuid
from decimal import Decimal
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool
    phone_whatsapp: str | None = None
    preferred_currency: str = "CLP"
    household_id: uuid.UUID | None = None
    # Contribution mode for the caller's active HouseholdMember row.
    # Null when the user has no active household membership.
    contribution_mode: str | None = None
    fixed_contribution_amount: Decimal | None = None
    fixed_contribution_currency: str | None = None
    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Extend the `/auth/me` handler to select + return the new fields**

In `backend/modules/auth/router.py`, replace the body of `get_me()` (lines 29–52):

```python
@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            HouseholdMember.household_id,
            HouseholdMember.contribution_mode,
            HouseholdMember.fixed_contribution_amount,
            HouseholdMember.fixed_contribution_currency,
        ).where(
            HouseholdMember.user_id == current_user.id,
            HouseholdMember.left_at.is_(None),
        )
    )
    row = result.first()
    household_id = row[0] if row else None
    contribution_mode = row[1] if row else None
    fixed_contribution_amount = row[2] if row else None
    fixed_contribution_currency = row[3] if row else None

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_provider=current_user.email_provider,
        whatsapp_verified=current_user.whatsapp_verified,
        phone_whatsapp=current_user.phone_whatsapp,
        preferred_currency=current_user.preferred_currency,
        household_id=household_id,
        contribution_mode=contribution_mode,
        fixed_contribution_amount=fixed_contribution_amount,
        fixed_contribution_currency=fixed_contribution_currency,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd backend && pytest tests/test_auth.py::test_get_me_includes_contribution_fields_for_household_member -v
```

Expected: PASS.

- [ ] **Step 6: Run the full auth test file to catch regressions**

```bash
cd backend && pytest tests/test_auth.py -v
```

Expected: all tests pass. The existing `test_get_me_returns_user_when_authenticated` should still pass — the new fields default to `None` and aren't asserted on.

- [ ] **Step 7: Commit**

```bash
git add backend/modules/auth/schemas.py backend/modules/auth/router.py backend/tests/test_auth.py
git commit -m "$(cat <<'EOF'
feat(auth): expose contribution fields on /auth/me

Closes a pre-existing TODO in ContributionSection — the frontend had no
way to read the current contribution_mode, so it defaulted to "full" on
every mount. /auth/me now returns contribution_mode, fixed_contribution_amount,
and fixed_contribution_currency from the caller's active household membership.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Frontend: extend `UserMe` interface to match

**Files:**
- Modify: `frontend/app/lib/api.ts:31-40`

- [ ] **Step 1: Update the interface**

Replace the `UserMe` interface in `frontend/app/lib/api.ts`:

```ts
export interface UserMe {
  id: string;
  email: string;
  full_name: string;
  email_provider: string;
  whatsapp_verified: boolean;
  phone_whatsapp: string | null;
  preferred_currency: string;
  household_id: string | null;
  // Contribution fields for the caller's active household membership.
  // Null when the user has no active membership.
  contribution_mode: "full" | "fixed" | "reimbursement" | null;
  fixed_contribution_amount: number | null;
  fixed_contribution_currency: string | null;
}
```

- [ ] **Step 2: Run the type-check to verify nothing breaks**

```bash
cd frontend && npm run build
```

Expected: build passes. The three new fields are optional (nullable) so nothing that previously read `UserMe` needs to change.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/api.ts
git commit -m "feat(frontend): add contribution fields to UserMe type

Mirrors the /auth/me backend extension. Nullable so no existing consumer
code has to change.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Frontend: create `categoryIcons.ts`

**Files:**
- Create: `frontend/app/lib/categoryIcons.ts`

- [ ] **Step 1: Create the file**

Create `frontend/app/lib/categoryIcons.ts` with the full contents:

```ts
/**
 * Category icon + color mapping for the budget config modal.
 *
 * Each expense category from the default seed gets a hand-picked emoji
 * and a gradient color theme for the pill background. Unknown or custom
 * categories fall back to a first-letter pill + a deterministic color
 * picked from the name hash.
 *
 * Additive-only: adding a new entry never breaks an existing one.
 */

export type CategoryPillTheme = "amber" | "green" | "pink" | "blue" | "purple";

export const PILL_GRADIENTS: Record<CategoryPillTheme, string> = {
  amber: "linear-gradient(135deg, #FEF3C7, #FDE68A)",
  green: "linear-gradient(135deg, #D1FAE5, #A7F3D0)",
  pink: "linear-gradient(135deg, #FCE7F3, #FBCFE8)",
  blue: "linear-gradient(135deg, #DBEAFE, #BFDBFE)",
  purple: "linear-gradient(135deg, #E9D5FF, #DDD6FE)",
};

type CategoryIconSpec = { emoji: string; theme: CategoryPillTheme };

// Default-seed expense categories. Keys must match the Spanish labels
// used by modules/settings and the category_preferences table.
const EXPENSE_ICONS: Record<string, CategoryIconSpec> = {
  "Supermercado": { emoji: "🛒", theme: "green" },
  "Restaurantes": { emoji: "🍽️", theme: "pink" },
  "Transporte": { emoji: "🚗", theme: "blue" },
  "Combustible": { emoji: "⛽", theme: "amber" },
  "Entretenimiento": { emoji: "🎬", theme: "purple" },
  "Salud": { emoji: "💊", theme: "pink" },
  "Educación": { emoji: "📚", theme: "blue" },
  "Servicios del hogar": { emoji: "🏠", theme: "purple" },
  "Ropa": { emoji: "👕", theme: "pink" },
  "Tecnología": { emoji: "💻", theme: "blue" },
  "Viajes": { emoji: "✈️", theme: "blue" },
  "Cuidado personal": { emoji: "💈", theme: "pink" },
  "Regalos": { emoji: "🎁", theme: "amber" },
  "Mascotas": { emoji: "🐾", theme: "amber" },
  "Suscripciones": { emoji: "🔁", theme: "purple" },
  "Seguros": { emoji: "🛡️", theme: "blue" },
  "Impuestos": { emoji: "🧾", theme: "amber" },
  "Deporte": { emoji: "🏋️", theme: "green" },
  "Niños": { emoji: "🧸", theme: "pink" },
  "Otros gastos": { emoji: "💸", theme: "purple" },
};

const THEMES: CategoryPillTheme[] = ["amber", "green", "pink", "blue", "purple"];

/**
 * Deterministic theme for an arbitrary category name.
 * Uses the sum of char codes mod 5 so the same name always resolves to
 * the same theme across sessions and users.
 */
function themeFromName(name: string): CategoryPillTheme {
  let sum = 0;
  for (let i = 0; i < name.length; i++) sum += name.charCodeAt(i);
  return THEMES[sum % THEMES.length];
}

export function getCategoryIcon(category: string): {
  emoji: string;
  theme: CategoryPillTheme;
  gradient: string;
} {
  const known = EXPENSE_ICONS[category];
  if (known) {
    return { ...known, gradient: PILL_GRADIENTS[known.theme] };
  }
  const theme = themeFromName(category);
  return {
    emoji: category.trim().charAt(0).toUpperCase() || "?",
    theme,
    gradient: PILL_GRADIENTS[theme],
  };
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/lib/categoryIcons.ts
git commit -m "feat(frontend): add category icon + gradient mapping

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Frontend: create `AccordionRow` primitive

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/AccordionRow.tsx`

This is the shared row primitive. It owns the collapsed summary rendering, the expand chevron, the animated body, and the "auto-collapse after save" timer. Each row-specific component (`SavingsTargetRow`, etc.) wraps it with its own body content and saved-state signal.

- [ ] **Step 1: Create the file**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/AccordionRow.tsx`:

```tsx
"use client";

import { useEffect, useId, useRef } from "react";
import { ChevronRight } from "lucide-react";

export interface AccordionRowProps {
  /** Unique id so the parent can track which row is expanded. */
  id: string;
  /** Whether this row is the currently-expanded one. */
  expanded: boolean;
  /** Toggle callback from the parent state machine. */
  onToggle: (id: string) => void;
  /** Icon node rendered inside the 42x42 tile (e.g. <Target size={20} />). */
  icon: React.ReactNode;
  /** Small uppercase label, e.g. "Meta de ahorro". */
  label: string;
  /** Main value text, e.g. "$300.000" or "Sin meta". */
  valuePrimary: string;
  /** Muted unit text rendered in Geist Mono next to the primary value. */
  valueUnit?: string;
  /** Italic "empty" state — when true, the primary value renders muted + italic. */
  empty?: boolean;
  /**
   * Signal that a save just succeeded. Incrementing this number triggers
   * the auto-collapse timer inside the row. The parent increments it from
   * inside the save mutation's onSuccess.
   */
  savedTick?: number;
  /** Expanded body content (the editor form). */
  children: React.ReactNode;
}

export function AccordionRow({
  id,
  expanded,
  onToggle,
  icon,
  label,
  valuePrimary,
  valueUnit,
  empty = false,
  savedTick = 0,
  children,
}: AccordionRowProps) {
  const bodyId = useId();
  // Auto-collapse 900ms after a successful save.
  // Cancelled if the row is collapsed in the meantime (e.g. the user
  // expanded another row, or the modal closed and `expanded` flipped to false).
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (savedTick === 0) return;
    timerRef.current = setTimeout(() => {
      onToggle(id);
    }, 900);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedTick]);

  // Cancel the timer if the parent collapses this row from outside
  // (e.g. the user clicked a different row).
  useEffect(() => {
    if (!expanded && timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [expanded]);

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => onToggle(id)}
        className={`
          w-full text-left grid grid-cols-[42px_1fr_auto] items-center gap-3.5
          rounded-2xl px-4 py-3.5 transition-colors
          hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary/30
          ${expanded ? "bg-gradient-to-b from-[#F5F9FF] to-transparent" : ""}
        `}
      >
        {expanded && (
          <span
            aria-hidden
            className="absolute left-1 top-3.5 bottom-3.5 w-[3px] rounded-sm bg-gradient-to-b from-luka-primary to-luka-sky"
          />
        )}
        <span
          className="w-[42px] h-[42px] rounded-xl flex items-center justify-center text-luka-primary"
          style={{ background: "linear-gradient(135deg, #EFF6FF, #DBEAFE)" }}
        >
          {icon}
        </span>
        <span className="min-w-0">
          <span className="block text-[10.5px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            {label}
          </span>
          <span
            className={`block text-[15px] font-bold text-slate-900 truncate ${
              empty ? "italic font-medium text-slate-500" : ""
            }`}
          >
            {valuePrimary}
            {valueUnit && (
              <span className="ml-1.5 font-[var(--font-geist-mono)] font-medium text-[12px] text-slate-500">
                {valueUnit}
              </span>
            )}
          </span>
        </span>
        <ChevronRight
          size={18}
          className={`text-slate-400 transition-transform duration-[260ms] ease-[cubic-bezier(.2,.9,.25,1)] ${
            expanded ? "rotate-90 text-luka-primary" : ""
          }`}
        />
      </button>
      <div
        id={bodyId}
        role="region"
        aria-hidden={!expanded}
        className="grid transition-[grid-template-rows] duration-[280ms] ease-[cubic-bezier(.2,.9,.25,1)]"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden min-h-0">
          <div className="pt-1 pb-4 pl-[72px] pr-4">{children}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS. The component is self-contained and has no consumers yet.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/AccordionRow.tsx
git commit -m "feat(frontend): add AccordionRow primitive for budget config modal

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Frontend: create `BudgetConfigModal` shell

The shell renders the Radix Dialog, the header, the footer, the three breadcrumb section labels, and an empty accordion for now. Individual row components land in Tasks 6–11.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`

- [ ] **Step 1: Create the shell**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/app/lib/api";
import type { BudgetV2Response } from "@/app/lib/api";

export interface BudgetConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  householdId: string | null;
  month: string; // YYYY-MM-01
  /** Live household-view budget-v2 response for per-category spend lookups. */
  householdBudget: BudgetV2Response | undefined;
}

// Row ids used by the accordion state machine.
export type BudgetConfigRowId =
  | "savings"
  | "personal"
  | "payday"
  | "contribution"
  | "caps";

export function BudgetConfigModal({
  open,
  onOpenChange,
  householdId,
  month,
  householdBudget,
}: BudgetConfigModalProps) {
  // One row expanded at a time. null = all collapsed.
  const [expandedRow, setExpandedRow] = useState<BudgetConfigRowId | null>(null);

  // Prefetch the mutable data the individual rows need. We load it here
  // so the rows can read it via the query cache without each one
  // re-requesting on mount.
  const budgetSettings = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
    enabled: open,
    staleTime: 30 * 1000,
  });

  // First-open auto-expand logic. `needsSetup` is the one-time nudge:
  // if the user has no savings target AND no payday set, expand
  // Meta de ahorro on first open. The nudge only fires once per modal open.
  useEffect(() => {
    if (!open) {
      setExpandedRow(null);
      return;
    }
    if (!budgetSettings.data) return;
    const needsSetup =
      budgetSettings.data.savings_target_amount == null ||
      budgetSettings.data.payday_day_of_month == null;
    if (needsSetup) setExpandedRow("savings");
    // Only run once per open — the dep list intentionally omits expandedRow.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, budgetSettings.data]);

  function toggleRow(id: BudgetConfigRowId) {
    setExpandedRow((prev) => (prev === id ? null : id));
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm
                     data-[state=open]:animate-in data-[state=closed]:animate-out
                     data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />
        <Dialog.Content
          aria-describedby={undefined}
          className="
            fixed z-50
            left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-md max-h-[90vh]
            -translate-x-1/2 -translate-y-1/2
            bg-white rounded-2xl overflow-hidden flex flex-col
            shadow-[0_24px_64px_-16px_rgba(15,23,42,0.22),0_8px_24px_-12px_rgba(15,23,42,0.10)]
            data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[.985]
            data-[state=closed]:animate-out data-[state=closed]:fade-out-0
            max-md:top-auto max-md:bottom-0 max-md:left-0 max-md:translate-x-0 max-md:translate-y-0
            max-md:w-full max-md:max-w-full max-md:rounded-2xl max-md:rounded-b-none
            max-md:data-[state=open]:animate-slide-up
          "
        >
          {/* Mobile drag handle */}
          <div className="flex md:hidden justify-center pt-3 pb-1" aria-hidden>
            <div className="h-1 w-10 rounded-full bg-slate-200" />
          </div>

          {/* Header */}
          <div
            className="relative px-6 pt-5 pb-4 border-b border-slate-100"
            style={{
              background:
                "radial-gradient(1200px 200px at 90% -20%, rgba(96,165,250,0.18), transparent 60%), linear-gradient(180deg, #FFFFFF 0%, #F6FAFF 100%)",
            }}
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-luka-primary">
              Configurar presupuesto
            </div>
            <Dialog.Title className="text-[22px] font-bold text-luka-dark mt-1 tracking-[-0.02em]">
              Tu plan de este mes
            </Dialog.Title>
            <Dialog.Description className="text-[12.5px] text-slate-500 mt-0.5">
              Todos los números que alimentan el Sankey, en un solo lugar.
            </Dialog.Description>
            <Dialog.Close
              aria-label="Cerrar"
              className="absolute top-4 right-4 w-8 h-8 rounded-[9px] bg-slate-900/[0.04] hover:bg-slate-900/10 flex items-center justify-center transition-colors"
            >
              <X size={16} className="text-slate-700" />
            </Dialog.Close>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto pb-2">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Mi plan
            </div>
            <div className="px-2 space-y-0.5">
              {/* SavingsTargetRow / PersonalAllocationRow / PaydayRow land here in Tasks 6-8 */}
            </div>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Hogar
            </div>
            <div className="px-2 space-y-0.5">
              {/* ContributionRow lands here in Task 9 */}
            </div>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Categorías
            </div>
            <div className="px-2 space-y-0.5 pb-2">
              {/* CategoryCapsRow lands here in Task 11 */}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-3.5 border-t border-slate-100 bg-[#FAFBFF] flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11.5px] text-slate-500">
              <kbd className="bg-white border border-slate-200 rounded-[5px] px-1.5 py-0.5 font-[var(--font-geist-mono)] text-[10.5px]">
                Esc
              </kbd>
              <span>para cerrar</span>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4.5 py-2.5 shadow-[0_2px_10px_rgba(37,99,235,0.30)] hover:bg-luka-primary-dark transition-colors"
              >
                Listo
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// Suppress the unused-prop TS warnings for props that land in Tasks 6-11.
// The modal consumers (budgets/page.tsx) will pass them from the get-go.
type _UsedLater = Pick<BudgetConfigModalProps, "householdId" | "month" | "householdBudget">;
type _Touch = keyof _UsedLater extends never ? never : _UsedLater;
```

> **Note:** The `_UsedLater` type alias at the end is a tiny trick to silence "prop declared but unused" TS errors during the intermediate steps where the rows haven't landed yet. It compiles to zero runtime code and gets used for real in Tasks 6–11. Remove it after Task 11.

- [ ] **Step 2: Verify the type of `api.getBudgetSettings`**

The type import at the top of the file uses `BudgetV2Response`. Confirm this exists in `frontend/app/lib/api.ts`:

```bash
grep -n "export interface BudgetV2Response\|export type BudgetV2Response" "frontend/app/lib/api.ts"
```

Expected: one match (around line 887).

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS. The shell compiles but has no consumers yet.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/index.tsx
git commit -m "feat(frontend): BudgetConfigModal shell with header + breadcrumbs

Radix Dialog + responsive desktop/mobile styling (bottom sheet on <md).
Accordion rows land in follow-up commits.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Frontend: mount the modal + gear button on `/budgets`

Wire the modal into the page before creating the individual rows. This lets you visually verify the shell in the browser after every subsequent task.

**Files:**
- Modify: `frontend/app/(dashboard)/budgets/page.tsx`

- [ ] **Step 1: Add the gear button and modal mount**

In `frontend/app/(dashboard)/budgets/page.tsx`, at the top of the file, add the new imports:

```tsx
import { Settings2 } from "lucide-react";
import { BudgetConfigModal } from "@/app/(dashboard)/components/BudgetConfigModal";
```

Inside `BudgetsPage`, just before the existing `return`, add:

```tsx
const [configOpen, setConfigOpen] = useState(false);

// Prefetch budgetSettings so the gear-button empty-state dot is accurate
// before the user opens the modal.
const budgetSettings = useQuery({
  queryKey: ["budgetSettings"],
  queryFn: () => api.getBudgetSettings(),
  staleTime: 30 * 1000,
  enabled: !!householdId,
});
const needsSetup =
  budgetSettings.data != null &&
  (budgetSettings.data.savings_target_amount == null ||
    budgetSettings.data.payday_day_of_month == null);
```

Then modify the existing header `<div className="flex items-start justify-between gap-3">` block so the right-side actions include a gear button. Replace the `{showToggle && <CurrencyToggle ... />}` block with:

```tsx
<div className="flex items-center gap-2">
  {showToggle && (
    <CurrencyToggle
      value={selectedCurrency}
      onChange={(c) => setSelectedCurrency(c as Currency)}
    />
  )}
  {householdId && (
    <button
      type="button"
      aria-label="Configurar presupuesto"
      onClick={() => setConfigOpen(true)}
      className="relative w-9 h-9 rounded-lg border border-slate-200 bg-white hover:border-luka-primary hover:-translate-y-px transition-all shadow-[var(--shadow-card)] flex items-center justify-center"
    >
      <Settings2 size={16} className="text-slate-700" />
      {needsSetup && (
        <span
          aria-hidden
          className="absolute top-1.5 right-1.5 w-[7px] h-[7px] rounded-full bg-luka-primary border-2 border-white"
        />
      )}
    </button>
  )}
</div>
```

Finally, at the end of the JSX (after the closing of the last `</section>` or inside the root `<div className="space-y-5">`), mount the modal:

```tsx
<BudgetConfigModal
  open={configOpen}
  onOpenChange={setConfigOpen}
  householdId={householdId}
  month={monthStr}
  householdBudget={household.data}
/>
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Manual smoke test**

```bash
cd frontend && npm run dev
```

Navigate to `/budgets` in a browser. Verify:
- Gear button renders next to the currency toggle
- Clicking it opens an empty modal with header/footer but no accordion rows yet
- Esc closes the modal
- On iPhone viewport (375×812, Chrome DevTools device mode), the modal becomes a bottom sheet that slides up

Stop the dev server.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/budgets/page.tsx
git commit -m "feat(frontend): mount BudgetConfigModal on /budgets with gear trigger

Empty-state blue dot on the gear button when savings target or payday
is not yet configured.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Frontend: `SavingsTargetRow`

Ports the `Meta de ahorro` form from `BudgetSettingsSection`.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/SavingsTargetRow.tsx`
- Modify: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx` (wire the row)

- [ ] **Step 1: Create the row component**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/SavingsTargetRow.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Target, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

interface Props {
  expanded: boolean;
  onToggle: (id: "savings") => void;
}

const CURRENCIES = ["CLP", "USD"] as const;

function formatAmount(n: number | null, currency: string | null): string {
  if (n == null) return "Sin meta";
  if (currency === "USD") return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export function SavingsTargetRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("CLP");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setAmount(
      current.savings_target_amount != null ? String(current.savings_target_amount) : ""
    );
    setCurrency(current.savings_target_currency ?? "CLP");
  }, [current]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: amount ? Number(amount) : null,
        savings_target_currency: amount ? currency : null,
        payday_day_of_month: current?.payday_day_of_month ?? null,
        personal_allocation_amount: current?.personal_allocation_amount ?? null,
        personal_allocation_currency: current?.personal_allocation_currency ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgetSettings"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  return (
    <AccordionRow
      id="savings"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "savings")}
      icon={<Target size={20} />}
      label="Meta de ahorro"
      valuePrimary={formatAmount(
        current?.savings_target_amount ?? null,
        current?.savings_target_currency ?? null
      )}
      valueUnit={
        current?.savings_target_amount != null
          ? `${current.savings_target_currency ?? "CLP"} / mes`
          : undefined
      }
      empty={current?.savings_target_amount == null}
      savedTick={savedTick}
    >
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Ej. 300000"
          className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary font-[var(--font-geist-mono)]"
        />
        <select
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          className="w-20 rounded-[11px] border border-slate-200 px-2 py-2.5 text-[12px] font-[var(--font-geist-mono)] font-medium text-slate-500 bg-white text-center"
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Transacciones en categorías de ahorro/inversión cuentan hacia esta meta.
      </p>
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </AccordionRow>
  );
}
```

- [ ] **Step 2: Wire the row into the modal**

In `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`, add the import at the top:

```tsx
import { SavingsTargetRow } from "./SavingsTargetRow";
```

Replace the `"Mi plan"` section's empty `<div>` with the row:

```tsx
<div className="px-2 space-y-0.5">
  <SavingsTargetRow
    expanded={expandedRow === "savings"}
    onToggle={toggleRow}
  />
</div>
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual smoke test**

```bash
cd frontend && npm run dev
```

Navigate to `/budgets`, open the modal, verify:
- Meta de ahorro row appears under "Mi plan"
- Clicking it expands smoothly
- The amount input is pre-seeded from the current value
- Entering a new value and clicking Guardar → "Guardado ✓" chip appears
- Row auto-collapses after ~900ms
- The Sankey behind the modal updates the Meta de ahorro flow

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/
git commit -m "feat(frontend): SavingsTargetRow for budget config modal

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Frontend: `PersonalAllocationRow`

Ports the `Gasto personal` form. Same shape as `SavingsTargetRow`, without the currency select (follows the savings target currency).

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/PersonalAllocationRow.tsx`
- Modify: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`

- [ ] **Step 1: Create the row**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/PersonalAllocationRow.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { User, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

interface Props {
  expanded: boolean;
  onToggle: (id: "personal") => void;
}

function formatAmount(n: number | null, currency: string | null): string {
  if (n == null) return "Sin monto";
  if (currency === "USD") return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export function PersonalAllocationRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [amount, setAmount] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setAmount(
      current.personal_allocation_amount != null
        ? String(current.personal_allocation_amount)
        : ""
    );
  }, [current]);

  const inferredCurrency = current?.savings_target_currency ?? "CLP";

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: current?.savings_target_amount ?? null,
        savings_target_currency: current?.savings_target_currency ?? null,
        payday_day_of_month: current?.payday_day_of_month ?? null,
        personal_allocation_amount: amount ? Number(amount) : null,
        personal_allocation_currency: amount ? inferredCurrency : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgetSettings"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  return (
    <AccordionRow
      id="personal"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "personal")}
      icon={<User size={20} />}
      label="Gasto personal"
      valuePrimary={formatAmount(
        current?.personal_allocation_amount ?? null,
        current?.personal_allocation_currency ?? null
      )}
      valueUnit={
        current?.personal_allocation_amount != null
          ? `${current.personal_allocation_currency ?? "CLP"} / mes`
          : undefined
      }
      empty={current?.personal_allocation_amount == null}
      savedTick={savedTick}
    >
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Ej. 200000"
          className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary font-[var(--font-geist-mono)]"
        />
        <div className="w-20 rounded-[11px] border border-slate-200 px-2 py-2.5 text-[12px] font-[var(--font-geist-mono)] font-medium text-slate-500 bg-slate-50 text-center flex items-center justify-center">
          {inferredCurrency}
        </div>
      </div>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Monto que reservas para gasto personal cada mes. Aparece como un nodo &quot;Gasto personal&quot; en el Sankey del hogar.
      </p>
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </AccordionRow>
  );
}
```

- [ ] **Step 2: Wire the row into the modal**

In `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`, add the import:

```tsx
import { PersonalAllocationRow } from "./PersonalAllocationRow";
```

Add the row after `<SavingsTargetRow>` inside the "Mi plan" group:

```tsx
<SavingsTargetRow expanded={expandedRow === "savings"} onToggle={toggleRow} />
<PersonalAllocationRow expanded={expandedRow === "personal"} onToggle={toggleRow} />
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/
git commit -m "feat(frontend): PersonalAllocationRow for budget config modal

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — Frontend: `PaydayRow`

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/PaydayRow.tsx`
- Modify: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`

- [ ] **Step 1: Create the row**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/PaydayRow.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

interface Props {
  expanded: boolean;
  onToggle: (id: "payday") => void;
}

export function PaydayRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [day, setDay] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setDay(
      current.payday_day_of_month != null ? String(current.payday_day_of_month) : ""
    );
  }, [current]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: current?.savings_target_amount ?? null,
        savings_target_currency: current?.savings_target_currency ?? null,
        payday_day_of_month: day ? Number(day) : null,
        personal_allocation_amount: current?.personal_allocation_amount ?? null,
        personal_allocation_currency: current?.personal_allocation_currency ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgetSettings"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  return (
    <AccordionRow
      id="payday"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "payday")}
      icon={<Calendar size={20} />}
      label="Día de pago"
      valuePrimary={
        current?.payday_day_of_month != null
          ? `Día ${current.payday_day_of_month}`
          : "Sin configurar"
      }
      valueUnit={current?.payday_day_of_month != null ? "de cada mes" : undefined}
      empty={current?.payday_day_of_month == null}
      savedTick={savedTick}
    >
      <select
        value={day}
        onChange={(e) => setDay(e.target.value)}
        className="w-full sm:w-32 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white font-[var(--font-geist-mono)] focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary"
      >
        <option value="">—</option>
        {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Se usa para calcular los días restantes hasta el próximo sueldo.
      </p>
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </AccordionRow>
  );
}
```

- [ ] **Step 2: Wire into the modal**

Add the import in `index.tsx`:

```tsx
import { PaydayRow } from "./PaydayRow";
```

Append after the `PersonalAllocationRow`:

```tsx
<PaydayRow expanded={expandedRow === "payday"} onToggle={toggleRow} />
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/
git commit -m "feat(frontend): PaydayRow for budget config modal

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 — Frontend: `ContributionRow`

Ports the contribution-mode form from `ContributionSection`. Hydrates the initial state from the new `UserMe` fields added in Task 1.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/ContributionRow.tsx`
- Modify: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`

- [ ] **Step 1: Create the row**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/ContributionRow.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Home, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

type Mode = "full" | "fixed" | "reimbursement";

interface Props {
  expanded: boolean;
  onToggle: (id: "contribution") => void;
}

const MODE_LABELS: Record<Mode, string> = {
  full: "Completa",
  fixed: "Fija",
  reimbursement: "Reembolso",
};

const MODE_HELPERS: Record<Mode, string> = {
  full: "Mi ingreso real se suma al pot del hogar. Si prefieres mantener tu sueldo privado, elige Fija.",
  fixed: "Aporto un monto mensual fijo. Mi ingreso real queda privado — nadie más en el hogar lo verá.",
  reimbursement: "No aporto al pot. Mis gastos se llevan aparte y se reembolsan al final del mes.",
};

function formatAmount(n: number | null, currency: string | null): string {
  if (n == null) return "";
  if (currency === "USD") return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export function ContributionRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  const [mode, setMode] = useState<Mode>("full");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("CLP");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    setMode((me.contribution_mode as Mode | null) ?? "full");
    setAmount(
      me.fixed_contribution_amount != null ? String(me.fixed_contribution_amount) : ""
    );
    setCurrency(me.fixed_contribution_currency ?? "CLP");
  }, [me]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateContribution({
        mode,
        fixed_amount: mode === "fixed" ? Number(amount) : null,
        fixed_currency: mode === "fixed" ? currency : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["household-summary"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  const currentMode: Mode | null = (me?.contribution_mode as Mode | null) ?? null;
  const valuePrimary =
    currentMode === "fixed"
      ? `Fija (${formatAmount(me?.fixed_contribution_amount ?? null, me?.fixed_contribution_currency ?? null)})`
      : currentMode === "reimbursement"
        ? "Sólo reembolso"
        : "Completa";
  const valueUnit =
    currentMode === "fixed"
      ? "ingreso real queda privado"
      : currentMode === "reimbursement"
        ? "no aporta al pot"
        : "ingreso real se suma";

  const fixedInvalid =
    mode === "fixed" && (!amount || Number(amount) <= 0 || Number.isNaN(Number(amount)));

  return (
    <AccordionRow
      id="contribution"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "contribution")}
      icon={<Home size={20} />}
      label="Aporte al hogar"
      valuePrimary={valuePrimary}
      valueUnit={valueUnit}
      empty={currentMode == null}
      savedTick={savedTick}
    >
      <div className="grid grid-cols-3 gap-1.5 bg-slate-100 p-1 rounded-[12px]">
        {(["full", "fixed", "reimbursement"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`
              rounded-[9px] py-2.5 px-2 text-[12px] font-semibold transition-all
              ${mode === m
                ? "bg-white text-luka-dark shadow-[0_1px_2px_rgba(0,0,0,0.04),0_0_0_1px_rgba(37,99,235,0.22)]"
                : "text-slate-500 hover:text-slate-700"}
            `}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>
      <div className="text-[11.5px] text-slate-600 mt-2.5 py-2.5 px-3 bg-slate-50 rounded-[10px] border-l-2 border-luka-primary leading-[1.45]">
        {MODE_HELPERS[mode]}
      </div>
      {mode === "fixed" && (
        <div className="flex gap-2 mt-3">
          <input
            type="number"
            inputMode="numeric"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Ej. 800000"
            className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white font-[var(--font-geist-mono)] focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary"
          />
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-20 rounded-[11px] border border-slate-200 px-2 py-2.5 text-[12px] font-[var(--font-geist-mono)] font-medium text-slate-500 bg-white text-center"
          >
            <option value="CLP">CLP</option>
            <option value="USD">USD</option>
          </select>
        </div>
      )}
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || fixedInvalid}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </AccordionRow>
  );
}
```

- [ ] **Step 2: Wire into the modal**

In `index.tsx`, add the import:

```tsx
import { ContributionRow } from "./ContributionRow";
```

Replace the empty `"Hogar"` group:

```tsx
<div className="px-2 space-y-0.5">
  <ContributionRow
    expanded={expandedRow === "contribution"}
    onToggle={toggleRow}
  />
</div>
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS. This is the first commit where the new `UserMe.contribution_mode` field is read on the frontend — it's why Task 1 (backend) had to ship first.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/
git commit -m "feat(frontend): ContributionRow with segmented control + live hydration

Reads contribution_mode + fixed_contribution_amount + fixed_contribution_currency
from the extended /auth/me response. Fixes the pre-existing bug where
the old ContributionSection always defaulted to mode='full' on mount.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Frontend: `CategoryCapPicker` popover

Ships the picker first (easier to test in isolation) before wiring it into the caps editor.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapPicker.tsx`

- [ ] **Step 1: Create the picker**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapPicker.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { getCategoryIcon } from "@/app/lib/categoryIcons";

export interface PickerCategory {
  category: string;
  spend: number; // absolute value, same currency as the caller
}

export interface CategoryCapPickerProps {
  /** Every expense category in the user's category preferences. */
  allCategories: string[];
  /** Per-category spend this month, derived from the budget-v2 query. */
  spendByCategory: Record<string, number>;
  /** Categories already present in the caps list — excluded from the picker. */
  excluded: Set<string>;
  /** Called with the picked category name. */
  onPick: (category: string) => void;
  /** Currency symbol prefix, e.g. "$" or "US$". */
  formatSpend: (n: number) => string;
}

export function CategoryCapPicker({
  allCategories,
  spendByCategory,
  excluded,
  onPick,
  formatSpend,
}: CategoryCapPickerProps) {
  const [search, setSearch] = useState("");

  const candidates: PickerCategory[] = useMemo(() => {
    return allCategories
      .filter((c) => !excluded.has(c))
      .map((c) => ({ category: c, spend: spendByCategory[c] ?? 0 }))
      .sort((a, b) => b.spend - a.spend);
  }, [allCategories, spendByCategory, excluded]);

  const { suggested, other } = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const matches = needle
      ? candidates.filter((c) => c.category.toLowerCase().includes(needle))
      : candidates;
    return {
      suggested: matches.slice(0, 5).filter((c) => c.spend > 0),
      other: matches.slice(5),
    };
  }, [candidates, search]);

  return (
    <div
      className="mt-2 bg-white border border-slate-200 rounded-[14px] shadow-[0_12px_32px_-12px_rgba(15,23,42,0.18)] overflow-hidden animate-in fade-in-0 slide-in-from-top-1 duration-200"
      role="listbox"
      aria-label="Elegir categoría"
    >
      {/* Search */}
      <div className="px-3.5 py-3 border-b border-slate-100 flex items-center gap-2">
        <Search size={16} className="text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar categoría…"
          autoFocus
          className="flex-1 text-[13.5px] bg-transparent outline-none placeholder:text-slate-400"
        />
      </div>

      <div className="max-h-72 overflow-y-auto">
        {suggested.length > 0 && (
          <>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500 px-3.5 pt-2.5 pb-1">
              Sugeridas · top {suggested.length} gasto del mes
            </div>
            {suggested.map((c, i) => {
              const icon = getCategoryIcon(c.category);
              return (
                <button
                  key={c.category}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => onPick(c.category)}
                  className="w-full grid grid-cols-[32px_1fr_auto] items-center gap-2.5 px-3.5 py-2.5 text-left hover:bg-slate-50 transition-colors"
                  style={{
                    backgroundImage:
                      "linear-gradient(90deg, rgba(37,99,235,0.04), transparent)",
                  }}
                >
                  <span
                    className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                    style={{ background: icon.gradient }}
                  >
                    {icon.emoji}
                  </span>
                  <span className="text-[13.5px] font-medium text-luka-dark">
                    {c.category}
                    <span className="ml-1.5 align-middle text-[9px] font-bold uppercase tracking-[0.06em] bg-luka-primary text-white px-1.5 py-0.5 rounded">
                      top {i + 1}
                    </span>
                  </span>
                  <span className="text-[11px] text-slate-500 font-[var(--font-geist-mono)]">
                    {formatSpend(c.spend)}
                  </span>
                </button>
              );
            })}
          </>
        )}
        {other.length > 0 && (
          <>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500 px-3.5 pt-2.5 pb-1">
              Otras
            </div>
            {other.map((c) => {
              const icon = getCategoryIcon(c.category);
              return (
                <button
                  key={c.category}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => onPick(c.category)}
                  className="w-full grid grid-cols-[32px_1fr_auto] items-center gap-2.5 px-3.5 py-2.5 text-left hover:bg-slate-50 transition-colors"
                >
                  <span
                    className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                    style={{ background: icon.gradient }}
                  >
                    {icon.emoji}
                  </span>
                  <span className="text-[13.5px] font-medium text-luka-dark">{c.category}</span>
                  <span className="text-[11px] text-slate-500 font-[var(--font-geist-mono)]">
                    {c.spend > 0 ? formatSpend(c.spend) : "—"}
                  </span>
                </button>
              );
            })}
          </>
        )}
        {suggested.length === 0 && other.length === 0 && (
          <div className="px-3.5 py-4 text-center text-[12px] text-slate-500">
            No hay categorías disponibles.
          </div>
        )}
      </div>
      <div className="px-3.5 py-2.5 border-t border-slate-100 bg-[#FAFBFF] text-[11px] text-slate-500">
        {candidates.length} categoría{candidates.length === 1 ? "" : "s"} restante{candidates.length === 1 ? "" : "s"}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/CategoryCapPicker.tsx
git commit -m "feat(frontend): CategoryCapPicker popover with top-5 spend suggestions

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 12 — Frontend: `CategoryCapsEditor`

The body of the Topes por categoría row. Renders the list of active caps, the `+ Agregar tope` button (which mounts the picker), and the Guardar button that submits the full list.

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsEditor.tsx`

- [ ] **Step 1: Create the editor**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsEditor.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X, Check } from "lucide-react";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { getCategoryIcon } from "@/app/lib/categoryIcons";
import { CategoryCapPicker } from "./CategoryCapPicker";

interface Props {
  householdId: string;
  month: string;
  householdBudget: BudgetV2Response | undefined;
  onSaved: () => void;
}

function formatSpend(n: number, currency: string): string {
  if (currency === "USD") {
    return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

/** Derive per-category spend from the Sankey `spent_<cat>` nodes. */
function spendByCategoryFrom(budget: BudgetV2Response | undefined): Record<string, number> {
  if (!budget) return {};
  const map: Record<string, number> = {};
  for (const node of budget.sankey.nodes) {
    if (node.id.startsWith("spent_")) {
      const cat = node.label ?? node.id.slice("spent_".length);
      map[cat] = Math.abs(Number(node.value) || 0);
    }
  }
  return map;
}

export function CategoryCapsEditor({
  householdId,
  month,
  householdBudget,
  onSaved,
}: Props) {
  const queryClient = useQueryClient();

  const prefs = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: 5 * 60 * 1000,
  });
  const budgets = useQuery({
    queryKey: ["category-budgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId, month),
  });

  // Local draft: category → amount as a string. Only includes
  // categories the user intends to cap (uncapped categories are absent).
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [pickerOpen, setPickerOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedTick, setSavedTick] = useState(0);

  useEffect(() => {
    if (!budgets.data) return;
    const seed: Record<string, string> = {};
    for (const b of budgets.data.budgets) {
      if (b.amount > 0) seed[b.category] = String(b.amount);
    }
    setDraft(seed);
  }, [budgets.data]);

  const allExpenseCategories = useMemo(
    () =>
      (prefs.data?.categories ?? [])
        .filter((c) => c.category_type === "expense")
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((c) => c.category),
    [prefs.data]
  );

  const spendByCategory = useMemo(
    () => spendByCategoryFrom(householdBudget),
    [householdBudget]
  );

  const currency = householdBudget?.currency ?? "CLP";

  const mutation = useMutation({
    mutationFn: () => {
      const items = Object.entries(draft)
        .map(([category, raw]) => ({ category, amount: raw ? Number(raw) : 0 }))
        .filter((b) => b.amount > 0);
      return api.setCategoryBudgets(householdId, { month, budgets: items });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-budgets", householdId, month] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2", householdId] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
      onSaved();
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  const activeCaps = Object.keys(draft);
  const excluded = new Set(activeCaps);

  function handlePick(category: string) {
    setDraft((d) => ({ ...d, [category]: "" }));
    setPickerOpen(false);
    // Scroll focus to the new row on the next tick.
    setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>(
        `input[data-cap-input="${category}"]`
      );
      el?.focus();
    }, 60);
  }

  function handleRemove(category: string) {
    setDraft((d) => {
      const next = { ...d };
      delete next[category];
      return next;
    });
  }

  function handleChange(category: string, raw: string) {
    setDraft((d) => ({ ...d, [category]: raw }));
  }

  const isLoading = prefs.isPending || budgets.isPending;

  return (
    <div>
      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-12 rounded-[11px] bg-slate-100 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {activeCaps.map((category) => {
            const icon = getCategoryIcon(category);
            const spend = spendByCategory[category] ?? 0;
            return (
              <div
                key={category}
                className="grid grid-cols-[32px_1fr_130px_26px] items-center gap-2.5 px-2.5 py-2 rounded-[11px] bg-slate-50 border border-slate-100 hover:border-slate-200 hover:bg-white transition-all animate-in fade-in-0 zoom-in-[.98] duration-200"
              >
                <span
                  className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                  style={{ background: icon.gradient }}
                >
                  {icon.emoji}
                </span>
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium text-luka-dark truncate">
                    {category}
                  </div>
                  {spend > 0 && (
                    <div className="text-[10.5px] text-slate-500">
                      Gastado: {formatSpend(spend, currency)}
                    </div>
                  )}
                </div>
                <input
                  type="number"
                  inputMode="numeric"
                  min="0"
                  data-cap-input={category}
                  value={draft[category]}
                  onChange={(e) => handleChange(category, e.target.value)}
                  placeholder="Tu tope"
                  className="w-full rounded-[9px] bg-white border border-slate-200 px-2.5 py-1.5 text-[12.5px] text-right font-[var(--font-geist-mono)] text-luka-dark focus:outline-none focus:ring-2 focus:ring-luka-primary/20 focus:border-luka-primary placeholder:italic placeholder:text-slate-400"
                />
                <button
                  type="button"
                  onClick={() => handleRemove(category)}
                  aria-label={`Quitar tope de ${category}`}
                  className="w-6 h-6 rounded-[8px] flex items-center justify-center text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}

          <button
            type="button"
            onClick={() => setPickerOpen((v) => !v)}
            className="w-full mt-2 py-2.5 px-3.5 rounded-[12px] border border-dashed border-slate-300 text-[13px] font-semibold text-luka-primary hover:border-luka-primary hover:border-solid hover:bg-luka-primary/[0.04] transition-all flex items-center justify-center gap-1.5"
          >
            <Plus size={16} strokeWidth={2.4} />
            Agregar tope
          </button>

          {pickerOpen && (
            <CategoryCapPicker
              allCategories={allExpenseCategories}
              spendByCategory={spendByCategory}
              excluded={excluded}
              onPick={handlePick}
              formatSpend={(n) => formatSpend(n, currency)}
            />
          )}

          <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
            Sólo se muestran las categorías con tope activo. Toca <strong>+ Agregar tope</strong> para incluir otra.
          </p>
        </div>
      )}

      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || isLoading}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar topes"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/CategoryCapsEditor.tsx
git commit -m "feat(frontend): CategoryCapsEditor with active-only list + picker

Empty-by-default UX: only categories with an active cap render.
The picker appears inline below the + Agregar tope button; picking
a category adds a pre-focused row to the draft.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 13 — Frontend: `CategoryCapsRow` wrapper + wire into modal

**Files:**
- Create: `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsRow.tsx`
- Modify: `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`

- [ ] **Step 1: Create the row wrapper**

Create `frontend/app/(dashboard)/components/BudgetConfigModal/CategoryCapsRow.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Grid3x3 } from "lucide-react";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";
import { CategoryCapsEditor } from "./CategoryCapsEditor";

interface Props {
  expanded: boolean;
  onToggle: (id: "caps") => void;
  householdId: string | null;
  month: string;
  householdBudget: BudgetV2Response | undefined;
}

function formatTotal(n: number, currency: string): string {
  if (currency === "USD") {
    return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export function CategoryCapsRow({
  expanded,
  onToggle,
  householdId,
  month,
  householdBudget,
}: Props) {
  const [savedTick, setSavedTick] = useState(0);
  const budgets = useQuery({
    queryKey: ["category-budgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId as string, month),
    enabled: !!householdId,
  });

  const summary = useMemo(() => {
    const saved = budgets.data?.budgets?.filter((b) => b.amount > 0) ?? [];
    const count = saved.length;
    const total = saved.reduce((sum, b) => sum + b.amount, 0);
    return { count, total };
  }, [budgets.data]);

  const currency = householdBudget?.currency ?? "CLP";

  const valuePrimary =
    summary.count === 0
      ? "Sin topes"
      : `${summary.count} tope${summary.count === 1 ? "" : "s"} activo${summary.count === 1 ? "" : "s"}`;
  const valueUnit = summary.count === 0
    ? undefined
    : `${formatTotal(summary.total, currency)} cubiertos`;

  return (
    <AccordionRow
      id="caps"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "caps")}
      icon={<Grid3x3 size={20} />}
      label="Topes por categoría"
      valuePrimary={valuePrimary}
      valueUnit={valueUnit}
      empty={summary.count === 0}
      savedTick={savedTick}
    >
      {householdId && (
        <CategoryCapsEditor
          householdId={householdId}
          month={month}
          householdBudget={householdBudget}
          onSaved={() => setSavedTick((n) => n + 1)}
        />
      )}
    </AccordionRow>
  );
}
```

- [ ] **Step 2: Wire into the modal**

In `frontend/app/(dashboard)/components/BudgetConfigModal/index.tsx`:

Add the import:

```tsx
import { CategoryCapsRow } from "./CategoryCapsRow";
```

Replace the empty `"Categorías"` group with:

```tsx
<div className="px-2 space-y-0.5 pb-2">
  <CategoryCapsRow
    expanded={expandedRow === "caps"}
    onToggle={toggleRow}
    householdId={householdId}
    month={month}
    householdBudget={householdBudget}
  />
</div>
```

Now that all 5 rows are wired, **delete the `_UsedLater` / `_Touch` type aliases at the bottom of `index.tsx`** — they were scaffolding for intermediate type-check passes.

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Manual smoke test**

```bash
cd frontend && npm run dev
```

Navigate to `/budgets` and verify the full flow end-to-end:
- Gear button opens the modal
- All 5 rows render with correct current values
- Each row expands/collapses smoothly
- Each row saves individually
- The caps row empty state shows only the `+ Agregar tope` button
- Clicking the button opens the picker
- Top 5 suggested categories appear with badges
- Picking a category adds a row pre-focused
- Entering a value and clicking Guardar topes saves and the Sankey updates

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/components/BudgetConfigModal/
git commit -m "feat(frontend): wire CategoryCapsRow into budget config modal

All 5 accordion rows now live in the modal. Drops the intermediate
_UsedLater scaffolding type from Task 5.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 14 — Remove old settings sections

Now that the modal owns all budget config, strip the three old sections from `/settings`.

**Files:**
- Modify: `frontend/app/(dashboard)/settings/page.tsx`
- Delete: `frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx`
- Delete: `frontend/app/(dashboard)/settings/components/ContributionSection.tsx`
- Delete: `frontend/app/(dashboard)/settings/components/CategoryBudgetsSection.tsx`

- [ ] **Step 1: Update `settings/page.tsx`**

Remove the three imports:

```tsx
// DELETE these lines
import { ContributionSection } from "./components/ContributionSection";
import { BudgetSettingsSection } from "./components/BudgetSettingsSection";
import { CategoryBudgetsSection } from "./components/CategoryBudgetsSection";
```

Remove the three render calls from the JSX:

```tsx
// DELETE these three lines
<ContributionSection />
<BudgetSettingsSection />
<CategoryBudgetsSection />
```

The final file structure for `/settings` should render in this order: `ProfileSection` · `TransactionsConfigSection` · `BankAccountsSection` · `CompartidoSection` · `NotificationsSection` · `CategoriesSection` · `PrivacySection` · `DeleteAccountSection`.

- [ ] **Step 2: Delete the three component files**

```bash
rm "frontend/app/(dashboard)/settings/components/BudgetSettingsSection.tsx"
rm "frontend/app/(dashboard)/settings/components/ContributionSection.tsx"
rm "frontend/app/(dashboard)/settings/components/CategoryBudgetsSection.tsx"
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && npm run build
```

Expected: PASS. The budget config modal is the only consumer of `getBudgetSettings`, `updateBudgetSettings`, `updateContribution`, `getCategoryBudgets`, `setCategoryBudgets` now — nothing else breaks.

- [ ] **Step 4: Smoke test**

```bash
cd frontend && npm run dev
```

Navigate to `/settings` and verify:
- No budget-related sections visible
- Page still renders without errors
- All other sections (Profile, Transactions config, Bank accounts, Compartido, Notifications, Categories, Privacy, Delete account) work as before

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/settings/
git commit -m "refactor(frontend): remove budget sections from /settings

They've been absorbed into the BudgetConfigModal on /budgets.
Settings page now focuses on identity, connections, and preferences.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 15 — Full UAT sweep + final commit

The code is done. Now validate against the spec's UAT checklist (spec §7) and fix anything that surfaces.

- [ ] **Step 1: Start the backend and frontend locally**

Open three terminal tabs:

```bash
# Tab 1: backend API
cd backend && source .venv/bin/activate && uvicorn main:app --reload

# Tab 2: ARQ fast worker (email + cron)
cd backend && source .venv/bin/activate && arq worker.FastWorkerSettings

# Tab 3: frontend
cd frontend && npm run dev
```

- [ ] **Step 2: Run the full UAT checklist**

Walk through every step of spec §7 in order. Check each item:

- [ ] 1. Open `/budgets` as a user with no savings target → gear button shows the blue dot
- [ ] 2. Click gear → modal opens, `Meta de ahorro` row auto-expands (first-open nudge)
- [ ] 3. Enter 300000, click Guardar → "Guardado ✓" chip appears, row collapses after ~900ms, Sankey behind the modal updates
- [ ] 4. Blue dot on gear disappears
- [ ] 5. Expand Aporte al hogar, switch to "Fija", enter 800000, Guardar → verify the hogar Sankey renders the member as "Contribución fija" in the personal view
- [ ] 6. Expand Topes por categoría with zero existing caps → only `+ Agregar tope` button visible
- [ ] 7. Click `+ Agregar tope` → picker opens with top 5 suggested categories + badges
- [ ] 8. Click Supermercado → new cap row appears pre-focused, popover closes
- [ ] 9. Enter 250000, click Guardar topes → Sankey `spent_supermercado` link updates
- [ ] 10. Click × on an existing cap → row disappears, click Guardar topes → cap is gone
- [ ] 11. Mobile viewport (375×812 Chrome device mode): modal becomes bottom sheet, same content
- [ ] 12. `/settings` has no budget-related sections
- [ ] 13. Keyboard: Tab through modal, Esc closes, Enter on an accordion button toggles it

For any step that fails, diagnose and fix inline (file edits, not a new task). Re-run the affected step. Commit fixes individually.

- [ ] **Step 3: Final type-check and backend test sweep**

```bash
cd frontend && npm run build
cd ../backend && pytest -v
```

Expected:
- Frontend build: zero errors
- Backend tests: all ~401 pass (the existing number) plus the new `test_get_me_includes_contribution_fields_for_household_member`

- [ ] **Step 4: Commit any UAT fixes**

If UAT surfaced any fixes, commit them with messages like:

```bash
git commit -m "fix(budget-config): <specific issue>"
```

- [ ] **Step 5: Update the state docs**

Use the `luka-update-state-docs` skill (or invoke `update-project-docs` manually) to update `README.md`, `ARCHITECTURE.md`, and `NEXT-STEPS.md` to reflect:

- `/budgets` has a new "Configurar presupuesto" modal that consolidates all budget config
- `/settings` no longer contains budget-related sections
- `/auth/me` now returns contribution fields
- The "Budget v3 follow-ups" list in `NEXT-STEPS.md` should have the scan-fatigue cap-editor item marked as resolved

- [ ] **Step 6: Commit doc updates**

```bash
git add README.md ARCHITECTURE.md NEXT-STEPS.md
git commit -m "docs: refresh state docs after budget config modal ship

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Push**

```bash
git push
```

Ship complete.

---

## Self-review checklist

**Spec coverage (against spec §2 in-scope list):**

| Spec requirement | Task |
|------------------|------|
| `BudgetConfigModal` component on `/budgets` | Task 5 |
| Gear-button entry point next to `CurrencyToggle` | Task 6 |
| Accordion with 5 rows across 3 groups | Tasks 4, 5, 7–13 |
| Inline per-section save | Tasks 7–13 (each row owns its mutation) |
| `CategoryCapsEditor` + picker + top-5 suggestions | Tasks 11–13 |
| Mobile bottom-sheet | Task 5 (responsive classes in shell) |
| Removal of old settings sections | Task 14 |
| Blue-dot empty-state nudge | Task 6 |
| Auto-expand Meta de ahorro when `needsSetup` | Task 5 |
| 900ms auto-collapse after save + cancel on switch/close | Task 4 |
| Last-saved `topes` summary, not draft | Task 13 (wrapper reads `budgets.data` not `draft`) |
| Derive per-category spend from existing `budget-v2` query | Task 12 |
| a11y: Radix Dialog, aria-expanded on rows, Esc, focus trap | Tasks 4, 5 |

**Pre-existing TODO resolved:** Task 1 extends `/auth/me` with contribution fields, closing the `ContributionSection` TODO from the v2 sprint.

**Spec gaps I intentionally did not implement:** picker arrow-key navigation (spec §3.5 and §6 mark it as v1-deferred follow-up).

**Scope adjustment flagged in the plan header:** the backend change in Task 1. Everything else is frontend-only.
