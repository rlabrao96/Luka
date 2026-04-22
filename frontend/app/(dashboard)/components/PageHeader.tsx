import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /**
   * Controls row — all compact, 36px-tall chips and icon buttons that
   * belong to this page. Canonical order (enforced by convention, not the
   * component) is:
   *
   *   currency → month → icon actions (refresh, settings, ratios, ...)
   *   → filter triggers (search, filter)
   *
   * Big primary CTAs ("Agregar miembro", full-text buttons) do NOT belong
   * here — the header is for controls that modify the current view, not
   * for destructive or navigational buttons. Place those inline with the
   * section of the page they act on.
   */
  controls?: ReactNode;
  /** Opt-in extra classes on the outer header. */
  className?: string;
}

/**
 * Canonical dashboard page header. Two rows max:
 *
 *   1. title + subtitle
 *   2. controls (currency, month, icon actions, filter triggers)
 *
 * Row 2 flex-wraps on narrow viewports; every control is a 36px-tall chip
 * so they align on the same baseline whether they're labels, icons, or
 * pill toggles.
 */
export function PageHeader({
  title,
  subtitle,
  controls,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("space-y-3", className)}>
      <div className="min-w-0">
        <h1 className="text-2xl font-bold text-luka-dark tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-luka-muted mt-0.5">{subtitle}</p>
        )}
      </div>
      {controls && (
        <div className="flex flex-wrap items-center gap-2">{controls}</div>
      )}
    </header>
  );
}
