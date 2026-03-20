"use client";
import { useMemo } from "react";
import { CreditCard, Users, Wallet, TrendingUp, BarChart3 } from "lucide-react";
import { KpiCard } from "./components/KpiCard";
import { SpendingChart } from "./components/SpendingChart";
import { CategoryDonut } from "./components/CategoryDonut";
import { RecentTransactions } from "./components/RecentTransactions";
import { useMyTransactions, useSharedTransactions, useMonthlySpending } from "@/app/lib/hooks/useTransactions";
import { useHouseholdSummary } from "@/app/lib/hooks/useHousehold";
import { useBudgetStatus } from "@/app/lib/hooks/useBudget";
import { useLukaStore } from "@/app/lib/store";

export default function DashboardPage() {
  const name = useLukaStore((s) => s.userFullName) ?? "tú";
  const { data: myTxns    = [] } = useMyTransactions(200);
  const { data: monthlySpending = [] } = useMonthlySpending();
  const { data: sharedTxns = [] } = useSharedTransactions(10);
  const { data: summary   = [] } = useHouseholdSummary();
  const { data: budget }          = useBudgetStatus();

  const myRow       = summary[0];
  const personalSpent = myRow?.personal_paid ?? 0;
  const memberCount   = summary.length || 1;
  const sharedSpent   = summary.reduce((sum, r) => sum + r.shared_paid, 0) / memberCount;

  const recentAll = useMemo(
    () =>
      [...myTxns, ...sharedTxns]
        .sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime())
        .slice(0, 8),
    [myTxns, sharedTxns]
  );

  const categoryData = useMemo(() => {
    const now = new Date();
    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const map: Record<string, number> = {};
    myTxns
      .filter((t) => {
        const d = new Date(t.transaction_date);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        return key === currentMonth && t.category;
      })
      .forEach((t) => {
        map[t.category!] = (map[t.category!] ?? 0) + Number(t.amount);
      });
    const sorted = Object.entries(map)
      .map(([category, amount]) => ({ category, amount }))
      .sort((a, b) => b.amount - a.amount);
    if (sorted.length <= 5) return sorted;
    const top5 = sorted.slice(0, 5);
    const othersTotal = sorted.slice(5).reduce((s, e) => s + e.amount, 0);
    return [...top5, { category: "Otros", amount: othersTotal }];
  }, [myTxns]);

  const firstName = name.split(" ")[0];
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Buenos días" : hour < 19 ? "Buenas tardes" : "Buenas noches";

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-luka-dark tracking-tight">
            {greeting}, {firstName}
          </h1>
          <p className="text-sm text-luka-muted mt-0.5">Aquí está el resumen de este mes</p>
        </div>
        <div className="text-xs text-luka-muted bg-white border border-slate-200 px-3 py-1.5 rounded-full shadow-sm">
          {new Date().toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </div>
      </div>

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <KpiCard
          label="Gasto personal"
          value={`$${Math.round(personalSpent).toLocaleString("es-CL")}`}
          icon={CreditCard}
          iconColor="bg-blue-100"
          iconTextColor="text-blue-600"
        />
        <KpiCard
          label="Gasto compartido"
          value={`$${Math.round(sharedSpent).toLocaleString("es-CL")}`}
          icon={Users}
          iconColor="bg-sky-100"
          iconTextColor="text-sky-600"
        />
        {budget ? (
          <KpiCard
            label="Disponible (cuenta conjunta)"
            value={`$${Math.round(budget.available).toLocaleString("es-CL")}`}
            sublabel={`${budget.percent_used}% del presupuesto usado`}
            trend={budget.percent_used > 80 ? "down" : "neutral"}
            icon={Wallet}
            iconColor={budget.percent_used > 80 ? "bg-red-100" : "bg-emerald-100"}
            iconTextColor={budget.percent_used > 80 ? "text-red-600" : "text-emerald-600"}
          />
        ) : (
          <KpiCard
            label="Presupuesto"
            value="—"
            sublabel="Sin presupuesto configurado"
            icon={Wallet}
            iconColor="bg-amber-100"
            iconTextColor="text-amber-600"
          />
        )}
      </div>

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Spending trend */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-luka-dark">Tendencia de gastos</h2>
              <p className="text-xs text-luka-muted mt-0.5">Personal vs. compartido</p>
            </div>
          </div>
          <SpendingChart data={monthlySpending} />
        </div>

        {/* Category donut */}
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-luka-dark">Por categoría</h2>
            <p className="text-xs text-luka-muted mt-0.5">Este mes</p>
          </div>
          {categoryData.length > 0
            ? <CategoryDonut data={categoryData} />
            : (
              <div className="h-[200px] flex flex-col items-center justify-center gap-2">
                <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                  <BarChart3 size={18} className="text-slate-400" />
                </div>
                <p className="text-xs text-luka-muted">Sin datos aún</p>
              </div>
            )
          }
        </div>
      </div>

      {/* ── Recent Transactions ── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-luka-dark">Últimas transacciones</h2>
            <p className="text-xs text-luka-muted mt-0.5">Movimientos recientes</p>
          </div>
        </div>
        <RecentTransactions transactions={recentAll} compact={true} />
      </div>
    </div>
  );
}
