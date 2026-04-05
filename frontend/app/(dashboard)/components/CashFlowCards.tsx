"use client";
import { TrendingUp, TrendingDown, ArrowRightLeft } from "lucide-react";

interface CashFlowCardsProps {
  income: number;
  expenses: number;
  net: number;
  currency: string;
}

/** Amounts are pre-normalized to standard currency unit (dollars/pesos). */
function fmt(n: number, currency: string): string {
  if (currency === "USD")
    return `US$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(Math.abs(n)).toLocaleString("es-CL")}`;
}

export function CashFlowCards({ income, expenses, net, currency }: CashFlowCardsProps) {
  return (
    <>
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-3 sm:p-4">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-green-100 flex items-center justify-center mb-1.5 sm:mb-2">
          <TrendingUp size={14} className="text-green-600 sm:w-4 sm:h-4" />
        </div>
        <p className="text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide leading-tight">
          Ingresos
        </p>
        <p className="text-base sm:text-2xl font-bold text-green-600 mt-0.5 sm:mt-1 tabular-nums truncate">
          {fmt(income, currency)}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-3 sm:p-4">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-red-100 flex items-center justify-center mb-1.5 sm:mb-2">
          <TrendingDown size={14} className="text-red-600 sm:w-4 sm:h-4" />
        </div>
        <p className="text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide leading-tight">
          Gastos
        </p>
        <p className="text-base sm:text-2xl font-bold text-red-600 mt-0.5 sm:mt-1 tabular-nums truncate">
          ({fmt(expenses, currency)})
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-3 sm:p-4">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-blue-100 flex items-center justify-center mb-1.5 sm:mb-2">
          <ArrowRightLeft size={14} className="text-blue-600 sm:w-4 sm:h-4" />
        </div>
        <p className="text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide leading-tight">
          Neto
        </p>
        <p className={`text-base sm:text-2xl font-bold mt-0.5 sm:mt-1 tabular-nums truncate ${net >= 0 ? "text-blue-600" : "text-red-600"}`}>
          {net >= 0 ? `+${fmt(net, currency)}` : `(${fmt(Math.abs(net), currency)})`}
        </p>
      </div>
    </>
  );
}
