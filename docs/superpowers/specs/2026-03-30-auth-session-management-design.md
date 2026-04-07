# Auth Session Management: Double-Login Fix + PWA Persistent Sessions

**Date:** 2026-03-30
**Status:** Approved
**Scope:** 3 files, frontend only, no backend changes

## Problem

Two issues with the current auth/session flow:

1. **Double-login bug**: After Google OAuth, user sees the dashboard briefly, then gets redirected back to `/login`. Second login works. Root cause: `InactivityGuard` checks `luka_last_active` in localStorage on mount. If stale from a previous session (>timeout), it immediately calls `signOut()` — even on a fresh login.

2. **PWA session persistence**: Mobile users who save Luka to their homescreen (PWA) should stay logged in indefinitely, like a native banking app. Currently all users get the same 1-hour inactivity timeout.

## Design

### 1. Fix Double-Login Bug

**Mechanism:** Cookie-based fresh-login flag.

- In `auth/callback/route.ts`, after successful `exchangeCodeForSession`, set a cookie: `luka-fresh-login=1` (max-age=60, path=/, SameSite=Lax, httpOnly=false, secure=true). Must be `httpOnly=false` so `SessionGuard` can read it client-side.
- In `SessionGuard` (renamed from `InactivityGuard`), on mount: check for the `luka-fresh-login` cookie. If present:
  - Clear stale `luka_last_active` from localStorage
  - Write fresh `Date.now()` timestamp
  - Delete the cookie

**Why a cookie?** The callback is a server-side route handler (no localStorage access). The cookie bridges server → client.

**Edge cases:**
- Explicit sign-out ("Cerrar sesión") already clears `luka_last_active` — no issue on immediate re-login.
- The bug only triggers when session expires without going through the sign-out flow (token expiry, cookie clearing, refresh token revocation). The fresh-login cookie covers all these cases.

### 2. PWA Detection & Conditional Timeout

**Detection:** `window.matchMedia('(display-mode: standalone)').matches`
- `true` → PWA (homescreen app)
- `false` → any browser (desktop or mobile)

**Behavior:**
- **PWA mode:** Skip inactivity timer entirely. No timeout, no activity tracking event listeners.
- **Browser mode:** 30-minute inactivity timeout (changed from 60 minutes). Same activity-tracking logic as current implementation.

### 3. Token Refresh on PWA Resume

**Problem:** PWA sessions live indefinitely, but Supabase JWTs expire (~1 hour). User opens PWA after hours/days → expired JWT → broken dashboard.

**Fix:** In PWA mode, `SessionGuard` registers a `visibilitychange` listener:
- On `visible`: call `supabase.auth.getSession()` to trigger Supabase's built-in token auto-refresh.
- If refresh fails (refresh token revoked/expired): gracefully sign out and redirect to `/login`.

### 4. Component Rename

`InactivityGuard.tsx` → `SessionGuard.tsx` — reflects its expanded responsibility (inactivity timeout for browser + token refresh for PWA).

## Files Changed

| File | Change |
|---|---|
| `frontend/app/auth/callback/route.ts` | Set `luka-fresh-login` cookie after successful session exchange |
| `frontend/app/(dashboard)/components/InactivityGuard.tsx` → `SessionGuard.tsx` | Rename. Read & clear fresh-login flag on mount. PWA detection. PWA branch: visibilitychange token refresh, no timer. Browser branch: 30min timeout. |
| `frontend/app/(dashboard)/layout.tsx` | Update import: `InactivityGuard` → `SessionGuard` |

## Session Behavior Matrix

| Context | Timeout | Logout trigger |
|---|---|---|
| Desktop browser | 30 min inactivity | Auto (timer) or explicit |
| Mobile browser (Safari/Chrome) | 30 min inactivity | Auto (timer) or explicit |
| PWA (homescreen) | None | Explicit only |

## Non-Goals

- No backend changes
- No new dependencies
- No auth provider refactor
- No server-side session tracking
- No role-based access control
