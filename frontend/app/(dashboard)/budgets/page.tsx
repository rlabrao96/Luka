"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/app/lib/api";
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import type { Currency } from "@/app/lib/format";

// NOTE: formatMoney is imported by downstream chunks (B: Sankey, G: risk band,
// H: runway card) once they render monetary values. Keeping the runtime export
// out of this scaffold avoids a TS6133 unused-import warning on `npm run build`.

export default function BudgetsPage() {
  // ── Controls ──
  const [selectedMonth, setSelectedMonth] = useState<Date>(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1)
  );
  const [selectedCurrency, setSelectedCurrency] = useState<Currency>("CLP");

  // Default currency from user preference
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  useEffect(() => {
    if (me?.preferred_currency === "CLP" || me?.preferred_currency === "USD") {
      setSelectedCurrency(me.preferred_currency);
    }
  }, [me?.preferred_currency]);

  // TODO(Chunk C): wire /budgets/v2/{household_id} response here. The shape
  // will include `currencies_available: string[]` so the toggle auto-hides
  // when the household only transacts in one currency. Until then,
  // `budgetV2Data` is undefined and `showToggle` defaults to true.
  type BudgetV2Response = { currencies_available?: string[] };
  const budgetV2Data = undefined as BudgetV2Response | undefined;
  const showToggle = (budgetV2Data?.currencies_available?.length ?? 2) > 1;

  // ── Month nav ──
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

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Presupuesto</h2>
          <p className="text-sm text-gray-400 mt-0.5">Control de ingresos y gastos</p>
        </div>
        {showToggle && (
          <CurrencyToggle
            value={selectedCurrency}
            onChange={(c) => setSelectedCurrency(c as Currency)}
          />
        )}
      </div>

      {/* Month selector */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Mes anterior"
          onClick={prevMonth}
          className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary transition-colors shadow-[var(--shadow-card)]"
        >
          <ChevronLeft size={16} className="text-slate-600" />
        </button>
        <span className="text-sm font-semibold text-luka-dark capitalize min-w-[140px] text-center">
          {selectedMonth.toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </span>
        <button
          type="button"
          aria-label="Mes siguiente"
          onClick={nextMonth}
          disabled={isCurrentMonth}
          className="w-9 h-9 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:border-luka-primary disabled:opacity-30 transition-colors shadow-[var(--shadow-card)]"
        >
          <ChevronRight size={16} className="text-slate-600" />
        </button>
      </div>

      {/* Chunk G will mount <RiskAlertBand> above the HOGAR section. */}

      {/* HOGAR section — Chunk B renders BudgetSankey (household) inside the card. */}
      <section aria-labelledby="household-budget-heading" className="space-y-3">
        <h3
          id="household-budget-heading"
          className="text-[11px] font-semibold uppercase tracking-wide text-slate-400"
        >
          Hogar
        </h3>
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
          <p className="text-sm text-slate-400">Flujo del hogar — Chunk B</p>
        </div>
      </section>

      {/* PERSONAL section — Chunk B renders BudgetSankey (personal) inside the card. */}
      <section aria-labelledby="personal-budget-heading" className="space-y-3">
        <h3
          id="personal-budget-heading"
          className="text-[11px] font-semibold uppercase tracking-wide text-slate-400"
        >
          Personal
        </h3>
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4">
          <p className="text-sm text-slate-400">Flujo personal — Chunk B</p>
        </div>
      </section>

      {/* Chunk H will mount <RunwayCard> below the PERSONAL section. */}
    </div>
  );
}
