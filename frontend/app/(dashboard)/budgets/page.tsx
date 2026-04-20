"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Settings2 } from "lucide-react";
import dynamic from "next/dynamic";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { formatMoney, type Currency } from "@/app/lib/format";
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import { BudgetConfigModal } from "@/app/(dashboard)/components/BudgetConfigModal";
import { RiskAlertBand } from "@/app/(dashboard)/components/RiskAlertBand";
import { RunwayCard } from "@/app/(dashboard)/components/RunwayCard";

// Recharts' Sankey chart pulls in ~40KB of d3 + rendering code.
// Load it on demand so the budgets route shell paints first.
const BudgetSankey = dynamic(
  () => import("@/app/(dashboard)/components/BudgetSankey"),
  { ssr: false, loading: () => <SectionSkeleton /> }
);

function monthParam(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function SectionSkeleton() {
  return (
    <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-[var(--shadow-card)]">
      <div className="animate-pulse space-y-2">
        <div className="h-4 w-1/3 rounded bg-slate-100" />
        <div className="h-40 rounded bg-slate-100" />
      </div>
    </div>
  );
}

function SectionError({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      {message}
    </div>
  );
}

function SectionFlowBody({
  data,
  currency,
}: {
  data: BudgetV2Response;
  currency: Currency;
}) {
  const spendable = Number(data.spendable.amount);
  const spent = Number(data.spendable.spent);
  const income = Number(data.sankey.nodes.find((n) => n.id === "income")?.value ?? 0);
  const knownBillsNode = data.sankey.nodes.find((n) => n.id === "known_bills");
  const knownBills = Number(knownBillsNode?.value ?? 0);
  const cuotas = Number(data.cuotas.this_month);
  const savingsTarget = Number(data.savings_target.target);
  // Overspent case: fixed bills (+ cuotas + savings target) meet or exceed
  // income, so there's nothing left to visualize as a spendable flow. Show
  // an explicit banner with the shortfall breakdown and an actionable
  // next step instead of falling through to a degenerate Sankey.
  if (spendable <= 0 && (spent > 0 || knownBills > 0)) {
    const shortfall = Math.max(0, knownBills + cuotas + savingsTarget - income);
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 space-y-2">
        <p className="font-semibold">Tus compromisos superan tu ingreso este mes.</p>
        <div className="grid grid-cols-2 gap-y-1 text-red-700/90 tabular-nums">
          <span>Ingreso:</span>
          <span className="text-right">{formatMoney(income, currency)}</span>
          <span>Gastos fijos:</span>
          <span className="text-right">{formatMoney(knownBills, currency)}</span>
          {cuotas > 0 && (
            <>
              <span>Cuotas del mes:</span>
              <span className="text-right">{formatMoney(cuotas, currency)}</span>
            </>
          )}
          {savingsTarget > 0 && (
            <>
              <span>Meta de ahorro:</span>
              <span className="text-right">{formatMoney(savingsTarget, currency)}</span>
            </>
          )}
          {shortfall > 0 && (
            <>
              <span className="font-semibold">Déficit:</span>
              <span className="text-right font-semibold">
                -{formatMoney(shortfall, currency)}
              </span>
            </>
          )}
          <span>Gastado este mes:</span>
          <span className="text-right">{formatMoney(spent, currency)}</span>
        </div>
        <p className="text-xs text-red-700/80 pt-1">
          Revisa tus gastos fijos o tu meta de ahorro en Configuración para
          recuperar margen.
        </p>
      </div>
    );
  }
  return (
    <div className="min-h-[22rem] overflow-x-auto">
      <BudgetSankey
        nodes={data.sankey.nodes.map((n) => ({
          id: n.id,
          label: n.label,
          value: Number(n.value),
          risk: n.risk ?? undefined,
          level: n.level ?? undefined,
          kind: n.kind ?? undefined,
          member_id: n.member_id ?? undefined,
        }))}
        links={data.sankey.links.map((l) => ({
          source: l.source,
          target: l.target,
          value: Number(l.value),
        }))}
        currency={currency}
      />
    </div>
  );
}

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

  const householdId = me?.household_id ?? null;
  const monthStr = monthParam(selectedMonth);

  const [configOpen, setConfigOpen] = useState(false);

  // Prefetch budgetSettings so the gear-button empty-state dot is accurate
  // before the user opens the modal.
  const budgetSettings = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
    staleTime: 30 * 1000,
    enabled: !!householdId,
  });
  const needsSetup =
    budgetSettings.data != null &&
    (budgetSettings.data.savings_target_amount == null ||
      budgetSettings.data.payday_day_of_month == null);

  const household = useQuery({
    queryKey: ["budget-v2", householdId, monthStr, selectedCurrency, "household"],
    queryFn: () =>
      api.getBudgetV2(householdId as string, {
        month: monthStr,
        currency: selectedCurrency,
        view: "household",
      }),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });
  const personal = useQuery({
    queryKey: ["budget-v2", householdId, monthStr, selectedCurrency, "personal"],
    queryFn: () =>
      api.getBudgetV2(householdId as string, {
        month: monthStr,
        currency: selectedCurrency,
        view: "personal",
      }),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

  const currenciesAvailable = household.data?.currencies_available ?? ["CLP"];
  const showToggle = currenciesAvailable.length > 1;

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

  // Empty state: user has no household
  if (me && !householdId) {
    return (
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Presupuesto</h2>
          <p className="text-sm text-gray-400 mt-0.5">Control de ingresos y gastos</p>
        </div>
        <div className="rounded-xl border border-slate-100 bg-white p-6 shadow-[var(--shadow-card)] text-center text-sm text-slate-500">
          Crea o únete a un hogar para ver tu presupuesto.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">Presupuesto</h2>
          <p className="text-sm text-gray-400 mt-0.5">Control de ingresos y gastos</p>
        </div>
        <div className="flex items-center gap-2">
          {showToggle && (
            <CurrencyToggle
              value={selectedCurrency}
              onChange={(c) => setSelectedCurrency(c as Currency)}
            />
          )}
          {householdId && (
            <button
              type="button"
              aria-label="Configurar presupuesto"
              onClick={() => setConfigOpen(true)}
              className="relative w-9 h-9 rounded-lg border border-slate-200 bg-white hover:border-luka-primary hover:-translate-y-px transition-all shadow-[var(--shadow-card)] flex items-center justify-center"
            >
              <Settings2 size={16} className="text-slate-700" />
              {needsSetup && (
                <span
                  aria-hidden
                  className="absolute top-1.5 right-1.5 w-[7px] h-[7px] rounded-full bg-luka-primary border-2 border-white"
                />
              )}
            </button>
          )}
        </div>
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

      {/* Risk alert band — silent when no alerts */}
      {household.data && (
        <RiskAlertBand
          riskCategories={household.data.risk_categories}
          currency={selectedCurrency}
        />
      )}

      {/* HOGAR section */}
      <section aria-labelledby="household-budget-heading" className="space-y-3">
        <h3
          id="household-budget-heading"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Hogar
        </h3>
        {household.isPending ? (
          <SectionSkeleton />
        ) : household.isError ? (
          <SectionError message="No se pudo cargar el hogar." />
        ) : (
          <div className="space-y-3">
            {household.data && (
              <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
                <SectionFlowBody data={household.data} currency={selectedCurrency} />
              </div>
            )}
            {household.data && <RunwayCard runway={household.data.runway} />}
          </div>
        )}
      </section>

      {/* PERSONAL section — hidden when it's byte-identical to the Hogar view
          (typically when the caller is the only active member with
          transactions this month; showing two identical Sankeys is noise). */}
      {(() => {
        const sameAsHogar =
          household.data &&
          personal.data &&
          Number(household.data.spendable.amount) === Number(personal.data.spendable.amount) &&
          Number(household.data.spendable.spent) === Number(personal.data.spendable.spent) &&
          household.data.sankey.nodes.length === personal.data.sankey.nodes.length;
        if (sameAsHogar) {
          return (
            <p className="text-xs text-slate-500">
              Tu vista personal coincide con la del hogar este mes — no hay aportes
              de otros miembros activos todavía.
            </p>
          );
        }
        return (
          <section aria-labelledby="personal-budget-heading" className="space-y-3">
            <h3
              id="personal-budget-heading"
              className="text-xs font-semibold uppercase tracking-wide text-slate-400"
            >
              Personal
            </h3>
            {personal.isPending ? (
              <SectionSkeleton />
            ) : personal.isError ? (
              <SectionError message="No se pudo cargar tu vista personal." />
            ) : (
              <div className="space-y-3">
                {personal.data && (
                  <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
                    <SectionFlowBody data={personal.data} currency={selectedCurrency} />
                  </div>
                )}
                {personal.data && <RunwayCard runway={personal.data.runway} />}
              </div>
            )}
          </section>
        );
      })()}

      <BudgetConfigModal
        open={configOpen}
        onOpenChange={setConfigOpen}
        householdId={householdId}
        month={monthStr}
        householdBudget={household.data}
      />
    </div>
  );
}
