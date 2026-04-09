"use client";
import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { usePersonalBudget, useAllocation, useSaveAllocation } from "@/app/lib/hooks/useBudget";
import AllocationCard from "@/app/(dashboard)/components/AllocationCard";
import WaterfallCards from "@/app/(dashboard)/components/WaterfallCards";

const PaceChart = dynamic(
  () => import("@/app/(dashboard)/components/PaceChart"),
  { ssr: false, loading: () => <div className="h-[250px] animate-pulse bg-slate-100 rounded-xl" /> },
);

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function getMonthParam(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function BudgetsPage() {
  const [selectedMonth, setSelectedMonth] = useState<Date>(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
  );
  const monthParam = getMonthParam(selectedMonth);

  // Scope every aggregate to a single currency — the backend would otherwise
  // sum CLP and USD together and the numbers would be meaningless. This page
  // doesn't have its own toggle yet, so we use the user's preferred currency.
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  const currency = me?.preferred_currency ?? "CLP";

  const { data: budget, isLoading: budgetLoading } = usePersonalBudget(monthParam, currency);
  const { data: allocation, isLoading: allocLoading } = useAllocation(monthParam, currency);
  const { mutate: saveAllocation, isPending: isSaving } = useSaveAllocation();

  function prevMonth() {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() - 1, 1));
  }
  function nextMonth() {
    const next = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 1);
    if (next <= new Date()) setSelectedMonth(next);
  }
  const isCurrentMonth =
    selectedMonth.getFullYear() === new Date().getFullYear() &&
    selectedMonth.getMonth() === new Date().getMonth();

  if (budgetLoading || allocLoading) {
    return <p className="text-gray-400">Cargando...</p>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Presupuesto</h2>
        <p className="text-sm text-gray-400 mt-0.5">Control de ingresos y gastos</p>
      </div>

      {/* Month selector */}
      <div className="flex items-center gap-3">
        <button
          onClick={prevMonth}
          className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary transition-colors shadow-[var(--shadow-card)]"
        >
          <ChevronLeft size={16} className="text-slate-600" />
        </button>
        <span className="text-sm font-semibold text-luka-dark capitalize min-w-[140px] text-center">
          {selectedMonth.toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </span>
        <button
          onClick={nextMonth}
          disabled={isCurrentMonth}
          className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary disabled:opacity-30 transition-colors shadow-[var(--shadow-card)]"
        >
          <ChevronRight size={16} className="text-slate-600" />
        </button>
      </div>

      {/* Income card */}
      {budget && budget.income > 0 ? (
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
          <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Ingresos del mes</p>
          <p className="text-[22px] font-bold text-luka-dark mt-1 tabular-nums">{CLP(budget.income)}</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
          <p className="text-sm text-slate-400">Conecta tu banco para ver tus ingresos</p>
        </div>
      )}

      {/* Pace chart */}
      {budget?.pace && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Ritmo de gastos
          </p>
          <PaceChart pace={budget.pace} />
        </div>
      )}

      {/* Allocation card */}
      {allocation && budget && (
        <AllocationCard
          allocation={allocation}
          income={budget.income}
          month={monthParam}
          onSave={saveAllocation}
          isSaving={isSaving}
        />
      )}

      {/* Waterfall cards */}
      {budget && <WaterfallCards budget={budget} />}
    </div>
  );
}
