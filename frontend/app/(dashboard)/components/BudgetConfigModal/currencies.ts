// LATAM currency set supported by Luka. Matches the backend regex in
// `user_budget_settings_router` / `cuota_schemas` / `SetCategoryBudgetRequest`.
// Never hardcode a country-specific default in a component — fall back to the
// caller's `preferred_currency` from `/auth/me`, and finally to `CLP` only if
// that's missing.

export const CURRENCY_OPTIONS = ["CLP", "USD", "COP", "MXN", "PEN", "BRL"] as const;

export type CurrencyCode = (typeof CURRENCY_OPTIONS)[number];

export function isSupportedCurrency(code: string | null | undefined): code is CurrencyCode {
  return !!code && (CURRENCY_OPTIONS as readonly string[]).includes(code);
}
