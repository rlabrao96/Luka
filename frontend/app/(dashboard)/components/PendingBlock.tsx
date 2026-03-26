// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { useState, useEffect } from "react";
import { usePendingTransactions } from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction, type PendingTransactions } from "@/app/lib/api";
import { Trash2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const EXPENSE_CATEGORIES = [
  "Alimentación", "Supermercado", "Transporte", "Combustible",
  "Entretenimiento", "Salud", "Farmacia", "Hogar",
  "Ropa", "Tecnología", "Educación", "Viajes", "Servicios", "Otros",
];

const INCOME_CATEGORIES = [
  "Sueldo", "Freelance", "Inversiones", "Arriendo",
  "Bono", "Transferencia de terceros", "Deuda pendiente", "Otros ingresos",
];

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
      {isEmail ? "Email" : "Banco"}
    </span>
  );
}

/* ─── Inline category dropdown (matches CategoryCell in RecentTransactions) ─── */

interface PendingCategoryCellProps {
  txn: Transaction;
}

function PendingCategoryCell({ txn }: PendingCategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const isIncome = Number(txn.amount) < 0;
  const categories = isIncome ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

  async function handleSelect(cat: string | null) {
    setOpen(false);
    setLocalCategory(cat);
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    queryClient.setQueryData(queryKey, (old: PendingTransactions | undefined) => {
      if (!old) return old;
      const patch = (list: Transaction[]) =>
        list.map((t) => (t.id === txn.id ? { ...t, category: cat } : t));
      return {
        ...old,
        awaiting_reconciliation: patch(old.awaiting_reconciliation),
        unmatched_email: patch(old.unmatched_email),
      };
    });
    try {
      await api.updateTransactionCategory(txn.id, cat);
    } catch {
      queryClient.setQueryData(queryKey, previous);
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
          <div className="absolute left-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[160px]">
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

/* ─── PendingSection ─── */

interface PendingSectionProps {
  title: string;
  transactions: Transaction[];
  renderAction?: (txn: Transaction) => React.ReactNode;
  borderLeft?: boolean;
}

function PendingSection({ title, transactions, renderAction, borderLeft }: PendingSectionProps) {
  if (transactions.length === 0) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[10px] uppercase tracking-wide font-semibold text-orange-800 mb-1.5 pl-1">
        {title}
      </p>
      <div className="space-y-1">
        {transactions.map((txn) => {
          const amount = Number(txn.amount);
          const isOutflow = amount >= 0;
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
              {/* Row 2: source + category dropdown (left) | split badge + action (right) */}
              <div className="flex justify-between items-center mt-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <SourceBadge source={txn.source} />
                  <PendingCategoryCell txn={txn} />
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

/* ─── PendingBlock ─── */

export function PendingBlock() {
  const { data, isLoading } = usePendingTransactions();
  const queryClient = useQueryClient();
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

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
      />

      <PendingSection
        title="Sin match bancario"
        transactions={unmatched_email}
        borderLeft
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
    </div>
  );
}
