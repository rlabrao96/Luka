/**
 * Central registry of official bank/institution app icons.
 *
 * Source: Apple App Store artwork (512×512 PNG).
 *
 * To add a new bank:
 *  1. Find the app on the App Store and grab its 512×512 artwork URL from
 *     https://itunes.apple.com/search?term=<app>&country=<cc>&entity=software
 *     (field `artworkUrl512`).
 *  2. Save the PNG into `frontend/public/bank-logos/<slug>.png`.
 *  3. Add one entry here keyed by:
 *      - Luka Connect `bank_code` (lowercase), e.g. "bchile"
 *      - or Plaid `institution_name` (lowercase, trimmed), e.g. "bank of america"
 */

export interface BankLogoSpec {
  src: string;
  alt: string;
}

export const BANK_LOGOS: Record<string, BankLogoSpec> = {
  // Luka Connect — Chile (keyed by bank_code)
  bchile: { src: "/bank-logos/bchile.png", alt: "Banco de Chile" },
  falabella: { src: "/bank-logos/falabella.png", alt: "Banco Falabella" },

  // Plaid — US (keyed by institution_name.toLowerCase().trim())
  venmo: { src: "/bank-logos/venmo.png", alt: "Venmo" },
  "american express": { src: "/bank-logos/amex.png", alt: "American Express" },
  "bank of america": { src: "/bank-logos/bankofamerica.png", alt: "Bank of America" },
  chase: { src: "/bank-logos/chase.png", alt: "Chase" },
};

export function findBankLogo(key: string | null | undefined): BankLogoSpec | null {
  if (!key) return null;
  return BANK_LOGOS[key.toLowerCase().trim()] ?? null;
}
