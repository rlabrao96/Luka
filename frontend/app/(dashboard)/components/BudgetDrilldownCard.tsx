"use client";
import { X } from "lucide-react";
import type { BudgetV2DrilldownBlock } from "@/app/lib/api";
import { formatMoney, type Currency } from "@/app/lib/format";

interface Props {
  block: BudgetV2DrilldownBlock | undefined;
  loading: boolean;
  error: boolean;
  currency: Currency;
  locale: string;
  onDismiss: () => void;
}

function formatShortDate(iso: string, locale: string): string {
  // Backend sends date as YYYY-MM-DD. Construct in local tz to avoid
  // off-by-one from UTC-at-midnight parsing.
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString(locale, {
    day: "2-digit",
    month: "short",
  });
}

export function BudgetDrilldownCard({
  block,
  loading,
  error,
  currency,
  locale,
  onDismiss,
}: Props) {
  const showDismiss = block !== undefined || loading || error;

  return (
    <div className="rounded-xl border border-slate-100 bg-white p-3 sm:p-5 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Top transacciones
          </p>
          <h4 className="text-base font-semibold text-luka-dark mt-0.5">
            {block?.label ?? "Haz clic en una categoría"}
          </h4>
        </div>
        {showDismiss && (
          <button
            type="button"
            aria-label="Cerrar detalle"
            onClick={onDismiss}
            className="p-1 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X size={16} />
          </button>
        )}
      </div>

      <div className="mt-4">
        {!block && !loading && !error && (
          <p className="text-sm text-slate-500">
            Haz clic en cualquier categoría del flujo para ver las 5
            transacciones más grandes de este mes.
          </p>
        )}
        {loading && (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 rounded bg-slate-100 animate-pulse" />
            ))}
          </div>
        )}
        {error && (
          <p className="text-sm text-red-600">
            No se pudo cargar el detalle. Intenta de nuevo.
          </p>
        )}
        {block && block.kind === "empty" && (
          <p className="text-sm text-slate-500">
            {block.empty_reason ?? "Sin detalle disponible para este nodo."}
          </p>
        )}
        {block && block.kind === "transactions" && block.items.length === 0 && (
          <p className="text-sm text-slate-500">
            No hay transacciones en este mes para esta categoría.
          </p>
        )}
        {block && block.kind === "transactions" && block.items.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {block.items.map((item) => (
              <li
                key={item.id}
                className="py-2.5 flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-luka-dark truncate">
                    {item.merchant}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {formatShortDate(item.date, locale)}
                    {item.bank_name ? ` · ${item.bank_name}` : ""}
                    {item.category ? ` · ${item.category}` : ""}
                  </p>
                </div>
                <span className="text-sm font-semibold text-luka-dark tabular-nums shrink-0">
                  {formatMoney(item.amount, currency)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
