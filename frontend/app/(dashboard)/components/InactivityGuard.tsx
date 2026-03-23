"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";
import { useLukaStore } from "@/app/lib/store";

const TIMEOUT_MS = 60 * 60 * 1000; // 1 hour
const LAST_ACTIVE_KEY = "luka_last_active";

export function InactivityGuard() {
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

    const resetTimer = () => {
      // Throttle localStorage writes to once per second — mousemove fires 100+ times/sec
      const now = Date.now();
      if (now - lastWriteRef.current > 1000) {
        lastWriteRef.current = now;
        localStorage.setItem(LAST_ACTIVE_KEY, String(now));
      }
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(signOut, TIMEOUT_MS);
    };

    // On mount: check if already timed out (e.g. closed browser and came back)
    const lastActive = Number(localStorage.getItem(LAST_ACTIVE_KEY) ?? Date.now());
    if (Date.now() - lastActive > TIMEOUT_MS) {
      signOut();
      return;
    }

    // Resume timer for remaining time
    const remaining = TIMEOUT_MS - (Date.now() - lastActive);
    localStorage.setItem(LAST_ACTIVE_KEY, String(lastActive)); // preserve original
    timerRef.current = setTimeout(signOut, remaining);

    // Track user activity
    const events = ["mousemove", "keydown", "click", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, resetTimer, { passive: true }));

    // Check on tab re-focus — catches long-idle users returning from another tab
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
