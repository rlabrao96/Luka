"use client";
import { useState } from "react";
import { TrendingDown, TrendingUp, ChevronDown } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Transaction, api } from "@/app/lib/api";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  "Alimentación",
  "Supermercado",
  "Transporte",
  "Combustible",
  "Entretenimiento",
  "Salud",
  "Farmacia",
  "Hogar",
  "Ropa",
  "Tecnología",
  "Educación",
  "Viajes",
  "Servicios",
  "Otros",
];

const SPLIT_STYLES: Record<string, { label: string; className: string }> = {
  personal: { label: "Personal", className: "bg-blue-50 text-blue-600 border-blue-100" },
  partner: { label: "Pareja", className: "bg-purple-50 text-purple-600 border-purple-100" },
  shared: { label: "Compartido", className: "bg-emerald-50 text-emerald-600 border-emerald-100" },
};

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

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface CategoryCellProps {
  txn: Transaction;
  queryKeys: (string | number | null)[][];
}

function CategoryCell({ txn, queryKeys }: CategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  async function handleSelect(cat: string | null) {
    setOpen(false);
    setSaving(true);
    try {
      await api.updateTransactionCategory(txn.id, cat);
      // Invalidate all provided query keys so the list re-fetches with new category
      queryKeys.forEach((key) => queryClient.invalidateQueries({ queryKey: key }));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className={cn(
          "flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md border transition-colors",
          txn.category
            ? "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
            : "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100",
          saving && "opacity-50 cursor-wait"
        )}
      >
        <span>{saving ? "..." : (txn.category ?? "Sin categoría")}</span>
        <ChevronDown size={10} />
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
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => handleSelect(cat)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                  txn.category === cat ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
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

interface RecentTransactionsProps {
  transactions: Transaction[];
  queryKeys?: (string | number | null)[][];
  compact?: boolean;
}

export function RecentTransactions({
  transactions,
  queryKeys = [["transactions", "mine"], ["transactions", "shared"]],
  compact = false,
}: RecentTransactionsProps) {
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

  return (
    <div className="divide-y divide-slate-50">
      {transactions.map((txn) => {
        const isOutflow = txn.transaction_type !== "income";
        const split = SPLIT_STYLES[txn.split_type ?? "personal"] ?? SPLIT_STYLES.personal;

        return (
          <div
            key={txn.id}
            className="flex items-center gap-4 py-3.5 group hover:bg-slate-50/50 -mx-1 px-1 rounded-lg transition-colors"
          >
            {/* Direction indicator */}
            <div
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                isOutflow ? "bg-red-50" : "bg-emerald-50"
              )}
            >
              {isOutflow ? (
                <TrendingDown size={15} className="text-red-400" strokeWidth={2} />
              ) : (
                <TrendingUp size={15} className="text-emerald-500" strokeWidth={2} />
              )}
            </div>

            {/* Merchant + bank */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-luka-dark truncate leading-tight">
                {toTitleCase(txn.raw_merchant_name)}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">
                {txn.bank_name ? toTitleCase(txn.bank_name) : "—"}
                {" · "}
                {formatDate(txn.transaction_date)}
              </p>
            </div>

            {/* Category + split + amount */}
            <div className={cn("flex items-center gap-2.5 shrink-0", compact && "gap-2")}>
              {!compact && <CategoryCell txn={txn} queryKeys={queryKeys} />}
              <span
                className={cn(
                  "text-[10px] font-semibold px-2 py-0.5 rounded-full border",
                  split.className
                )}
              >
                {split.label}
              </span>
              <span
                className={cn(
                  "text-sm font-bold tabular-nums w-28 text-right",
                  isOutflow ? "text-luka-dark" : "text-luka-success"
                )}
              >
                {isOutflow ? "−" : "+"}{formatCLP(Math.abs(Number(txn.amount)))}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
