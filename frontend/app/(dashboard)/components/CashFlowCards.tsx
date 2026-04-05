"use client";
import { TrendingUp, TrendingDown, ArrowRightLeft } from "lucide-react";

interface CashFlowCardsProps {
  income: number;
  expenses: number;
  net: number;
  currency: string;
}

/** Full format for desktop. */
function fmt(n: number, currency: string): string {
  if (currency === "USD")
    return `US$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(Math.abs(n)).toLocaleString("es-CL")}`;
}

/** Compact format for mobile — abbreviate large CLP values, drop USD decimals. */
function fmtCompact(n: number, currency: string): string {
  const abs = Math.abs(n);
  if (currency === "USD") {
    if (abs >= 10_000) return `US$${(abs / 1000).toFixed(0)}k`;
    return `US$${abs.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
  if (abs >= 1_000_000) return `$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `$${Math.round(abs / 1000)}k`;
  return `$${Math.round(abs).toLocaleString("es-CL")}`;
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
        <p className="text-sm sm:text-2xl font-bold text-green-600 mt-0.5 sm:mt-1 tabular-nums">
          <span className="sm:hidden">{fmtCompact(income, currency)}</span>
          <span className="hidden sm:inline">{fmt(income, currency)}</span>
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-3 sm:p-4">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-red-100 flex items-center justify-center mb-1.5 sm:mb-2">
          <TrendingDown size={14} className="text-red-600 sm:w-4 sm:h-4" />
        </div>
        <p className="text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide leading-tight">
          Gastos
        </p>
        <p className="text-sm sm:text-2xl font-bold text-red-600 mt-0.5 sm:mt-1 tabular-nums">
          <span className="sm:hidden">({fmtCompact(expenses, currency)})</span>
          <span className="hidden sm:inline">({fmt(expenses, currency)})</span>
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-3 sm:p-4">
        <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-blue-100 flex items-center justify-center mb-1.5 sm:mb-2">
          <ArrowRightLeft size={14} className="text-blue-600 sm:w-4 sm:h-4" />
        </div>
        <p className="text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide leading-tight">
          Neto
        </p>
        <p className={`text-sm sm:text-2xl font-bold mt-0.5 sm:mt-1 tabular-nums ${net >= 0 ? "text-blue-600" : "text-red-600"}`}>
          <span className="sm:hidden">
            {net >= 0 ? `+${fmtCompact(net, currency)}` : `(${fmtCompact(Math.abs(net), currency)})`}
          </span>
          <span className="hidden sm:inline">
            {net >= 0 ? `+${fmt(net, currency)}` : `(${fmt(Math.abs(net), currency)})`}
          </span>
        </p>
      </div>
    </>
  );
}
