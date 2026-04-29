"use client";

import { Sparkles, Check, X } from "lucide-react";
import {
  useCreditSuggestions,
  useConfirmCreditSuggestion,
  useDismissCreditSuggestion,
} from "@/app/lib/hooks/useCreditSuggestions";

function fmtAmount(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-CL", { day: "numeric", month: "short" });
}

export function CreditSuggestionsBanner() {
  const { data: suggestions = [] } = useCreditSuggestions();
  const confirm = useConfirmCreditSuggestion();
  const dismiss = useDismissCreditSuggestion();

  if (suggestions.length === 0) return null;

  return (
    <div className="space-y-2 mb-4">
      {suggestions.map((s) => (
        <div
          key={s.id}
          className="rounded-xl border border-blue-200 bg-blue-50 p-4 flex items-start gap-3"
        >
          <div className="w-9 h-9 rounded-lg bg-luka-primary text-white flex items-center justify-center shrink-0">
            <Sparkles size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-luka-dark">
              Detectamos un reembolso
            </p>
            <p className="text-xs text-slate-600 mt-1">
              <span className="font-medium">{s.merchant_credit_name}</span>{" "}
              ({fmtAmount(s.amount, s.currency)}) parece compensar tu{" "}
              <span className="font-medium">{s.merchant_counterpart_name}</span>{" "}
              del {fmtDate(s.counterpart_date)}. ¿Vincular?
            </p>
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => confirm.mutate(s.id)}
                disabled={confirm.isPending || dismiss.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-luka-primary text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                <Check size={14} />
                Confirmar
              </button>
              <button
                onClick={() => dismiss.mutate(s.id)}
                disabled={confirm.isPending || dismiss.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white text-xs text-slate-600 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                <X size={14} />
                Ignorar
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
