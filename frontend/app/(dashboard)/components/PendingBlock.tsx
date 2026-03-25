// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { useState } from "react";
import { usePendingTransactions } from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction, type PendingTransactions } from "@/app/lib/api";
import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { CategoryBottomSheet } from "./CategoryBottomSheet";

const SPLIT_STYLES: Record<string, { label: string; className: string }> = {
  personal: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  partner: { label: "Personal", className: "bg-blue-50 text-blue-600" },
  shared: { label: "Hogar", className: "bg-emerald-50 text-emerald-600" },
};

function toTitleCase(str: string) {
  return str.toLowerCase().split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatCLP(amount: number) {
  return `$${Math.round(amount).toLocaleString("es-CL")}`;
}

function SourceBadge({ source }: { source: string }) {
  const isEmail = source === "gmail" || source === "outlook";
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0",
        isEmail ? "bg-blue-50 text-blue-600" : "bg-green-50 text-green-600"
      )}
    >
      {isEmail ? "Email" : "Fintoc"}
    </span>
  );
}

interface PendingSectionProps {
  title: string;
  transactions: Transaction[];
  renderAction?: (txn: Transaction) => React.ReactNode;
  onCategoryClick?: (txn: Transaction) => void;
  borderLeft?: boolean;
}

function PendingSection({ title, transactions, renderAction, onCategoryClick, borderLeft }: PendingSectionProps) {
  if (transactions.length === 0) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[10px] uppercase tracking-wide font-semibold text-orange-800 mb-1.5 pl-1">
        {title}
      </p>
      <div className="space-y-1">
        {transactions.map((txn) => {
          const amount = Number(txn.amount);
          const isOutflow = amount >= 0; // email txns stored as positive = expense
          const formattedAmount = isOutflow
            ? `(${formatCLP(Math.abs(amount))})`
            : `+${formatCLP(Math.abs(amount))}`;
          const split = txn.split_type ? SPLIT_STYLES[txn.split_type] : null;

          return (
            <div
              key={txn.id}
              className={cn(
                "bg-white rounded-lg px-3 py-2.5",
                borderLeft ? "border-l-[3px] border-l-amber-400" : ""
              )}
            >
              {/* Row 1: name + amount */}
              <div className="flex justify-between items-baseline gap-2">
                <p className="text-sm font-semibold text-slate-800 truncate">
                  {toTitleCase(txn.raw_merchant_name)}
                </p>
                <span
                  className={cn(
                    "text-[15px] font-bold tabular-nums shrink-0",
                    isOutflow ? "text-slate-800" : "text-emerald-600"
                  )}
                >
                  {formattedAmount}
                </span>
              </div>
              {/* Row 2: source + category (left) | split badge + action (right) */}
              <div className="flex justify-between items-center mt-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <SourceBadge source={txn.source} />
                  {onCategoryClick ? (
                    <button
                      onClick={() => onCategoryClick(txn)}
                      className={cn(
                        "text-[10px] font-medium px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80 w-[90px] text-center truncate",
                        txn.category ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600"
                      )}
                    >
                      {txn.category ?? "Sin categoría"}
                    </button>
                  ) : txn.category ? (
                    <span className="text-[11px] text-slate-400 truncate">{txn.category}</span>
                  ) : null}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {split && (
                    <span
                      className={cn(
                        "text-[10px] font-medium px-1.5 py-0.5 rounded w-[60px] text-center",
                        split.className
                      )}
                    >
                      {split.label}
                    </span>
                  )}
                  {renderAction?.(txn)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PendingBlock() {
  const { data, isLoading } = usePendingTransactions();
  const queryClient = useQueryClient();
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [categorySheet, setCategorySheet] = useState<{
    txnId: string;
    currentCategory: string | null;
    isIncome: boolean;
  } | null>(null);

  if (isLoading || !data) return null;

  const { awaiting_reconciliation, unmatched_email } = data;
  const total = awaiting_reconciliation.length + unmatched_email.length;

  if (total === 0) return null;

  function handleDelete(id: string) {
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    setConfirmingId(null);
    queryClient.setQueryData(queryKey, (old: typeof data) => {
      if (!old) return old;
      return { ...old, unmatched_email: old.unmatched_email.filter((t) => t.id !== id) };
    });
    api.deleteTransaction(id)
      .catch(() => queryClient.setQueryData(queryKey, previous));
  }

  function handleCategorySelect(category: string | null) {
    if (!categorySheet) return;
    const { txnId } = categorySheet;
    setCategorySheet(null);
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    // Optimistic: update category in cache immediately
    queryClient.setQueryData(queryKey, (old: PendingTransactions | undefined) => {
      if (!old) return old;
      const update = (list: Transaction[]) =>
        list.map((t) => (t.id === txnId ? { ...t, category } : t));
      return {
        ...old,
        awaiting_reconciliation: update(old.awaiting_reconciliation),
        unmatched_email: update(old.unmatched_email),
      };
    });
    // Sync to DB + train merchant data in background
    api.updateCategory(txnId, category ?? "")
      .catch(() => queryClient.setQueryData(queryKey, previous));
  }

  return (
    <div className="bg-orange-50 border border-orange-300 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[15px] font-bold text-orange-700">Pendientes</span>
        <span className="bg-orange-400 text-white text-[11px] font-semibold rounded-full px-2 py-0.5">
          {total}
        </span>
      </div>

      <PendingSection
        title="Esperando confirmación bancaria"
        transactions={awaiting_reconciliation}
        onCategoryClick={(txn) =>
          setCategorySheet({ txnId: txn.id, currentCategory: txn.category ?? null, isIncome: Number(txn.amount) < 0 })
        }
      />

      <PendingSection
        title="Sin match bancario"
        transactions={unmatched_email}
        borderLeft
        onCategoryClick={(txn) =>
          setCategorySheet({ txnId: txn.id, currentCategory: txn.category ?? null, isIncome: Number(txn.amount) < 0 })
        }
        renderAction={(txn) =>
          confirmingId === txn.id ? (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-slate-500">¿Eliminar?</span>
              <button
                onClick={() => handleDelete(txn.id)}
                className="text-[11px] font-semibold text-white bg-red-500 rounded-md px-2 py-1 hover:bg-red-600 transition-colors"
              >
                Sí
              </button>
              <button
                onClick={() => setConfirmingId(null)}
                className="text-[11px] font-medium text-slate-500 border border-slate-200 rounded-md px-2 py-1 hover:bg-slate-50 transition-colors"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmingId(txn.id)}
              className="flex items-center gap-1 text-[11px] font-medium text-red-600 border border-red-300 rounded-md px-2 py-1 hover:bg-red-50 transition-colors"
            >
              <Trash2 size={11} />
              Eliminar
            </button>
          )
        }
      />

      {categorySheet && (
        <CategoryBottomSheet
          open={!!categorySheet}
          onClose={() => setCategorySheet(null)}
          currentCategory={categorySheet.currentCategory}
          isIncome={categorySheet.isIncome}
          onSelect={handleCategorySelect}
        />
      )}
    </div>
  );
}
