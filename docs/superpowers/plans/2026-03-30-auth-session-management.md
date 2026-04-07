# Auth Session Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the double-login bug and add PWA-aware session management (persistent for PWA, 30min timeout for browser).

**Architecture:** Cookie-based fresh-login flag bridges server callback → client SessionGuard. PWA detected via `display-mode: standalone` media query. SessionGuard handles both modes: browser (inactivity timeout) and PWA (token refresh on resume).

**Tech Stack:** Next.js 14 App Router, Supabase SSR, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-30-auth-session-management-design.md`

---

### Task 1: Set fresh-login cookie in auth callback

**Files:**
- Modify: `frontend/app/auth/callback/route.ts:63`

- [ ] **Step 1: Add fresh-login cookie before the final redirect**

In `frontend/app/auth/callback/route.ts`, replace the final redirect (line 63):

```typescript
// Before:
return NextResponse.redirect(`${origin}/`);

// After:
const response = NextResponse.redirect(`${origin}/`);
response.cookies.set("luka-fresh-login", "1", {
  maxAge: 60,
  path: "/",
  sameSite: "lax",
  httpOnly: false,
  secure: origin.startsWith("https"),
});
return response;
```

Also apply the same cookie to the onboarding redirect (line 56):

```typescript
// Before:
return NextResponse.redirect(`${origin}/onboarding/setup-household`);

// After:
const onboardingResponse = NextResponse.redirect(`${origin}/onboarding/setup-household`);
onboardingResponse.cookies.set("luka-fresh-login", "1", {
  maxAge: 60,
  path: "/",
  sameSite: "lax",
  httpOnly: false,
  secure: origin.startsWith("https"),
});
return onboardingResponse;
```

- [ ] **Step 2: Verify the callback builds**

Run: `cd frontend && npx next build --no-lint 2>&1 | head -30`
Expected: No TypeScript errors in `app/auth/callback/route.ts`

- [ ] **Step 3: Commit**

```bash
git add frontend/app/auth/callback/route.ts
git commit -m "fix: set fresh-login cookie in auth callback to prevent double-login"
```

---

### Task 2: Rename InactivityGuard → SessionGuard and fix double-login bug

**Files:**
- Delete: `frontend/app/(dashboard)/components/InactivityGuard.tsx`
- Create: `frontend/app/(dashboard)/components/SessionGuard.tsx`
- Modify: `frontend/app/(dashboard)/layout.tsx:4,45`

- [ ] **Step 1: Create SessionGuard.tsx with fresh-login cookie handling**

Create `frontend/app/(dashboard)/components/SessionGuard.tsx`:

```typescript
"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";
import { useLukaStore } from "@/app/lib/store";

const TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes
const LAST_ACTIVE_KEY = "luka_last_active";
const FRESH_LOGIN_COOKIE = "luka-fresh-login";

function isFreshLogin(): boolean {
  return document.cookie.split("; ").some((c) => c.startsWith(`${FRESH_LOGIN_COOKIE}=`));
}

function clearFreshLoginCookie(): void {
  document.cookie = `${FRESH_LOGIN_COOKIE}=; max-age=0; path=/`;
}

function isPWA(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches;
}

export function SessionGuard() {
  const router = useRouter();
  const reset = useLukaStore((s) => s.reset);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastWriteRef = useRef(0);

  useEffect(() => {
    const supabase = createClient();

    const signOut = async () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      localStorage.removeItem(LAST_ACTIVE_KEY);
      await supabase.auth.signOut();
      reset();
      router.push("/login");
    };

    // Handle fresh login: clear stale timestamp, write fresh one
    if (isFreshLogin()) {
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
      clearFreshLoginCookie();
    }

    // --- PWA mode: persistent session, just refresh tokens on resume ---
    if (isPWA()) {
      let signingOut = false;
      const onVisibilityChange = async () => {
        if (document.visibilityState === "visible" && !signingOut) {
          // getUser() hits Supabase auth server, triggering token auto-refresh.
          // getSession() only reads cached/local state and would NOT refresh expired JWTs.
          const { data: { user }, error } = await supabase.auth.getUser();
          if (error || !user) {
            signingOut = true;
            await signOut();
          }
        }
      };
      document.addEventListener("visibilitychange", onVisibilityChange);
      return () => {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      };
    }

    // --- Browser mode: 30-minute inactivity timeout ---
    const resetTimer = () => {
      const now = Date.now();
      if (now - lastWriteRef.current > 1000) {
        lastWriteRef.current = now;
        localStorage.setItem(LAST_ACTIVE_KEY, String(now));
      }
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(signOut, TIMEOUT_MS);
    };

    // On mount: check if already timed out
    const lastActive = Number(localStorage.getItem(LAST_ACTIVE_KEY) ?? Date.now());
    if (Date.now() - lastActive > TIMEOUT_MS) {
      signOut();
      return;
    }

    // Resume timer for remaining time
    const remaining = TIMEOUT_MS - (Date.now() - lastActive);
    localStorage.setItem(LAST_ACTIVE_KEY, String(lastActive));
    timerRef.current = setTimeout(signOut, remaining);

    // Track user activity
    const events = ["mousemove", "keydown", "click", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, resetTimer, { passive: true }));

    // Check on tab re-focus
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        const last = Number(localStorage.getItem(LAST_ACTIVE_KEY) ?? Date.now());
        if (Date.now() - last > TIMEOUT_MS) {
          signOut();
        } else {
          resetTimer();
        }
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      events.forEach((e) => window.removeEventListener(e, resetTimer));
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [router, reset]);

  return null;
}
```

- [ ] **Step 2: Delete the old InactivityGuard.tsx**

```bash
rm frontend/app/\(dashboard\)/components/InactivityGuard.tsx
```

- [ ] **Step 3: Update dashboard layout import**

In `frontend/app/(dashboard)/layout.tsx`, change line 4:

```typescript
// Before:
import { InactivityGuard } from "./components/InactivityGuard";

// After:
import { SessionGuard } from "./components/SessionGuard";
```

And line 45:

```typescript
// Before:
<InactivityGuard />

// After:
<SessionGuard />
```

- [ ] **Step 4: Verify the build**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -20`
Expected: Build succeeds, no TypeScript errors, no missing import errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\(dashboard\)/components/SessionGuard.tsx frontend/app/\(dashboard\)/layout.tsx
git rm frontend/app/\(dashboard\)/components/InactivityGuard.tsx
git commit -m "feat: rename InactivityGuard → SessionGuard, fix double-login, add PWA persistence"
```

---

### Task 3: Manual verification

- [ ] **Step 1: Verify double-login fix (browser)**

1. Open browser DevTools → Application → Local Storage
2. Set `luka_last_active` to a timestamp from 2 hours ago (e.g., `Date.now() - 7200000`)
3. Clear all cookies
4. Go to `/login`, log in with Google
5. Expected: land on dashboard and STAY there (no redirect back to login)

- [ ] **Step 2: Verify browser timeout is 30 minutes**

1. Open DevTools → Console
2. After login, check localStorage for `luka_last_active` — should be recent timestamp
3. Confirm `TIMEOUT_MS` is 30 minutes (check source in DevTools)

- [ ] **Step 3: Verify PWA mode skips timeout**

1. Open DevTools → Console
2. Run: `window.matchMedia("(display-mode: standalone)").matches`
3. In browser, expected: `false` (timeout active)
4. If testing from homescreen PWA, expected: `true` (no timeout)

- [ ] **Step 4: Verify explicit logout still works**

1. Click "Cerrar sesión" in sidebar
2. Expected: redirected to `/login`, `luka_last_active` cleared from localStorage
3. Log in again immediately — should work without double-login
