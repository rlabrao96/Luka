# Day 6 — UX / Design Consistency Review

**Sprint:** Budget page redesign (`budget-v2`)
**Date:** 2026-04-14
**Method:** Code-level style audit (browser-based Lighthouse/a11y pass
blocked by the Google OAuth automation policy that Task I already
documented; substituted with a structural comparison against the
canonical dashboard + settings style references.)

## Canonical patterns established from the reference set

(Grepped from `frontend/app/(dashboard)/page.tsx`, `transactions/page.tsx`,
`household/page.tsx`, `subscriptions/page.tsx`, `settings/page.tsx`, and
the existing settings sections.)

| Token | Canonical value |
|---|---|
| Page outer spacing | `space-y-5` or `space-y-6` (both acceptable; no single canonical) |
| Page title | `text-2xl font-bold tracking-tight` + `text-luka-dark` (most common) or `text-gray-900` (subscriptions) |
| Content card | `rounded-xl border border-slate-100 bg-white p-5 shadow-[var(--shadow-card)]` |
| Compact KPI card | `... p-4` with `text-2xl font-bold` headline value |
| Settings card | `... p-5 shadow-[0_1px_3px_rgba(0,0,0,0.03)]` |
| Settings card heading | `text-sm font-semibold text-slate-500 uppercase tracking-wider` |
| Section sub-label | `text-xs font-semibold uppercase tracking-wide text-slate-400` |
| Settings input | `rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500` |
| Primary button | `rounded-xl bg-luka-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60` |
| Icon size | `size={16}` (most common) |

## Drift inventory — **14 items found, 0 blocking**

| # | File | Item | Severity | Action |
|---|---|---|---|---|
| 1 | `components/RunwayCard.tsx:14` | Headline value `text-lg` (too small for a KPI card) | Important | **Fixed** → `text-2xl mt-1` |
| 2 | `components/RunwayCard.tsx:10` | Card padding `p-4` inconsistent with settings KPI cards | Important | **Fixed** → `p-5` |
| 3 | `budgets/page.tsx` (x2) | `text-[11px]` on Hogar / Personal section labels instead of canonical `text-xs` | Important | **Fixed** → `text-xs` |
| 4 | `components/MarkAsCuotaDialog.tsx:99,111` | Inputs use `rounded-lg py-2` + `focus:ring-luka-primary/20` instead of canonical settings-input style | Important | **Fixed** → `rounded-xl py-2.5 focus:ring-blue-500/20 focus:border-blue-500` |
| 5 | `components/MarkAsCuotaDialog.tsx:163,171` | Footer buttons `rounded-lg` instead of canonical `rounded-xl` | Important | **Fixed** → `rounded-xl` |
| 6 | `budgets/page.tsx` (x2) | Sankey wrapper card `p-4` vs canonical content card `p-5` | Minor | **Fixed** → `p-5` |
| 7 | `budgets/page.tsx` | Personal-equals-Hogar note uses `italic text-slate-400` (italic unusual in the codebase) | Minor | **Fixed** → drop italic, bump to `text-slate-500` |
| 8 | `settings/components/ContributionSection.tsx:141` | `disabled:opacity-50` inconsistent with siblings | Minor | **Fixed** → `disabled:opacity-60` |
| 9 | `budgets/page.tsx:115-117` | Title uses `text-gray-900`/`text-gray-400` (subscriptions style) instead of `text-luka-dark`/`text-luka-muted` | Minor | **Deferred** — both styles already exist in the codebase; not drift, just variation |
| 10 | `components/RiskAlertBand.tsx:23` | Literal `⚠️` emoji where other warning surfaces use `<AlertTriangle>` from Lucide | Minor | **Deferred** — aria-hidden'd, accessibility is fine, a future polish pass can swap |
| 11 | `components/BudgetSankey.tsx:14-22` | Hardcoded hex colors (`#2563EB`, etc.) duplicating the `luka-*` CSS tokens | Minor | **Deferred** — SVG `fill` values can't use Tailwind classes directly; values match tokens exactly, semantically correct |
| 12 | `components/BudgetSankey.tsx` empty state | Dashed border one-off (other empty states use `rounded-full bg-slate-100` with an icon) | Minor | **Deferred** — acceptable for a chart-area empty state |
| 13 | `components/RunwayCard.tsx` | Missing explicit `bg-white` in the base class string (provided via the template literal) | Minor | **Deferred** — functions correctly |
| 14 | `settings/components/ContributionSection.tsx:83-87` | Active radio state uses `border-blue-500 bg-blue-50/40` instead of `border-luka-primary bg-luka-primary/10` | Minor | **Deferred** — blue-500 equals luka-primary at runtime |

## Applied fixes

### frontend/app/(dashboard)/components/RunwayCard.tsx
- `p-4` → `p-5` (padding parity with other dashboard cards)
- headline value `text-lg` → `text-2xl mt-1` (KPI hierarchy parity with `KpiCard` and `BalanceCard`)

### frontend/app/(dashboard)/components/MarkAsCuotaDialog.tsx
- Installments input: `rounded-lg py-2 focus:ring-luka-primary/20` → `rounded-xl py-2.5 focus:ring-blue-500/20 focus:border-blue-500`
- First-date input: same as above
- Cancel + Confirm footer buttons: `rounded-lg` → `rounded-xl`

### frontend/app/(dashboard)/budgets/page.tsx
- Hogar + Personal section labels: `text-[11px]` → `text-xs`
- Sankey wrapper cards (both sections): `p-4` → `p-5`
- Personal-equals-Hogar note: removed `italic`, bumped color from `text-slate-400` to `text-slate-500`

### frontend/app/(dashboard)/settings/components/ContributionSection.tsx
- Save button: `disabled:opacity-50` → `disabled:opacity-60` (matches `BudgetSettingsSection` and `CategoryBudgetsSection` siblings)

## Verification

- `npm run build` — clean, 21 routes, 0 TypeScript errors
- Backend tests unaffected (no backend changes in this pass)

## Items deliberately deferred

The 6 deferred minors are all judgment calls that either:
- Have multiple coexisting styles already in the codebase (items 9, 10, 14)
- Are technically correct and semantically equivalent (items 11, 13)
- Work as intended for a one-off context (item 12)

None of them affect correctness, accessibility, or the overall visual
coherence of the page. Batching them into a follow-up polish pass is
acceptable.

## Verdict

**APPROVED for Day 7 ship.** The budget-v2 redesign visually matches
the rest of the Luka dashboard. All 4 important items flagged by the
code-level audit are fixed; the 6 deferred minors are documented and
non-blocking.
