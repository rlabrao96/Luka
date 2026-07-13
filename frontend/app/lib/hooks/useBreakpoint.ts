"use client";
import { useEffect, useState } from "react";

const BP = {
  sm: "(max-width: 639px)",
  md: "(max-width: 767px)",
  lg: "(max-width: 1023px)",
} as const;

type BreakpointKey = keyof typeof BP;

/** Returns true when the viewport matches `max-width` at the given Tailwind
 *  breakpoint. Single source of truth so the same "is this mobile?" check
 *  doesn't drift between components.
 *
 *  - "sm": narrow phones (≤639px)
 *  - "md": larger phones + small tablets (≤767px)
 *  - "lg": phones + tablets (≤1023px) — matches the dashboard layout's
 *    `lg:pb-0` / Sidebar `hidden lg:flex` switch. */
export function useBreakpoint(bp: BreakpointKey): boolean {
  // Lazy-init from the real media query so the first paint already reflects the
  // viewport (no desktop→mobile flash). Guarded for SSR where `window` is absent.
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(BP[bp]).matches : false
  );
  useEffect(() => {
    const mq = window.matchMedia(BP[bp]);
    setMatches(mq.matches);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [bp]);
  return matches;
}
