/**
 * Central registry of official bank/institution logos.
 *
 * Sources:
 *  - "mark" kind: monochrome SVG (simple-icons.org) rendered white on a brand-color tile.
 *  - "wordmark" kind: full-color SVG (Wikimedia Commons) rendered on a white tile.
 *
 * To add a new bank:
 *  1. Drop the SVG into `frontend/public/bank-logos/`
 *  2. Add an entry here keyed by:
 *      - Luka Connect `bank_code` (lowercase), e.g. "bchile"
 *      - or Plaid `institution_name` (lowercase, trimmed), e.g. "bank of america"
 */

export type BankLogoKind = "mark" | "wordmark";

export interface BankLogoSpec {
  src: string;
  kind: BankLogoKind;
  alt: string;
  bg?: string;
}

const mark = (src: string, bg: string, alt: string): BankLogoSpec => ({
  src,
  kind: "mark",
  bg,
  alt,
});

const wordmark = (src: string, alt: string): BankLogoSpec => ({
  src,
  kind: "wordmark",
  alt,
});

export const BANK_LOGOS: Record<string, BankLogoSpec> = {
  // Luka Connect — Chile
  bchile: wordmark("/bank-logos/bchile.svg", "Banco de Chile"),
  falabella: wordmark("/bank-logos/falabella.svg", "Banco Falabella"),

  // Plaid — US (keyed by institution_name.toLowerCase().trim())
  venmo: mark("/bank-logos/venmo.svg", "#3D95CE", "Venmo"),
  "american express": mark("/bank-logos/amex.svg", "#006FCF", "American Express"),
  "bank of america": mark("/bank-logos/bankofamerica.svg", "#E31837", "Bank of America"),
  chase: mark("/bank-logos/chase.svg", "#117ACA", "Chase"),
};

export function findBankLogo(key: string | null | undefined): BankLogoSpec | null {
  if (!key) return null;
  return BANK_LOGOS[key.toLowerCase().trim()] ?? null;
}
