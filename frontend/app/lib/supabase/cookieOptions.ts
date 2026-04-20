import type { CookieOptions } from "@supabase/ssr";

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

export function withDurableCookie(options: CookieOptions = {}): CookieOptions {
  if (options.maxAge !== undefined || options.expires !== undefined) {
    return options;
  }
  return { ...options, maxAge: ONE_YEAR_SECONDS };
}
