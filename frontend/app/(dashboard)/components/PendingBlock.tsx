// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { usePendingTransactions } from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction } from "@/app/lib/api";
import { Trash2 } from "lucide-react";

function formatCLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  const time = d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
  if (diffDays === 0) return `Hoy, ${time}`;
  if (diffDays === 1) return `Ayer, ${time}`;
  return `${diffDays} días`;
}

function SourceBadge({ source }: { source: string }) {
  const isEmail = source === "gmail" || source === "outlook";
  return (
    <span
      className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
        isEmail ? "bg-blue-50 text-blue-600" : "bg-green-50 text-green-600"
      }`}
    >
      {isEmail ? "Email" : "Fintoc"}
    </span>
  );
}

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
        {transactions.map((txn) => (
          <div
            key={txn.id}
            className={`bg-white rounded-lg px-3 py-2.5 flex items-center justify-between ${
              borderLeft ? "border-l-[3px] border-l-amber-400" : ""
            }`}
          >
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">
                {txn.raw_merchant_name}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <SourceBadge source={txn.source} />
                <span className="text-[11px] text-slate-500">
                  {txn.split_type ? `${txn.split_type === "personal" ? "Mío" : txn.split_type === "partner" ? "Pareja" : "Compartido"}` : ""}
                  {txn.category ? ` · ${txn.category}` : ""}
                  {!txn.category && txn.source === "fintoc" ? (
                    <span className="text-red-500">Sin categoría</span>
                  ) : null}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="text-right">
                <p className="text-sm font-semibold text-slate-800 tabular-nums">
                  {formatCLP(Number(txn.amount))}
                </p>
                <p className="text-[10px] text-orange-500">{formatTime(txn.transaction_date)}</p>
              </div>
              {renderAction?.(txn)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PendingBlock() {
  const { data, isLoading } = usePendingTransactions();
  const queryClient = useQueryClient();
  if (isLoading || !data) return null;

  const { awaiting_reconciliation, unmatched_email } = data;
  const total = awaiting_reconciliation.length + unmatched_email.length;

  if (total === 0) return null;

  function handleDelete(id: string) {
    if (!confirm("¿Eliminar esta transacción? Esta acción no se puede deshacer.")) return;
    // Optimistic: remove immediately from cache
    queryClient.setQueryData(["transactions", "pending"], (old: typeof data) => {
      if (!old) return old;
      return {
        ...old,
        unmatched_email: old.unmatched_email.filter((t) => t.id !== id),
      };
    });
    // Fire-and-forget: sync with DB in background
    api.deleteTransaction(id).catch(() => {
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    });
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
        renderAction={(txn) => (
          <button
            onClick={() => handleDelete(txn.id)}
            className="flex items-center gap-1 text-[11px] font-medium text-red-600 border border-red-300 rounded-md px-2.5 py-1.5 hover:bg-red-50 transition-colors"
          >
            <Trash2 size={12} />
            Eliminar
          </button>
        )}
      />
    </div>
  );
}
