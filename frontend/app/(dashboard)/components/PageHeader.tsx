import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /**
   * Actions row — page-level buttons (primary CTAs and icon buttons) that
   * belong to this page. Rendered on its own line, below the title, always
   * left-aligned. Examples: "Agregar miembro", refresh, settings gear,
   * "Marcar todas leídas".
   */
  actions?: ReactNode;
  /**
   * Filters row — compact controls that modify the page's data view.
   * Order is deliberate and consistent across every page:
   *   currency → month → everything else (search, filter icons, ...).
   * Pass the controls in that order; PageHeader just flex-wraps them.
   */
  filters?: ReactNode;
  /** Opt-in extra classes on the outer header. */
  className?: string;
}

/**
 * Canonical dashboard page header. All top-level routes under (dashboard)/
 * open with <PageHeader/> so the title block, actions, and filter chips
 * always land in the same place — on mobile AND on desktop. The three
 * rows are:
 *
 *   1. title + subtitle
 *   2. actions (left-aligned, this page's primary buttons)
 *   3. filters (left-aligned, currency first, then month, then others)
 *
 * If a row has no content it's skipped, so the header compresses on pages
 * that don't need all three bands.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  filters,
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
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
      {filters && (
        <div className="flex flex-wrap items-center gap-2">{filters}</div>
      )}
    </header>
  );
}
