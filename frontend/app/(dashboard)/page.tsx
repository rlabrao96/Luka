"use client";
import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KpiCard } from "./components/KpiCard";
import { SpendingChart } from "./components/SpendingChart";
import { CategoryDonut } from "./components/CategoryDonut";
import { RecentTransactions } from "./components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { useHouseholdSummary } from "@/app/lib/hooks/useHousehold";
import { useBudgetStatus } from "@/app/lib/hooks/useBudget";
import { useLukaStore } from "@/app/lib/store";

export default function DashboardPage() {
  const name = useLukaStore((s) => s.userFullName) ?? "tú";
  const { data: myTxns = [] } = useMyTransactions(10);
  const { data: sharedTxns = [] } = useSharedTransactions(10);
  const { data: summary = [] } = useHouseholdSummary();
  const { data: budget } = useBudgetStatus();

  const myRow = summary[0];
  const personalSpent = myRow?.personal_paid ?? 0;
  const memberCount = summary.length || 1;
  const sharedSpent = summary.reduce((sum, r) => sum + r.shared_paid, 0) / memberCount;

  const recentAll = useMemo(
    () =>
      [...myTxns, ...sharedTxns]
        .sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime())
        .slice(0, 8),
    [myTxns, sharedTxns]
  );

  const categoryData = useMemo(() => {
    const categoryMap: Record<string, number> = {};
    recentAll.forEach((t) => {
      if (t.category) categoryMap[t.category] = (categoryMap[t.category] ?? 0) + t.amount;
    });
    return Object.entries(categoryMap)
      .map(([category, amount]) => ({ category, amount }))
      .sort((a, b) => b.amount - a.amount)
      .slice(0, 5);
  }, [recentAll]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-luka-dark">Hola, {name.split(" ")[0]} 👋</h2>
        <p className="text-luka-muted text-sm mt-0.5">Resumen de este mes</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <KpiCard label="Gasto personal" value={`$${Math.round(personalSpent).toLocaleString("es-CL")}`} />
        <KpiCard label="Gasto compartido" value={`$${Math.round(sharedSpent).toLocaleString("es-CL")}`} />
        {budget && (
          <KpiCard
            label="Disponible (cuenta conjunta)"
            value={`$${Math.round(budget.available).toLocaleString("es-CL")}`}
            sublabel={`${budget.percent_used}% usado`}
            trend={budget.percent_used > 80 ? "down" : "neutral"}
            className="col-span-2 lg:col-span-1"
          />
        )}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2 bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-luka-dark">Tendencia de gastos</CardTitle>
          </CardHeader>
          <CardContent>
            {/* TODO: aggregate transactions by month for trend chart */}
            <SpendingChart data={[]} />
          </CardContent>
        </Card>
        <Card className="bg-white">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-luka-dark">Por categoría</CardTitle>
          </CardHeader>
          <CardContent>
            {categoryData.length > 0
              ? <CategoryDonut data={categoryData} />
              : <p className="text-sm text-luka-muted text-center py-8">Sin datos aún</p>
            }
          </CardContent>
        </Card>
      </div>

      {/* Recent Transactions */}
      <Card className="bg-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-luka-dark">Últimas transacciones</CardTitle>
        </CardHeader>
        <CardContent>
          <RecentTransactions transactions={recentAll} />
        </CardContent>
      </Card>
    </div>
  );
}
