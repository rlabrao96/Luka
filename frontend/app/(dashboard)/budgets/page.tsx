"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
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

  const { data: budget, isLoading: budgetLoading } = usePersonalBudget(monthParam);
  const { data: allocation, isLoading: allocLoading } = useAllocation(monthParam);
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
      <div className="flex items-center gap-3 text-sm">
        <button onClick={prevMonth} className="text-gray-400 hover:text-gray-800">
          ‹
        </button>
        <span className="font-medium text-gray-800 capitalize">
          {selectedMonth.toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </span>
        <button
          onClick={nextMonth}
          disabled={isCurrentMonth}
          className="text-gray-400 hover:text-gray-800 disabled:opacity-30"
        >
          ›
        </button>
      </div>

      {/* Income header */}
      <div className="text-sm text-gray-400">
        {budget && budget.income > 0 ? (
          <span>
            Ingresos: <span className="text-gray-900 font-semibold">{CLP(budget.income)}</span>
          </span>
        ) : (
          <span className="text-gray-400">Conecta tu banco para ver tus ingresos</span>
        )}
      </div>

      {/* Pace chart */}
      {budget?.pace && (
        <div className="bg-white rounded-xl border border-gray-100 p-4">
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
