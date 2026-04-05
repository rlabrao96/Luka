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
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center mb-2">
          <TrendingUp size={16} className="text-green-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Ingresos del mes
        </p>
        <p className="text-2xl font-bold text-green-600 mt-1 tabular-nums">
          {fmt(income, currency)}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center mb-2">
          <TrendingDown size={16} className="text-red-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Gastos del mes
        </p>
        <p className="text-2xl font-bold text-red-600 mt-1 tabular-nums">
          ({fmt(expenses, currency)})
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
        <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center mb-2">
          <ArrowRightLeft size={16} className="text-blue-600" />
        </div>
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Movimiento neto
        </p>
        <p className={`text-2xl font-bold mt-1 tabular-nums ${net >= 0 ? "text-blue-600" : "text-red-600"}`}>
          {net >= 0 ? `+${fmt(net, currency)}` : `(${fmt(Math.abs(net), currency)})`}
        </p>
      </div>
    </>
  );
}
