"use client";
import { useState, useEffect } from "react";
import { TrendingDown, TrendingUp, ChevronDown } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Transaction, api } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { TransactionCard } from "./TransactionCard";
import { CategoryBottomSheet } from "./CategoryBottomSheet";
import { SplitTypeEditor } from "./SplitTypeEditor";


function toTitleCase(str: string) {
  return str
    .toLowerCase()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatCLP(amount: number) {
  return `$${Math.round(amount).toLocaleString("es-CL")}`;
}

/** Normalize + format a transaction amount respecting source and currency. */
function formatTxnAmount(txn: { amount: number; currency: string; source: string }): string {
  let val = Math.abs(Number(txn.amount));
  const currency = txn.currency ?? "CLP";
  // USD is always stored as cents (email, manual, plaid)
  if (currency === "USD") val = val / 100;
  if (currency === "USD")
    return `US$${val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(val).toLocaleString("es-CL")}`;
}

function formatDate(iso: string) {
  // Parse as date-only (YYYY-MM-DD) to avoid timezone shift.
  // "2026-03-20T00:00:00+00:00" in UTC would display as Mar 19 in Chile (UTC-3).
  const dateOnly = iso.split("T")[0];
  const [y, m, d] = dateOnly.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/* ─── useIsMobile hook ─── */

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 1023px)");
    setIsMobile(mql.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);
  return isMobile;
}

/* ─── Date grouping utilities ─── */

function getDateKey(iso: string): string {
  return iso.split("T")[0];
}

function formatDateHeader(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.getTime() === today.getTime()) {
    return `Hoy, ${date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" })}`;
  }
  if (date.getTime() === yesterday.getTime()) {
    return `Ayer, ${date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" })}`;
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString("es-CL", { day: "2-digit", month: "short" });
  }
  return date.toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
}

function groupByDate(txns: Transaction[]): Map<string, Transaction[]> {
  const groups = new Map<string, Transaction[]>();
  for (const txn of txns) {
    const key = getDateKey(txn.transaction_date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(txn);
  }
  return groups;
}

/* ─── CategoryCell (desktop inline dropdown) ─── */

interface CategoryCellProps {
  txn: Transaction;
}

function CategoryCell({ txn }: CategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  // Sync if parent passes updated txn (e.g. after refetch)
  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const { expense: expenseCats, income: incomeCats } = useCategories();
  const isIncome = txn.transaction_type === "income";
  const categories = isIncome ? incomeCats : expenseCats;

  async function handleSelect(cat: string | null) {
    setOpen(false);
    setLocalCategory(cat); // instant UI update

    // Optimistically patch cached transaction lists so the whole page reflects the change
    const patchCache = (old: Transaction[] | undefined) =>
      old?.map((t) => (t.id === txn.id ? { ...t, category: cat } : t));
    queryClient.setQueriesData<Transaction[]>({ queryKey: ["transactions"] }, patchCache);

    try {
      await api.updateTransactionCategory(txn.id, cat);
    } catch {
      setLocalCategory(txn.category); // revert on error
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center justify-between gap-1 text-[11px] font-medium px-2 py-1 rounded-md border transition-colors w-[140px]",
          localCategory
            ? "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
            : "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100"
        )}
      >
        <span className="truncate">{localCategory ?? "Sin categoría"}</span>
        <ChevronDown size={10} className="shrink-0" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[160px]">
            <button
              onClick={() => handleSelect(null)}
              className="w-full text-left px-3 py-1.5 text-[11px] text-slate-400 hover:bg-slate-50"
            >
              Sin categoría
            </button>
            <div className="border-t border-slate-100 my-1" />
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => handleSelect(cat)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                  localCategory === cat ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
                )}
              >
                {cat}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ─── RecentTransactions ─── */

interface RecentTransactionsProps {
  transactions: Transaction[];
  compact?: boolean;
}

export function RecentTransactions({
  transactions,
  compact = false,
}: RecentTransactionsProps) {
  const isMobile = useIsMobile();
  const [categorySheet, setCategorySheet] = useState<Transaction | null>(null);
  const queryClient = useQueryClient();

  if (!transactions.length) {
    return (
      <div className="py-12 flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
          <TrendingDown size={18} className="text-slate-400" />
        </div>
        <p className="text-xs text-luka-muted">No hay transacciones.</p>
      </div>
    );
  }

  async function handleCategorySelect(txn: Transaction, category: string | null) {
    const patchCache = (old: Transaction[] | undefined) =>
      old?.map((t) => (t.id === txn.id ? { ...t, category } : t));
    queryClient.setQueriesData<Transaction[]>({ queryKey: ["transactions"] }, patchCache);

    try {
      await api.updateTransactionCategory(txn.id, category);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    }
  }

  const dateGroups = groupByDate(transactions);

  return (
    <div className="space-y-1">
      {Array.from(dateGroups.entries()).map(([dateKey, txns]) => (
        <div key={dateKey}>
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest pt-3 pb-1.5">
            {formatDateHeader(dateKey)}
          </p>
          <div className="space-y-1.5">
            {txns.map((txn) => {
              /* Compact mode: simple card, no editing */
              if (compact) {
                return <TransactionCard key={txn.id} txn={txn} compact />;
              }

              /* Mobile non-compact: card layout with bottom sheet for category, SplitTypeEditor for split */
              if (isMobile) {
                const isOutflow = txn.transaction_type !== "income";
                return (
                  <div
                    key={txn.id}
                    className="bg-white rounded-xl p-3 border border-slate-100 shadow-[var(--shadow-card)]"
                  >
                    <div className="flex items-center gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-baseline gap-2">
                          <p className="text-[13px] font-semibold text-luka-dark truncate">
                            {txn.display_name ?? toTitleCase(txn.raw_merchant_name)}
                          </p>
                          <span
                            className={cn(
                              "text-[13px] font-bold tabular-nums shrink-0",
                              isOutflow ? "text-red-500" : "text-luka-success"
                            )}
                          >
                            {isOutflow
                              ? `(${formatTxnAmount(txn)})`
                              : `+${formatTxnAmount(txn)}`}
                          </span>
                        </div>
                        <div className="flex justify-between items-center mt-1">
                          <div className="flex items-center gap-1 min-w-0">
                            <span className="text-[9px] text-slate-400 shrink-0">
                              {txn.bank_name ? toTitleCase(txn.bank_name) : txn.source === "manual" ? "Manual" : "\u2014"}
                            </span>
                            <button
                              onClick={() => setCategorySheet(txn)}
                              className={cn(
                                "text-[9px] font-medium px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80 max-w-[80px] text-center truncate",
                                txn.category
                                  ? "bg-slate-100 text-slate-600"
                                  : "bg-amber-50 text-amber-600"
                              )}
                            >
                              {txn.category ?? "Sin categor\u00eda"}
                            </button>
                          </div>
                          <SplitTypeEditor txn={txn} isMobile={true} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }

              /* Desktop non-compact: card layout with inline CategoryCell and SplitTypeEditor */
              const isOutflow = txn.transaction_type !== "income";
              return (
                <div
                  key={txn.id}
                  className="bg-white rounded-xl p-3.5 border border-slate-100 shadow-[var(--shadow-card)] flex items-center gap-3"
                >
                  <div
                    className="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center shrink-0"
                    style={{
                      background: isOutflow
                        ? "linear-gradient(135deg, #fef2f2, #fecaca)"
                        : "linear-gradient(135deg, #ecfdf5, #d1fae5)",
                    }}
                  >
                    {isOutflow ? (
                      <TrendingDown size={16} className="text-red-400" strokeWidth={2.5} />
                    ) : (
                      <TrendingUp size={16} className="text-emerald-500" strokeWidth={2.5} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-baseline gap-2">
                      <p className="text-sm font-semibold text-luka-dark truncate">
                        {txn.display_name ?? toTitleCase(txn.raw_merchant_name)}
                      </p>
                      <span
                        className={cn(
                          "text-[15px] font-bold tabular-nums shrink-0",
                          isOutflow ? "text-luka-dark" : "text-luka-success"
                        )}
                      >
                        {isOutflow
                          ? `(${formatTxnAmount(txn)})`
                          : `+${formatTxnAmount(txn)}`}
                      </span>
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-[10px] text-slate-400 shrink-0">
                          {txn.bank_name ? toTitleCase(txn.bank_name) : txn.source === "manual" ? "Agregado Manualmente" : "\u2014"}
                        </span>
                        <CategoryCell txn={txn} />
                      </div>
                      <SplitTypeEditor txn={txn} isMobile={false} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Mobile category bottom sheet */}
      {categorySheet && (
        <CategoryBottomSheet
          open={!!categorySheet}
          onClose={() => setCategorySheet(null)}
          currentCategory={categorySheet.category}
          isIncome={categorySheet.transaction_type === "income"}
          onSelect={(cat) => {
            handleCategorySelect(categorySheet, cat);
            setCategorySheet(null);
          }}
        />
      )}
    </div>
  );
}
