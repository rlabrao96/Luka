"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import { api, type Transaction } from "@/app/lib/api";
import { formatStoredAmount, isNegativeStored } from "@/app/lib/currency";
import { resolveAppLocale } from "@/app/lib/locale";
import { toTitleCase } from "@/app/lib/strings";
import { cn } from "@/lib/utils";

function useDebounced(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

/** ⌘K / Ctrl-K command palette searching the caller's transactions by
 *  merchant, category, or amount. Selecting a row jumps to /transactions
 *  filtered to that month with the merchant pre-searched. */
export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const debouncedQ = useDebounced(q, 250);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    const onOpenEvent = () => setOpen(true);
    window.addEventListener("luka:open-search", onOpenEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("luka:open-search", onOpenEvent);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      // Focus after the dialog paints.
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const results = useQuery({
    queryKey: ["global-search", debouncedQ],
    queryFn: () => api.searchTransactions(debouncedQ),
    enabled: open && debouncedQ.trim().length >= 2,
    staleTime: 30 * 1000,
  });

  if (!open) return null;

  const rows: Transaction[] = results.data ?? [];
  const locale = resolveAppLocale();

  const goTo = (t: Transaction) => {
    setOpen(false);
    const month = t.transaction_date.slice(0, 7);
    const params = new URLSearchParams({
      month,
      q: t.display_name ?? t.raw_merchant_name,
    });
    router.push(`/transactions?${params.toString()}`);
  };

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center bg-black/40 px-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Buscar transacciones"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-slate-100 px-4">
          <Search size={16} className="shrink-0 text-slate-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Busca por comercio, categoría o monto…"
            className="h-12 w-full bg-transparent text-sm text-luka-dark outline-none placeholder:text-slate-400"
            aria-label="Buscar transacciones"
          />
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
            aria-label="Cerrar búsqueda"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[50vh] overflow-y-auto">
          {debouncedQ.trim().length < 2 && (
            <p className="px-4 py-6 text-center text-xs text-slate-400">
              Escribe al menos 2 caracteres. Tip: también funciona con montos
              (ej. “45.990”).
            </p>
          )}
          {results.isFetching && (
            <p className="px-4 py-4 text-center text-xs text-slate-400">Buscando…</p>
          )}
          {results.isSuccess && rows.length === 0 && debouncedQ.trim().length >= 2 && (
            <p className="px-4 py-6 text-center text-xs text-slate-400">
              Sin resultados para “{debouncedQ}”.
            </p>
          )}
          {rows.length > 0 && (
            <ul className="divide-y divide-slate-50 py-1">
              {rows.map((t) => {
                const isOutflow = isNegativeStored(t.amount);
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => goTo(t)}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-50"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-luka-dark">
                          {toTitleCase(t.display_name ?? t.raw_merchant_name)}
                        </p>
                        <p className="text-[11px] text-slate-500">
                          {new Date(t.transaction_date).toLocaleDateString(locale, {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                          {t.category ? ` · ${t.category}` : ""}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 text-sm font-semibold tabular-nums",
                          isOutflow ? "text-red-500" : "text-luka-success",
                        )}
                      >
                        {isOutflow ? "-" : "+"}
                        {formatStoredAmount(t.amount, t.currency ?? "CLP")}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <div className="border-t border-slate-100 px-4 py-2 text-[10px] text-slate-400">
          ⌘K para abrir · Esc para cerrar
        </div>
      </div>
    </div>
  );
}
