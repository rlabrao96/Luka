"use client";

import { useMemo, useState } from "react";
import { useCreateCuota } from "@/app/lib/hooks/useCuotas";

type Props = {
  open: boolean;
  onClose: () => void;
  transaction: {
    id: string;
    merchant_name: string;
    amount: number;
    currency: "CLP" | "USD";
  };
};

/**
 * MarkAsCuotaDialog — Chunk E.
 *
 * Prefilled from an existing transaction (merchant + amount + currency).
 * The user picks installments count + first cuota date; the server computes
 * monthly_amount and last_cuota_date.
 */
export function MarkAsCuotaDialog({ open, onClose, transaction }: Props) {
  const [installments, setInstallments] = useState("3");
  const [firstDate, setFirstDate] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
  });
  const [splitType, setSplitType] = useState<"personal" | "shared">("personal");
  const createCuota = useCreateCuota();

  const installmentsNum = Number(installments) || 0;
  const absAmount = Math.abs(Number(transaction.amount) || 0);
  const monthlyPreview = useMemo(() => {
    if (!installmentsNum || installmentsNum <= 0) return null;
    return absAmount / installmentsNum;
  }, [absAmount, installmentsNum]);

  if (!open) return null;

  const formatPreview = (n: number) => {
    if (transaction.currency === "USD") {
      return `US$${(n / 100).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    return `$${Math.round(n).toLocaleString("es-CL")}`;
  };

  const disabled =
    createCuota.isPending || installmentsNum < 2 || !firstDate;

  const handleConfirm = () => {
    createCuota.mutate(
      {
        merchant_name: transaction.merchant_name,
        total_amount: absAmount,
        currency: transaction.currency,
        installments_total: installmentsNum,
        first_cuota_date: firstDate,
        split_type: splitType,
        origin_transaction_id: transaction.id,
      },
      { onSuccess: onClose },
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <h3 className="text-base font-bold text-luka-dark">Marcar como cuota</h3>
          <p className="text-xs text-slate-500 truncate">
            {transaction.merchant_name}
          </p>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Total: {formatPreview(absAmount)}
          </p>
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">
            Número de cuotas
          </label>
          <input
            type="number"
            min={2}
            max={60}
            value={installments}
            onChange={(e) => setInstallments(e.target.value)}
            className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-luka-primary/20"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">
            Primera cuota
          </label>
          <input
            type="date"
            value={firstDate}
            onChange={(e) => setFirstDate(e.target.value)}
            className="w-full mt-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-luka-primary/20"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">Tipo</label>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSplitType("personal")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                splitType === "personal"
                  ? "border-luka-primary bg-luka-primary/10 text-luka-primary"
                  : "border-slate-200 text-slate-500"
              }`}
            >
              Personal
            </button>
            <button
              type="button"
              onClick={() => setSplitType("shared")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                splitType === "shared"
                  ? "border-emerald-500 bg-emerald-50 text-emerald-600"
                  : "border-slate-200 text-slate-500"
              }`}
            >
              Compartido
            </button>
          </div>
        </div>

        {monthlyPreview !== null && installmentsNum >= 2 && (
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            Pagarás{" "}
            <span className="font-semibold text-luka-dark">
              {formatPreview(monthlyPreview)}
            </span>{" "}
            por {installmentsNum} meses.
          </div>
        )}

        {createCuota.isError && (
          <p className="text-xs text-red-500">
            {(createCuota.error as Error)?.message ?? "Error al guardar"}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-600"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={disabled}
            className="flex-1 rounded-lg bg-luka-primary py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {createCuota.isPending ? "Guardando..." : "Confirmar"}
          </button>
        </div>
      </div>
    </div>
  );
}
