import type { BankLogoSpec } from "@/app/lib/bank-logos";

export function BankLogo({ logo, size = 36 }: { logo: BankLogoSpec; size?: number }) {
  if (logo.kind === "mark") {
    return (
      <div
        className="rounded-lg flex items-center justify-center shrink-0 shadow-sm"
        style={{ width: size, height: size, background: logo.bg }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={logo.src}
          alt={logo.alt}
          className="w-[58%] h-[58%]"
          style={{ filter: "brightness(0) invert(1)" }}
        />
      </div>
    );
  }
  return (
    <div
      className="rounded-lg flex items-center justify-center shrink-0 bg-white border border-slate-100"
      style={{ width: size, height: size, padding: Math.max(2, Math.round(size * 0.12)) }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={logo.src}
        alt={logo.alt}
        className="max-w-full max-h-full object-contain"
      />
    </div>
  );
}
