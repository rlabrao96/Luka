"use client";
import { TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/app/lib/api";

const SPLIT_STYLES: Record<string, { label: string; className: string }> = {
  personal: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  partner: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  shared: { label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
};

function toTitleCase(str: string) {
  return str.toLowerCase().split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatAmount(amount: number, currency: string) {
  if (currency === "USD") {
    const dollars = amount / 100;
    return `US$${dollars.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(amount).toLocaleString("es-CL")}`;
}

function bankLabel(txn: Transaction): string {
  if (txn.bank_name) return toTitleCase(txn.bank_name);
  if (txn.source === "manual") return "Manual";
  return "—";
}

interface TransactionCardProps {
  txn: Transaction;
  compact?: boolean;
  currentCategory?: string | null;
  onCategoryTap?: (txn: Transaction) => void;
  onSplitTap?: (txn: Transaction) => void;
}

export function TransactionCard({
  txn,
  compact = false,
  currentCategory,
  onCategoryTap,
  onSplitTap,
}: TransactionCardProps) {
  const isOutflow = txn.transaction_type !== "income";
  const split = SPLIT_STYLES[txn.split_type ?? "personal"] ?? SPLIT_STYLES.personal;
  const category = currentCategory !== undefined ? currentCategory : txn.category;

  return (
    <div className="bg-white rounded-xl p-3 sm:p-3.5 border border-slate-100 shadow-[var(--shadow-card)]">
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Direction icon — hidden on mobile */}
        <div
          className="hidden sm:flex w-[38px] h-[38px] rounded-[10px] items-center justify-center shrink-0"
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

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Line 1: Merchant + Amount */}
          <div className="flex justify-between items-baseline gap-2">
            <p className="text-[13px] sm:text-sm font-semibold text-luka-dark truncate">
              {toTitleCase(txn.raw_merchant_name)}
            </p>
            <span
              className={cn(
                "text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0",
                isOutflow ? "text-luka-dark" : "text-luka-success"
              )}
            >
              {isOutflow
                ? `(${formatAmount(Math.abs(Number(txn.amount)), txn.currency ?? "CLP")})`
                : `+${formatAmount(Math.abs(Number(txn.amount)), txn.currency ?? "CLP")}`}
            </span>
          </div>

          {/* Line 2: Bank + Category + Split */}
          <div className="flex justify-between items-center mt-1">
            <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
              <span className="text-[9px] sm:text-[10px] text-slate-400 shrink-0">
                {bankLabel(txn)}
              </span>
              {compact ? (
                <span className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded text-center truncate max-w-[80px] sm:max-w-[90px]", category ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600")}>
                  {category ?? "Sin categoría"}
                </span>
              ) : (
                <button onClick={() => onCategoryTap?.(txn)} className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded text-center truncate max-w-[80px] sm:max-w-[90px] cursor-pointer hover:opacity-80", category ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600")}>
                  {category ?? "Sin categoría"}
                </button>
              )}
            </div>
            {compact ? (
              <span className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 text-center", split.className)}>
                {split.label}
              </span>
            ) : (
              <button onClick={() => onSplitTap?.(txn)} className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 text-center cursor-pointer hover:opacity-80", split.className)}>
                {split.label}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
