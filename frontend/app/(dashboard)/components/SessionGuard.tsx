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
