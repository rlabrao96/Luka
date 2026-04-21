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
import { formatStoredAmount } from "@/app/lib/currency";
import { PairedTransactionCard, groupPairs } from "./PairedTransactionCard";

// Derived once: match the user's OS locale for date labels rather than
// hardcoding es-CL. Task 4.6 polish. SSR fallback to es-CL.
const RESOLVED_LOCALE =
  typeof Intl !== "undefined"
    ? Intl.DateTimeFormat().resolvedOptions().locale || "es-CL"
    : "es-CL";


function toTitleCase(str: string) {
  return str
    .toLowerCase()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Format a stored transaction amount (absolute, no sign). */
function formatTxnAmount(txn: { amount: number; currency: string }): string {
  return formatStoredAmount(Number(txn.amount), txn.currency ?? "CLP");
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
    return `Hoy, ${date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" })}`;
  }
  if (date.getTime() === yesterday.getTime()) {
    return `Ayer, ${date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" })}`;
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" });
  }
  return date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short", year: "numeric" });
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
  const isIncome = Number(txn.amount) > 0;
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

  const allItems = groupPairs(transactions);

  function getItemDateKey(item: import("./PairedTransactionCard").TransactionOrPair): string {
    if (item.kind === "single") return getDateKey(item.txn.transaction_date);
    let maxDate = item.legs[0].transaction_date;
    for (let i = 1; i < item.legs.length; i++) {
      if (item.legs[i].transaction_date > maxDate) maxDate = item.legs[i].transaction_date;
    }
    return getDateKey(maxDate);
  }

  const dateGroups = new Map<string, import("./PairedTransactionCard").TransactionOrPair[]>();
  for (const item of allItems) {
    const key = getItemDateKey(item);
    if (!dateGroups.has(key)) dateGroups.set(key, []);
    dateGroups.get(key)!.push(item);
  }

  const sortedDates = Array.from(dateGroups.keys()).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-1">
      {sortedDates.map((dateKey) => {
        const items = dateGroups.get(dateKey)!;
        return (
          <div key={dateKey}>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest pt-3 pb-1.5">
              {formatDateHeader(dateKey)}
            </p>
            <div className="space-y-1.5">
              {items.map((item) => {
                if (item.kind === "pair") {
                  return (
                    <PairedTransactionCard
                      key={item.pairId}
                      pairId={item.pairId}
                      pairType={item.pairType}
                      legs={item.legs}
                    />
                  );
                }
                const txn = item.txn;
                /* Compact mode: simple card, no editing */
                if (compact) {
                  return <TransactionCard key={txn.id} txn={txn} compact />;
                }

                // TODO(chunk-E): wire MarkAsCuotaDialog into the mobile / desktop
                // non-compact transaction row. The dialog component lives at
                // `./MarkAsCuotaDialog` and is already prefillable from a txn.
                // The current non-compact layouts are inlined rather than
                // delegating to TransactionCard, so exposing the "Marcar como
                // cuota" affordance here requires adding a button adjacent to
                // SplitTypeEditor / the desktop row actions and managing a
                // per-txn open-state map. Deferring to a follow-up to avoid
                // refactoring RecentTransactions during the parallel sprint.

                /* Mobile non-compact: card layout with bottom sheet for category, SplitTypeEditor for split */
                if (isMobile) {
                  const isOutflow = Number(txn.amount) < 0;
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
                                {txn.category ?? "Sin categoría"}
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
                const isOutflow = Number(txn.amount) < 0;
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
        );
      })}

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
