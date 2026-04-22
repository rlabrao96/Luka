// frontend/app/lib/locale.ts
//
// LATAM-first locale resolution. CLAUDE.md forbids hardcoding "es-CL".
// Two entry points:
//   - localeForCurrency(code)   → pick a locale from the currency the user is
//     viewing (BRL→pt-BR, USD→en-US, MXN→es-MX, ...).
//   - resolveAppLocale()         → fall back to the browser/OS locale, safe
//     on the server where Intl can't read a navigator.
//
// Prefer localeForCurrency when the rendered value is tied to a currency;
// prefer resolveAppLocale for currency-agnostic dates (recent-tx headers,
// greeting-line month names, etc).

const CURRENCY_LOCALE: Record<string, string> = {
  CLP: "es-CL",
  USD: "en-US",
  BRL: "pt-BR",
  MXN: "es-MX",
  COP: "es-CO",
  PEN: "es-PE",
  ARS: "es-AR",
  UYU: "es-UY",
  PYG: "es-PY",
  BOB: "es-BO",
  VES: "es-VE",
  DOP: "es-DO",
  GTQ: "es-GT",
  HNL: "es-HN",
  NIO: "es-NI",
  CRC: "es-CR",
};

export function localeForCurrency(currency?: string | null): string {
  if (!currency) return resolveAppLocale();
  return CURRENCY_LOCALE[currency.toUpperCase()] ?? resolveAppLocale();
}

export function resolveAppLocale(): string {
  if (typeof Intl === "undefined") return "es-CL";
  try {
    return Intl.DateTimeFormat().resolvedOptions().locale || "es-CL";
  } catch {
    return "es-CL";
  }
}
