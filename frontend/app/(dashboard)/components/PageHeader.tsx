import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /**
   * Top-right slot — primary call-to-action and page-level icon buttons
   * (e.g. "Agregar miembro", refresh, settings gear). Inline with the title
   * on sm+; drops below the title block on narrow mobile if it overflows.
   */
  actions?: ReactNode;
  /**
   * Second row — compact filters that modify the page's data view
   * (MonthSelector, CurrencyToggle, search/filter chips). Always lives
   * below the title row so every page has a predictable "title → filters
   * → content" rhythm.
   */
  filters?: ReactNode;
  /** Opt-in extra classes on the outer header. */
  className?: string;
}

/**
 * Canonical dashboard page header. All top-level routes under (dashboard)/
 * should open with <PageHeader/> so the title, actions, and filters land in
 * the same place regardless of which page the user is on.
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
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-luka-dark tracking-tight">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-luka-muted mt-0.5">{subtitle}</p>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </div>
      {filters && (
        <div className="flex flex-wrap items-center gap-2">{filters}</div>
      )}
    </header>
  );
}
