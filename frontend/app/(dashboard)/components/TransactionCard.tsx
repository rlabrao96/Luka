"use client";
import { useState, type ReactNode } from "react";
import { CreditCard } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/app/lib/api";
import { MarkAsCuotaDialog } from "./MarkAsCuotaDialog";
import { formatStoredAmount, isNegativeStored } from "@/app/lib/currency";
import { toTitleCase } from "@/app/lib/strings";
import { DirectionIcon } from "./DirectionIcon";

const SPLIT_STYLES: Record<string, { label: string; className: string }> = {
  personal: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  shared: { label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
};

function bankLabel(txn: Transaction): string {
  if (txn.bank_name) return toTitleCase(txn.bank_name);
  if (txn.source === "manual") return "Manual";
  return "—";
}

interface TransactionCardProps {
  txn: Transaction;
  compact?: boolean;
  currentCategory?: string | null;
  /** Preferred title — falls back to raw_merchant_name (title-cased). */
  displayName?: string | null;
  onCategoryTap?: (txn: Transaction) => void;
  onSplitTap?: (txn: Transaction) => void;
  /** Inline editor node rendered in place of the default category badge. */
  categorySlot?: ReactNode;
  /** Inline editor node rendered in place of the default split badge. */
  splitSlot?: ReactNode;
  /**
   * Show a "Marcar como cuota" action that opens MarkAsCuotaDialog.
   * Opt-in so existing callers are not affected. Only non-compact mode renders it.
   */
  enableMarkCuota?: boolean;
  /**
   * Optional action node rendered at the right edge of the card (after the
   * split pill). Used by RecentTransactions to surface a kebab menu with
   * "Editar nombre / Editar fecha / Vincular".
   */
  actionsSlot?: ReactNode;
}

export function TransactionCard({
  txn,
  compact = false,
  currentCategory,
  displayName,
  onCategoryTap,
  onSplitTap,
  categorySlot,
  splitSlot,
  enableMarkCuota = false,
  actionsSlot,
}: TransactionCardProps) {
  const isOutflow = isNegativeStored(Number(txn.amount));
  const split = SPLIT_STYLES[txn.split_type ?? "personal"] ?? SPLIT_STYLES.personal;
  const category = currentCategory !== undefined ? currentCategory : txn.category;
  const [cuotaOpen, setCuotaOpen] = useState(false);

  const canMarkCuota = enableMarkCuota && !compact && isOutflow;
  const currencyForCuota = (txn.currency ?? "CLP").toUpperCase();
  const title = displayName ?? toTitleCase(txn.raw_merchant_name);

  return (
    <div className="bg-white rounded-xl p-3 sm:p-3.5 border border-slate-100 shadow-[var(--shadow-card)]">
      {canMarkCuota && (
        <MarkAsCuotaDialog
          open={cuotaOpen}
          onClose={() => setCuotaOpen(false)}
          transaction={{
            id: txn.id,
            merchant_name: txn.raw_merchant_name,
            amount: Math.abs(Number(txn.amount) || 0),
            currency: currencyForCuota,
          }}
        />
      )}
      <div className="flex items-center gap-2 sm:gap-3">
        <DirectionIcon direction={isOutflow ? "outflow" : "inflow"} />

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Line 1: Merchant + Amount */}
          <div className="flex justify-between items-baseline gap-2">
            <p className="text-[13px] sm:text-sm font-semibold text-luka-dark truncate">
              {title}
            </p>
            {(() => {
              const formatted = formatStoredAmount(
                Number(txn.amount),
                txn.currency ?? "CLP",
              );
              const visible = isOutflow ? `(${formatted})` : `+${formatted}`;
              // Parentheses on negatives are a visual convention — screen
              // readers spell them literally. Override with "menos X" so
              // the direction is unambiguous without reading punctuation.
              const label = isNegativeStored(Number(txn.amount))
                ? `menos ${formatted}`
                : formatted;
              return (
                <span
                  aria-label={label}
                  className={cn(
                    "text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0",
                    isOutflow ? "text-luka-dark" : "text-luka-success",
                  )}
                >
                  {visible}
                </span>
              );
            })()}
          </div>

          {/* Line 2: Bank + Category + Split */}
          <div className="flex justify-between items-center mt-1">
            <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
              <span className="text-[9px] sm:text-[10px] text-slate-400 shrink-0">
                {bankLabel(txn)}
              </span>
              {!txn.transfer_pair_id && (
                categorySlot !== undefined
                  ? categorySlot
                  : compact ? (
                    <span className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded text-center truncate max-w-[80px] sm:max-w-[90px]", category ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600")}>
                      {category ?? "Sin categoría"}
                    </span>
                  ) : (
                    <button onClick={() => onCategoryTap?.(txn)} className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded text-center truncate max-w-[80px] sm:max-w-[90px] cursor-pointer hover:opacity-80", category ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600")}>
                      {category ?? "Sin categoría"}
                    </button>
                  )
              )}
            </div>
            <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
              {canMarkCuota && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCuotaOpen(true);
                  }}
                  title="Marcar como cuota"
                  className="flex items-center gap-0.5 text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded bg-luka-primary/10 text-luka-primary hover:bg-luka-primary/15"
                >
                  <CreditCard size={10} strokeWidth={2.5} />
                  <span className="hidden sm:inline">Cuota</span>
                </button>
              )}
              {splitSlot !== undefined ? (
                splitSlot
              ) : compact ? (
                <span className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 text-center", split.className)}>
                  {split.label}
                </span>
              ) : (
                <button onClick={() => onSplitTap?.(txn)} className={cn("text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 text-center cursor-pointer hover:opacity-80", split.className)}>
                  {split.label}
                </button>
              )}
              {actionsSlot}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
