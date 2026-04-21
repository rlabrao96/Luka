// Re-exports derived from the single source of truth in `lib/currency.ts`.
// Do not add codes here — edit `SUPPORTED_CURRENCIES` instead.
import { SUPPORTED_CURRENCIES } from "@/app/lib/currency";

export const CURRENCY_OPTIONS: readonly string[] = SUPPORTED_CURRENCIES.map((c) => c.code);

export type CurrencyCode = string;

export function isSupportedCurrency(code: string | null | undefined): code is CurrencyCode {
  return !!code && CURRENCY_OPTIONS.includes(code);
}
