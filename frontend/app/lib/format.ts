export type Currency = "CLP" | "USD";

/** Format a monetary amount in the given currency using Intl.NumberFormat.
 *  - CLP: no fractional digits, es-CL locale (e.g. "$1.234.567").
 *  - USD: two fractional digits, en-US locale (e.g. "$1,234.56"). */
export function formatMoney(amount: number, currency: Currency): string {
  if (currency === "CLP") {
    return new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    }).format(Math.round(amount));
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}
