"use client";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useSubscriptions } from "@/app/lib/hooks/useSubscriptions";
import { useMyTransactions } from "@/app/lib/hooks/useTransactions";
import type { RecurringExpense } from "@/app/lib/api";

function fmt(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function getNextMonthName() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toLocaleDateString("es-CL", { month: "long", year: "numeric" });
}

function formatTimelineDate(iso: string) {
  const d = new Date(iso + "T00:00:00");
  const day = d.getDate();
  const month = d
    .toLocaleDateString("es-CL", { month: "short" })
    .toUpperCase()
    .replace(".", "");
  return { day, label: `${day} ${month}` };
}

function trendText(sub: RecurringExpense) {
  const prev = sub.previous_amount ?? sub.average_amount;
  const dir = sub.trend === "increased" ? "subió" : "bajó";
  const pct = sub.trend_pct != null ? Math.abs(sub.trend_pct) : 0;
  return `${sub.merchant_name} ${dir} de ${fmt(prev)} a ${fmt(sub.last_amount)} (${sub.trend === "increased" ? "+" : "-"}${Math.round(pct)}%)`;
}

export default function SubscriptionsPage() {
  const { data: subscriptions = [], isLoading } = useSubscriptions();
  const { data: allTxns = [] } = useMyTransactions();

  // Monthly spending for % KPI
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const monthlyTotal = allTxns
    .filter((t) => t.transaction_date.startsWith(currentMonth) && t.amount < 0)
    .reduce((sum, t) => sum + Math.abs(t.amount), 0);

  const totalRecurring = subscriptions.reduce((s, sub) => s + sub.last_amount, 0);
  const pct = monthlyTotal > 0 ? (totalRecurring / monthlyTotal) * 100 : 0;

  // Sorted for timeline
  const sorted = [...subscriptions].sort(
    (a, b) => a.predicted_next_date.localeCompare(b.predicted_next_date),
  );

  // Price change alerts
  const alerts = subscriptions.filter((s) => s.trend !== "stable");

  if (isLoading) {
    return <p className="text-gray-400">Cargando...</p>;
  }

  // Empty state
  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-lg font-semibold text-gray-700">
          No hemos detectado gastos recurrentes aún
        </p>
        <p className="text-sm text-gray-400 mt-2 max-w-xs">
          Necesitamos al menos 2 meses de transacciones para identificar patrones
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
          Suscripciones
        </h2>
        <p className="text-sm text-gray-400 mt-0.5">
          Gastos recurrentes detectados automáticamente
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
              Total mensual recurrente
            </p>
            <p className="text-[22px] font-bold text-gray-900 mt-1 tabular-nums">
              {fmt(totalRecurring)}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              {subscriptions.length} suscripciones activas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
              % de gastos totales
            </p>
            <p className="text-[22px] font-bold text-blue-600 mt-1 tabular-nums">
              {Math.round(pct)}%
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              de {fmt(monthlyTotal)} este mes
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Price change alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((sub) => (
            <div
              key={`alert-${sub.merchant_name}`}
              className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3"
            >
              <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0" />
              <p className="text-sm text-amber-800">{trendText(sub)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Timeline */}
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">
          Próximos cobros — <span className="capitalize">{getNextMonthName()}</span>
        </p>

        <div className="relative border-l-2 border-gray-200 ml-3 pl-6 space-y-4">
          {sorted.map((sub) => {
            const { day, label } = formatTimelineDate(sub.predicted_next_date);
            const isFirstHalf = day <= 15;

            return (
              <div key={sub.merchant_name} className="relative">
                {/* Dot */}
                <div
                  className={`absolute -left-[31px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white ${
                    isFirstHalf ? "bg-blue-600" : "bg-gray-300"
                  }`}
                />
                {/* Date label */}
                <p
                  className={`text-[11px] font-bold uppercase ${
                    isFirstHalf ? "text-blue-600" : "text-gray-400"
                  }`}
                >
                  {label}
                </p>
                {/* Merchant + amount */}
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-sm text-gray-700">{sub.merchant_name}</span>
                  <span className="text-sm font-bold text-gray-900 tabular-nums">
                    {fmt(sub.last_amount)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
