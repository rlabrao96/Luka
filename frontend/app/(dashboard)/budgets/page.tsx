"use client";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import dynamic from "next/dynamic";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { formatMoney, type Currency } from "@/app/lib/format";
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import { MonthSelector } from "@/app/(dashboard)/components/MonthSelector";
import { PageHeader } from "@/app/(dashboard)/components/PageHeader";
import { usePrimaryCurrency } from "@/app/lib/hooks/useCurrencies";
import { BudgetConfigModal } from "@/app/(dashboard)/components/BudgetConfigModal";
import { RiskAlertBand } from "@/app/(dashboard)/components/RiskAlertBand";
import { BudgetDrilldownCard } from "@/app/(dashboard)/components/BudgetDrilldownCard";
import { localeForCurrency } from "@/app/lib/locale";
import { currentMonthKey, dateFromMonthKey } from "@/app/lib/months";

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
  onNodeClick,
  activeNodeId,
}: {
  data: BudgetV2Response;
  currency: Currency;
  onNodeClick?: (nodeId: string) => void;
  activeNodeId?: string | null;
}) {
  const spendable = Number(data.spendable.amount);
  const spent = Number(data.spendable.spent);
  // v3 emits different node ids per view (ingresos_hogar / ingresos_personales,
  // gastos_fijos / gastos_fijos_personal). Look up both shapes so the overspent
  // banner works for either household or personal response.
  const incomeNode = data.sankey.nodes.find(
    (n) => n.id === "ingresos_hogar" || n.id === "ingresos_personales" || n.kind === "hub"
  );
  const income = Number(incomeNode?.value ?? 0);
  const knownBillsNode = data.sankey.nodes.find(
    (n) => n.id === "gastos_fijos" || n.id === "gastos_fijos_personal"
  );
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
    <div className="min-h-[22rem]">
      <p className="text-xs text-slate-500 mb-2">
        Haz clic en cualquier categoría para ver las 5 transacciones más grandes.
      </p>
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
        onNodeClick={onNodeClick ? (n) => onNodeClick(n.id) : undefined}
        activeNodeId={activeNodeId ?? undefined}
      />
    </div>
  );
}

export default function BudgetsPage() {
  // ── Controls ──
  const nowKey = currentMonthKey();
  const [selectedMonthKey, setSelectedMonthKey] = useState<string>(nowKey);
  const selectedMonth = dateFromMonthKey(selectedMonthKey);
  const primaryCurrency = usePrimaryCurrency();
  const [selectedCurrency, setSelectedCurrency] = useState<Currency>("");

  // Default currency from user's primary (preferred) currency
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  useEffect(() => {
    if (!selectedCurrency && primaryCurrency) setSelectedCurrency(primaryCurrency);
  }, [primaryCurrency, selectedCurrency]);

  const householdId = me?.household_id ?? null;
  const monthStr = monthParam(selectedMonth);

  const [configOpen, setConfigOpen] = useState(false);

  // One active node per Sankey view — clicking a node on the Hogar chart
  // shouldn't disturb Personal's drilldown, and vice versa.
  const [hogarNodeId, setHogarNodeId] = useState<string | null>(null);
  const [personalNodeId, setPersonalNodeId] = useState<string | null>(null);
  // Locale for date formatting in the drilldown list. Matches the Spanish
  // CLAUDE.md rule: derive from currency, don't hardcode es-CL.
  const drilldownLocale = localeForCurrency(me?.preferred_currency);

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

  const hogarDrilldown = useQuery({
    queryKey: [
      "budget-drilldown",
      householdId,
      monthStr,
      selectedCurrency,
      "household",
      hogarNodeId,
    ],
    queryFn: () =>
      api.getBudgetNodeDrilldown(householdId as string, {
        node_id: hogarNodeId as string,
        view: "household",
        month: monthStr,
        currency: selectedCurrency,
      }),
    enabled: !!householdId && !!hogarNodeId,
    staleTime: 60 * 1000,
  });

  const personalDrilldown = useQuery({
    queryKey: [
      "budget-drilldown",
      householdId,
      monthStr,
      selectedCurrency,
      "personal",
      personalNodeId,
    ],
    queryFn: () =>
      api.getBudgetNodeDrilldown(householdId as string, {
        node_id: personalNodeId as string,
        view: "personal",
        month: monthStr,
        currency: selectedCurrency,
      }),
    enabled: !!householdId && !!personalNodeId,
    staleTime: 60 * 1000,
  });


  // Empty state: user has no household
  if (me && !householdId) {
    return (
      <div className="space-y-5">
        <PageHeader title="Presupuesto" subtitle="Control de ingresos y gastos" />
        <div className="rounded-xl border border-slate-100 bg-white p-6 shadow-[var(--shadow-card)] text-center text-sm text-slate-500">
          Crea o únete a un hogar para ver tu presupuesto.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Presupuesto"
        subtitle="Control de ingresos y gastos"
        actions={
          householdId ? (
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
          ) : undefined
        }
        filters={
          <>
            <MonthSelector
              value={selectedMonthKey}
              onChange={setSelectedMonthKey}
              currentMonth={nowKey}
              currency={me?.preferred_currency}
              size="md"
            />
            {selectedCurrency && (
              <CurrencyToggle
                value={selectedCurrency}
                onChange={setSelectedCurrency}
              />
            )}
          </>
        }
      />

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
                <SectionFlowBody
                  data={household.data}
                  currency={selectedCurrency}
                  onNodeClick={(id) => setHogarNodeId((prev) => (prev === id ? null : id))}
                  activeNodeId={hogarNodeId}
                />
              </div>
            )}
            {household.data && (
              <BudgetDrilldownCard
                block={hogarDrilldown.data}
                loading={hogarDrilldown.isFetching && !!hogarNodeId}
                error={hogarDrilldown.isError}
                currency={selectedCurrency}
                locale={drilldownLocale}
                onDismiss={() => setHogarNodeId(null)}
              />
            )}
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
                    <SectionFlowBody
                      data={personal.data}
                      currency={selectedCurrency}
                      onNodeClick={(id) =>
                        setPersonalNodeId((prev) => (prev === id ? null : id))
                      }
                      activeNodeId={personalNodeId}
                    />
                  </div>
                )}
                {personal.data && (
                  <BudgetDrilldownCard
                    block={personalDrilldown.data}
                    loading={personalDrilldown.isFetching && !!personalNodeId}
                    error={personalDrilldown.isError}
                    currency={selectedCurrency}
                    locale={drilldownLocale}
                    onDismiss={() => setPersonalNodeId(null)}
                  />
                )}
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
