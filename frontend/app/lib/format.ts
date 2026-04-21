import { formatStoredAmount } from "@/app/lib/currency";

/** ISO 4217 currency code (e.g. "CLP", "USD", "BRL"). */
export type Currency = string;

/** Format a stored monetary amount using the LATAM-aware helper.
 *  Zero-decimal currencies (CLP, COP, PYG, CRC) are treated as major units;
 *  all others are divided by 100 before formatting. */
export function formatMoney(amount: number, currency: Currency): string {
  return formatStoredAmount(amount, currency);
}
