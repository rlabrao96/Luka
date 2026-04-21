// frontend/app/lib/currency.ts

export interface SupportedCurrency {
  code: string;
  name: string;
  symbol: string;
}

export const SUPPORTED_CURRENCIES: SupportedCurrency[] = [
  { code: "CLP", name: "Peso chileno",          symbol: "CLP$" },
  { code: "USD", name: "Dólar estadounidense",   symbol: "US$"  },
  { code: "COP", name: "Peso colombiano",        symbol: "COP$" },
  { code: "BRL", name: "Real brasileño",         symbol: "R$"   },
  { code: "MXN", name: "Peso mexicano",          symbol: "MX$"  },
  { code: "ARS", name: "Peso argentino",         symbol: "AR$"  },
  { code: "PEN", name: "Sol peruano",            symbol: "S/"   },
  { code: "UYU", name: "Peso uruguayo",          symbol: "$U"   },
  { code: "PYG", name: "Guaraní paraguayo",      symbol: "₲"    },
  { code: "BOB", name: "Boliviano",              symbol: "Bs."  },
  { code: "VES", name: "Bolívar venezolano",     symbol: "Bs.S" },
  { code: "DOP", name: "Peso dominicano",        symbol: "RD$"  },
  { code: "GTQ", name: "Quetzal guatemalteco",   symbol: "Q"    },
  { code: "HNL", name: "Lempira hondureño",      symbol: "L"    },
  { code: "NIO", name: "Córdoba nicaragüense",   symbol: "C$"   },
  { code: "CRC", name: "Colón costarricense",    symbol: "₡"    },
];

// (symbol, decimals, thousands_sep, decimal_sep)
const FORMAT_MAP: Record<string, [string, number, string, string]> = {
  CLP: ["CLP$", 0, ".", ""],
  COP: ["COP$", 0, ".", ""],
  PYG: ["₲",    0, ".", ""],
  CRC: ["₡",    0, ".", ""],
  USD: ["US$",  2, ",", "."],
  MXN: ["MX$",  2, ",", "."],
  PEN: ["S/",   2, ",", "."],
  BOB: ["Bs.",  2, ",", "."],
  DOP: ["RD$",  2, ",", "."],
  GTQ: ["Q",    2, ",", "."],
  HNL: ["L",    2, ",", "."],
  NIO: ["C$",   2, ",", "."],
  BRL: ["R$",   2, ".", ","],
  ARS: ["AR$",  2, ".", ","],
  UYU: ["$U",   2, ".", ","],
  VES: ["Bs.S", 2, ".", ","],
};

/**
 * Format a transaction amount for display.
 * Amounts are stored as-is (CLP as integers, others as floats with 2 decimal places).
 * This is NOT for account balances (which may use different storage units).
 */
export function formatAmount(amount: number, currency: string): string {
  const fmt = FORMAT_MAP[currency];
  if (!fmt) return `${currency} ${Math.round(amount).toLocaleString()}`;

  const [symbol, decimals, thouSep, decSep] = fmt;

  if (decimals === 0) {
    const n = Math.round(amount);
    const parts = Math.abs(n).toString().split("");
    const withSeps: string[] = [];
    parts.reverse().forEach((d, i) => {
      if (i > 0 && i % 3 === 0) withSeps.push(thouSep);
      withSeps.push(d);
    });
    const formatted = withSeps.reverse().join("");
    return `${symbol}${formatted}`;
  }

  const intPart = Math.floor(Math.abs(amount));
  const frac = Math.round((Math.abs(amount) - intPart) * 100);
  const parts = intPart.toString().split("");
  const withSeps: string[] = [];
  parts.reverse().forEach((d, i) => {
    if (i > 0 && i % 3 === 0) withSeps.push(thouSep);
    withSeps.push(d);
  });
  const intFormatted = withSeps.reverse().join("");
  return `${symbol}${intFormatted}${decSep}${frac.toString().padStart(2, "0")}`;
}

/**
 * Currencies with no minor units — amounts are stored directly as integer
 * major units, not cents. Mirrors the backend's storage convention.
 */
export const ZERO_DECIMAL_CURRENCIES = new Set([
  "CLP", "COP", "PYG", "CRC", "JPY", "KRW", "VND", "HUF", "ISK", "TWD", "UGX", "RWF",
]);

export function isZeroDecimalCurrency(code: string): boolean {
  return ZERO_DECIMAL_CURRENCIES.has(code.toUpperCase());
}

export function isNegativeStored(amountCents: number): boolean {
  return amountCents < 0;
}

/**
 * Format a stored amount (as persisted in the DB) to a localized currency
 * string. Returns the absolute value — callers wrap the sign/parentheses
 * themselves via `isNegativeStored`.
 *
 *  - For zero-decimal currencies (CLP, COP, PYG, ...), the stored value is
 *    already in major units.
 *  - For all other currencies, the stored value is in minor units (cents)
 *    and is divided by 100 before formatting.
 */
/** Valid ISO 4217 code guard. Intl.NumberFormat throws RangeError on empty
 *  or non-3-letter codes, which kills the page during the brief window
 *  before user preferences resolve. */
function isValidCurrencyCode(code: string | undefined | null): code is string {
  return typeof code === "string" && /^[A-Za-z]{3}$/.test(code);
}

export function formatStoredAmount(
  amountCents: number,
  currency: string,
  locale?: string,
): string {
  if (!isValidCurrencyCode(currency)) return "—";
  const decimals = isZeroDecimalCurrency(currency) ? 0 : 2;
  const value = decimals === 0 ? amountCents : amountCents / 100;
  const resolvedLocale =
    locale ?? Intl.DateTimeFormat().resolvedOptions().locale ?? "es-CL";
  return new Intl.NumberFormat(resolvedLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(value));
}

/** Format an amount already in major units (e.g. after /100 normalization).
 *  Unlike formatStoredAmount, no division is applied. */
export function formatMajorAmount(
  amount: number,
  currency: string,
  locale?: string,
): string {
  if (!isValidCurrencyCode(currency)) return "—";
  const decimals = isZeroDecimalCurrency(currency) ? 0 : 2;
  const resolvedLocale =
    locale ?? Intl.DateTimeFormat().resolvedOptions().locale ?? "es-CL";
  return new Intl.NumberFormat(resolvedLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(Math.abs(amount));
}

/** Compact formatter for large major-unit amounts (k/M abbreviations). */
export function formatMajorAmountCompact(
  amount: number,
  currency: string,
): string {
  if (!isValidCurrencyCode(currency)) return "—";
  const abs = Math.abs(amount);
  const symbol = FORMAT_MAP[currency]?.[0] ?? currency + " ";
  if (abs >= 1_000_000) return `${symbol}${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${symbol}${Math.round(abs / 1_000)}k`;
  return formatMajorAmount(amount, currency);
}
