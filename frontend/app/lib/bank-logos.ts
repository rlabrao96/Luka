/**
 * Central registry of official bank/institution app icons.
 *
 * Source: Apple App Store artwork (512×512 PNG) from the iTunes Search API.
 * Organized by country; each entry can carry multiple lookup keys so both a
 * Luka Connect `bank_code` and a Plaid `institution_name` resolve correctly.
 *
 * To add a new bank:
 *  1. Find the app on the App Store and grab its 512×512 artwork URL from
 *     https://itunes.apple.com/search?term=<app>&country=<cc>&entity=software
 *     (field `artworkUrl512`).
 *  2. Save the PNG into `frontend/public/bank-logos/<slug>.png`.
 *  3. Add one entry below keyed by the lowercase bank_code / institution_name.
 */

export interface BankLogoSpec {
  src: string;
  alt: string;
}

const icon = (slug: string, alt: string): BankLogoSpec => ({
  src: `/bank-logos/${slug}.png`,
  alt,
});

export const BANK_LOGOS: Record<string, BankLogoSpec> = {
  // ────────────── Chile ──────────────
  bchile: icon("bchile", "Banco de Chile"),
  falabella: icon("falabella", "Banco Falabella"),
  bestado: icon("bestado", "BancoEstado"),
  "santander-cl": icon("santander-cl", "Santander Chile"),
  "santander chile": icon("santander-cl", "Santander Chile"),
  bci: icon("bci", "BCI"),
  "scotiabank-cl": icon("scotiabank-cl", "Scotiabank Chile"),
  "scotiabank chile": icon("scotiabank-cl", "Scotiabank Chile"),
  "itau-cl": icon("itau-cl", "Itaú Chile"),
  "itau chile": icon("itau-cl", "Itaú Chile"),
  bice: icon("bice", "Banco BICE"),
  mach: icon("mach", "MACH"),

  // ────────────── Colombia ──────────────
  bancolombia: icon("bancolombia", "Bancolombia"),
  davivienda: icon("davivienda", "Davivienda"),
  "bbva-co": icon("bbva-co", "BBVA Colombia"),
  "bbva colombia": icon("bbva-co", "BBVA Colombia"),
  bogota: icon("bogota", "Banco de Bogotá"),
  "banco de bogota": icon("bogota", "Banco de Bogotá"),
  nequi: icon("nequi", "Nequi"),
  daviplata: icon("daviplata", "DaviPlata"),
  avvillas: icon("avvillas", "AV Villas"),
  "av villas": icon("avvillas", "AV Villas"),

  // ────────────── Brazil ──────────────
  nubank: icon("nubank", "Nubank"),
  "itau-br": icon("itau-br", "Itaú"),
  "itau unibanco": icon("itau-br", "Itaú Unibanco"),
  bradesco: icon("bradesco", "Bradesco"),
  bb: icon("bb", "Banco do Brasil"),
  "banco do brasil": icon("bb", "Banco do Brasil"),
  caixa: icon("caixa", "Caixa"),
  "santander-br": icon("santander-br", "Santander Brasil"),
  "santander brasil": icon("santander-br", "Santander Brasil"),
  inter: icon("inter", "Inter"),
  "banco inter": icon("inter", "Inter"),

  // ────────────── USA ──────────────
  venmo: icon("venmo", "Venmo"),
  "american express": icon("amex", "American Express"),
  "bank of america": icon("bankofamerica", "Bank of America"),
  chase: icon("chase", "Chase"),
  wellsfargo: icon("wellsfargo", "Wells Fargo"),
  "wells fargo": icon("wellsfargo", "Wells Fargo"),
  citi: icon("citi", "Citi"),
  citibank: icon("citi", "Citi"),
  usbank: icon("usbank", "U.S. Bank"),
  "u.s. bank": icon("usbank", "U.S. Bank"),
  "us bank": icon("usbank", "U.S. Bank"),
  capitalone: icon("capitalone", "Capital One"),
  "capital one": icon("capitalone", "Capital One"),
  paypal: icon("paypal", "PayPal"),
  discover: icon("discover", "Discover"),

  // ────────────── Mexico ──────────────
  "bbva-mx": icon("bbva-mx", "BBVA México"),
  "bbva mexico": icon("bbva-mx", "BBVA México"),
  banorte: icon("banorte", "Banorte"),
  "santander-mx": icon("santander-mx", "Santander México"),
  "santander mexico": icon("santander-mx", "Santander México"),
  banamex: icon("banamex", "Banamex"),
  citibanamex: icon("banamex", "Citibanamex"),
  "hsbc-mx": icon("hsbc-mx", "HSBC México"),
  "hsbc mexico": icon("hsbc-mx", "HSBC México"),
  azteca: icon("azteca", "Banco Azteca"),
  "banco azteca": icon("azteca", "Banco Azteca"),

  // ────────────── Peru ──────────────
  bcp: icon("bcp", "BCP"),
  "bbva-pe": icon("bbva-pe", "BBVA Perú"),
  "bbva peru": icon("bbva-pe", "BBVA Perú"),
  interbank: icon("interbank", "Interbank"),
  "scotiabank-pe": icon("scotiabank-pe", "Scotiabank Perú"),
  "scotiabank peru": icon("scotiabank-pe", "Scotiabank Perú"),
  yape: icon("yape", "Yape"),
};

export function findBankLogo(key: string | null | undefined): BankLogoSpec | null {
  if (!key) return null;
  const norm = key.toLowerCase().trim();
  const exact = BANK_LOGOS[norm];
  if (exact) return exact;

  // Plaid often returns decorated names like "Venmo - Personal" or
  // "Chase – Credit Card". Fall back to the first token split on common
  // separators so those still resolve to the base bank icon.
  const head = norm.split(/\s*[-–—|:]\s*/)[0].trim();
  if (head && head !== norm) {
    const byHead = BANK_LOGOS[head];
    if (byHead) return byHead;
  }
  return null;
}
