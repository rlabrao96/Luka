export type Currency = "CLP" | "USD";

/** Format a monetary amount in the given currency using Intl.NumberFormat.
 *  - CLP: stored as integers, no fractional digits, es-CL locale (e.g. "$1.234.567").
 *  - USD: stored as CENTS across Luka (email parser, manual, plaid sync).
 *    We divide by 100 at the display layer, then format with two
 *    fractional digits en-US (e.g. 195018 → "$1,950.18").
 *    Matches the convention used by TransactionCard, RecentTransactions,
 *    BalanceCard, and the dashboard page. */
export function formatMoney(amount: number, currency: Currency): string {
  if (currency === "CLP") {
    return new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    }).format(Math.round(amount));
  }
  const dollars = amount / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(dollars);
}
