"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";
import { useLukaStore } from "@/app/lib/store";

const TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes (untrusted device)
const TRUSTED_TIMEOUT_MS = 7 * 24 * 60 * 60 * 1000; // 7 days (trusted device)
const WARNING_MS = 60 * 1000; // "¿Sigues ahí?" window before signout
const LAST_ACTIVE_KEY = "luka_last_active";
const FRESH_LOGIN_COOKIE = "luka-fresh-login";
const PWA_SESSION_KEY = "luka_pwa_session";
const TRUSTED_KEY = "luka_trusted_device"; // stores expiry epoch ms

function isFreshLogin(): boolean {
  return document.cookie.split("; ").some((c) => c.startsWith(`${FRESH_LOGIN_COOKIE}=`));
}

function clearFreshLoginCookie(): void {
  document.cookie = `${FRESH_LOGIN_COOKIE}=; max-age=0; path=/`;
}

function isPWA(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches;
}

function isTrustedDevice(): boolean {
  const raw = localStorage.getItem(TRUSTED_KEY);
  if (!raw) return false;
  const expires = Number(raw);
  if (!Number.isFinite(expires) || Date.now() > expires) {
    localStorage.removeItem(TRUSTED_KEY);
    return false;
  }
  return true;
}

function timeoutMs(): number {
  return isTrustedDevice() ? TRUSTED_TIMEOUT_MS : TIMEOUT_MS;
}

export function SessionGuard() {
  const router = useRouter();
  const reset = useLukaStore((s) => s.reset);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastWriteRef = useRef(0);
  const signingOutRef = useRef(false);
  const [showWarning, setShowWarning] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [countdown, setCountdown] = useState(60);
  const showWarningRef = useRef(false);
  showWarningRef.current = showWarning;

  const signOut = useCallback(async () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    setShowWarning(false);
    localStorage.removeItem(LAST_ACTIVE_KEY);
    localStorage.removeItem(PWA_SESSION_KEY);
    await createClient().auth.signOut();
    reset();
    router.push("/login");
  }, [reset, router]);

  useEffect(() => {
    const supabase = createClient();

    // In PWA mode, persist session to localStorage as backup
    // (iOS may not reliably persist cookies across PWA termination/relaunch)
    const saveSessionForPWA = async () => {
      if (!isPWA()) return;
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session?.refresh_token) {
        localStorage.setItem(
          PWA_SESSION_KEY,
          JSON.stringify({
            access_token: session.access_token,
            refresh_token: session.refresh_token,
          }),
        );
      }
    };

    // Handle fresh login: clear stale timestamp, write fresh one
    if (isFreshLogin()) {
      localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
      clearFreshLoginCookie();
      saveSessionForPWA();
    }

    // --- PWA mode: persistent session, just refresh tokens on resume ---
    if (isPWA()) {
      // Always save session on mount — not just on fresh login
      saveSessionForPWA();

      const onVisibilityChange = async () => {
        if (document.visibilityState === "visible" && !signingOutRef.current) {
          // getUser() hits Supabase auth server, triggering token auto-refresh.
          // getSession() only reads cached/local state and would NOT refresh expired JWTs.
          const {
            data: { user },
            error,
          } = await supabase.auth.getUser();
          if (error || !user) {
            signingOutRef.current = true;
            await signOut();
          } else {
            // Session is valid — update localStorage backup with fresh tokens
            saveSessionForPWA();
          }
        }
      };
      document.addEventListener("visibilitychange", onVisibilityChange);
      return () => {
        document.removeEventListener("visibilitychange", onVisibilityChange);
      };
    }

    // --- Browser mode: inactivity timeout with a warning window ---
    const armTimers = (remaining: number) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      const warnIn = Math.max(0, remaining - WARNING_MS);
      warningTimerRef.current = setTimeout(() => {
        setCountdown(Math.ceil(Math.min(WARNING_MS, remaining) / 1000));
        setShowWarning(true);
      }, warnIn);
      timerRef.current = setTimeout(() => {
        signingOutRef.current = true;
        signOut();
      }, remaining);
    };

    const resetTimer = () => {
      // While the warning modal is up, only its buttons decide the outcome —
      // a stray mousemove must not silently dismiss the security prompt.
      if (showWarningRef.current) return;
      const now = Date.now();
      if (now - lastWriteRef.current > 1000) {
        lastWriteRef.current = now;
        localStorage.setItem(LAST_ACTIVE_KEY, String(now));
      }
      armTimers(timeoutMs());
    };

    // On mount: check if already timed out
    const stored = localStorage.getItem(LAST_ACTIVE_KEY);
    const lastActive = stored ? Number(stored) : Date.now();
    if (Date.now() - lastActive > timeoutMs()) {
      signOut();
      return;
    }

    // Resume timers for remaining time
    localStorage.setItem(LAST_ACTIVE_KEY, String(lastActive));
    armTimers(timeoutMs() - (Date.now() - lastActive));

    // Track user activity
    const events = ["mousemove", "keydown", "click", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, resetTimer, { passive: true }));

    // Check on tab re-focus
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        const lastStored = localStorage.getItem(LAST_ACTIVE_KEY);
        const last = lastStored ? Number(lastStored) : Date.now();
        if (Date.now() - last > timeoutMs()) {
          signOut();
        } else {
          resetTimer();
        }
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      events.forEach((e) => window.removeEventListener(e, resetTimer));
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [router, reset, signOut]);

  // Countdown ticker while the warning modal is visible.
  useEffect(() => {
    if (!showWarning) return;
    const interval = setInterval(() => {
      setCountdown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [showWarning]);

  const stayLoggedIn = () => {
    if (rememberDevice) {
      localStorage.setItem(TRUSTED_KEY, String(Date.now() + TRUSTED_TIMEOUT_MS));
    }
    setShowWarning(false);
    localStorage.setItem(LAST_ACTIVE_KEY, String(Date.now()));
    // Re-arm via the existing listeners — one code path for activity resets.
    window.dispatchEvent(new Event("click"));
  };

  if (!showWarning) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 px-4"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="session-warning-title"
    >
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="session-warning-title" className="text-base font-semibold text-luka-dark">
          ¿Sigues ahí?
        </h2>
        <p className="mt-1.5 text-sm text-slate-600">
          Por seguridad cerraremos tu sesión en{" "}
          <span className="font-semibold tabular-nums">{countdown}s</span>.
        </p>
        <label className="mt-4 flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={rememberDevice}
            onChange={(e) => setRememberDevice(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-luka-primary focus:ring-luka-primary/30"
          />
          Recordar este dispositivo por 7 días
        </label>
        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={() => {
              signingOutRef.current = true;
              signOut();
            }}
            className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Cerrar sesión
          </button>
          <button
            type="button"
            onClick={stayLoggedIn}
            className="flex-1 rounded-lg bg-luka-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Seguir conectado
          </button>
        </div>
      </div>
    </div>
  );
}
