// frontend/app/(dashboard)/components/LinkMatchDialog.tsx
"use client";

import { useMatchCandidates, useLinkTransaction, useDismissTransaction } from "@/app/lib/hooks/useTransactions";
import { formatStoredAmount } from "@/app/lib/currency";
import type { Transaction } from "@/app/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { AlertCircle, Link2, Check } from "lucide-react";
import { toTitleCase } from "@/app/lib/strings";

type Props = {
  pendingTransaction: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function LinkMatchDialog({ pendingTransaction, open, onOpenChange }: Props) {
  const pendingId = pendingTransaction?.id ?? null;
  const { data: candidates, isLoading, isError, refetch } = useMatchCandidates(
    open ? pendingId : null,
    7,
  );
  const link = useLinkTransaction();
  const dismiss = useDismissTransaction();

  function handleLink(bankTransactionId: string) {
    if (!pendingId) return;
    link.mutate(
      { pendingId, bankTransactionId },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  function handleDismiss() {
    if (!pendingId) return;
    dismiss.mutate(pendingId, { onSuccess: () => onOpenChange(false) });
  }

  const pendingAmount = pendingTransaction
    ? formatStoredAmount(Number(pendingTransaction.amount), pendingTransaction.currency ?? "CLP")
    : "";
  const pendingMerchant = pendingTransaction ? toTitleCase(pendingTransaction.raw_merchant_name) : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Vincular con movimiento bancario</DialogTitle>
          {pendingTransaction && (
            <DialogDescription>
              {pendingMerchant} · {pendingAmount}
            </DialogDescription>
          )}
        </DialogHeader>

        {isLoading && (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <AlertCircle className="h-6 w-6 text-red-400" />
            <p className="text-sm text-slate-600">No pudimos cargar los candidatos.</p>
            <button
              onClick={() => refetch()}
              className="text-[12px] font-semibold text-luka-primary border border-luka-primary/40 rounded-md px-3 py-1.5 hover:bg-blue-50 transition-colors"
            >
              Reintentar
            </button>
          </div>
        )}

        {!isLoading && !isError && candidates && candidates.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <p className="text-sm text-slate-600">No encontramos coincidencias</p>
            <button
              onClick={handleDismiss}
              disabled={dismiss.isPending}
              className="text-[12px] font-semibold text-slate-600 border border-slate-200 rounded-md px-3 py-1.5 hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              {dismiss.isPending ? "Marcando…" : "Marcar como resuelta"}
            </button>
          </div>
        )}

        {!isLoading && !isError && candidates && candidates.length > 0 && (
          <ul className="flex flex-col gap-1.5 max-h-[50vh] overflow-y-auto">
            {candidates.map((c) => {
              const date = new Date(c.transaction_date).toLocaleDateString("es-CL", {
                day: "2-digit",
                month: "short",
                year: "numeric",
              });
              const amount = formatStoredAmount(Number(c.amount), c.currency ?? "CLP");
              const merchant = toTitleCase(c.raw_merchant_name);
              const bank = c.bank_account_name ? toTitleCase(c.bank_account_name) : "—";
              const aria = `Vincular con ${merchant}, ${amount}, ${date}, ${bank}`;
              const isPending = link.isPending && link.variables?.bankTransactionId === c.id;
              return (
                <li key={c.id}>
                  <button
                    onClick={() => handleLink(c.id)}
                    disabled={link.isPending}
                    aria-label={aria}
                    className={cn(
                      "w-full text-left flex items-center gap-3 bg-white border border-slate-200 rounded-lg px-3 py-2 hover:bg-blue-50 hover:border-luka-primary/40 transition-colors disabled:opacity-60",
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-baseline gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <p className="text-[13px] font-semibold text-luka-dark truncate">{merchant}</p>
                          {c.status === "pending" && (
                            <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-amber-700 bg-amber-100 border border-amber-200 rounded px-1.5 py-0.5">
                              pendiente
                            </span>
                          )}
                        </div>
                        <span className="text-[13px] font-bold tabular-nums text-slate-700 shrink-0">{amount}</span>
                      </div>
                      <div className="flex justify-between items-center mt-0.5">
                        <span className="text-[11px] text-slate-400 truncate">{bank}</span>
                        <span className="text-[11px] text-slate-400 shrink-0">{date}</span>
                      </div>
                    </div>
                    {isPending ? (
                      <Check className="h-4 w-4 text-luka-primary shrink-0" />
                    ) : (
                      <Link2 className="h-4 w-4 text-slate-300 shrink-0" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {link.isError && (
          <p className="text-[11px] text-red-500 text-center">No pudimos vincular. Intenta de nuevo.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
