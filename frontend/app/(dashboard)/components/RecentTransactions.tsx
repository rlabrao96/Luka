"use client";
import { useState, useEffect } from "react";
import { TrendingDown, ChevronDown } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Transaction, api } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { useLukaStore } from "@/app/lib/store";
import { TransactionCard } from "./TransactionCard";
import { CategoryPicker } from "./CategoryPicker";
import { SplitTypeEditor } from "./SplitTypeEditor";
import { resolveAppLocale } from "@/app/lib/locale";
import { useBreakpoint } from "@/app/lib/hooks/useBreakpoint";
import { EmptyState } from "./EmptyState";
import { PairedTransactionCard, groupPairs } from "./PairedTransactionCard";

// Match the user's OS locale for date labels. SSR-safe via resolveAppLocale.
const RESOLVED_LOCALE = resolveAppLocale();

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

    // Optimistically patch array-shaped caches only — ["transactions","mine"]
    // and ["transactions","shared"] are Transaction[]; ["transactions","pending"]
    // is the 3-bucket PendingTransactions object which would crash .map().
    const patchCache = (old: Transaction[] | undefined) =>
      Array.isArray(old)
        ? old.map((t) => (t.id === txn.id ? { ...t, category: cat } : t))
        : old;
    queryClient.setQueriesData<Transaction[]>(
      {
        predicate: (q) => {
          const [root, bucket] = q.queryKey as unknown as [string, string];
          return root === "transactions" && (bucket === "mine" || bucket === "shared");
        },
      },
      patchCache,
    );

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
  const isMobile = useBreakpoint("lg");
  const showCuotaButton = useLukaStore((s) => s.showCuotaButton);
  const [categorySheet, setCategorySheet] = useState<Transaction | null>(null);
  const queryClient = useQueryClient();

  if (!transactions.length) {
    return <EmptyState icon={TrendingDown} message="No hay transacciones." height={140} />;
  }

  async function handleCategorySelect(txn: Transaction, category: string | null) {
    const patchCache = (old: Transaction[] | undefined) =>
      Array.isArray(old)
        ? old.map((t) => (t.id === txn.id ? { ...t, category } : t))
        : old;
    queryClient.setQueriesData<Transaction[]>(
      {
        predicate: (q) => {
          const [root, bucket] = q.queryKey as unknown as [string, string];
          return root === "transactions" && (bucket === "mine" || bucket === "shared");
        },
      },
      patchCache,
    );

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

                /* Non-compact: delegate to TransactionCard with slotted editors.
                 * Mobile → category opens a bottom sheet via onCategoryTap.
                 * Desktop → inline CategoryCell dropdown via categorySlot. */
                return (
                  <TransactionCard
                    key={txn.id}
                    txn={txn}
                    displayName={txn.display_name}
                    onCategoryTap={isMobile ? (t) => setCategorySheet(t) : undefined}
                    categorySlot={!isMobile ? <CategoryCell txn={txn} /> : undefined}
                    splitSlot={<SplitTypeEditor txn={txn} isMobile={isMobile} />}
                    enableMarkCuota={showCuotaButton}
                  />
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Mobile category picker */}
      {categorySheet && (
        <CategoryPicker
          open={!!categorySheet}
          onClose={() => setCategorySheet(null)}
          currentCategory={categorySheet.category}
          dominantSign={Number(categorySheet.amount) > 0 ? "positive" : "negative"}
          onSelect={(cat) => {
            handleCategorySelect(categorySheet, cat);
            setCategorySheet(null);
          }}
        />
      )}
    </div>
  );
}
