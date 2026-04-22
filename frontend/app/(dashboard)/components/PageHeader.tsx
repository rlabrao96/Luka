import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /**
   * Left-aligned controls — view filters the user reaches for on every
   * page. Canonical order is CurrencyToggle → MonthSelector. Keeping them
   * on the left gives every page the same visual anchor point.
   */
  controls?: ReactNode;
  /**
   * Right-aligned actions — page-level icon buttons, filter triggers, and
   * small status actions (refresh, settings gear, ratios, search/filter,
   * mark-all-read). All 36px tall so they sit on the same baseline as the
   * left-group chips.
   *
   * Big primary CTAs ("Agregar miembro", full-text buttons) do NOT belong
   * here — the header is for controls that modify the current view.
   * Place those inline with the section they act on.
   */
  actions?: ReactNode;
  /** Opt-in extra classes on the outer header. */
  className?: string;
}

/**
 * Canonical dashboard page header. Two rows max:
 *
 *   1. title + subtitle
 *   2. [controls left-aligned]       [actions right-aligned]
 *
 * Row 2 uses justify-between so the two groups anchor to opposite edges
 * on wide viewports; on narrow viewports they flex-wrap with no gap
 * between groups (they collapse into a single left-aligned stream).
 */
export function PageHeader({
  title,
  subtitle,
  controls,
  actions,
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
      {(controls || actions) && (
        <div className="flex flex-wrap items-center gap-2 justify-between">
          {controls && (
            <div className="flex flex-wrap items-center gap-2">{controls}</div>
          )}
          {actions && (
            <div className="flex flex-wrap items-center gap-2 ml-auto">
              {actions}
            </div>
          )}
        </div>
      )}
    </header>
  );
}
