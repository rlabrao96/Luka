import type { BankLogoSpec } from "@/app/lib/bank-logos";

/**
 * Render an official app-store icon for a bank. Size defaults to 36 (matches
 * the existing BankIcon initials tile). Uses iOS-style rounded corners (~22%
 * of the side) so the tiles sit well next to the colored-initials fallback.
 */
export function BankLogo({ logo, size = 36 }: { logo: BankLogoSpec; size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={logo.src}
      alt={logo.alt}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className="shrink-0 shadow-sm"
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.22) }}
    />
  );
}
