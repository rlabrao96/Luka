"use client";
import { useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { BarChart3 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { MonthSelector } from "./components/MonthSelector";
import { CurrencyToggle } from "./components/CurrencyToggle";
import { BalanceCard } from "./components/BalanceCard";
import { CashFlowCards } from "./components/CashFlowCards";
import { BudgetBars } from "./components/BudgetBars";
import { RecentTransactions } from "./components/RecentTransactions";

import { useMyTransactions, useMonthlySpending } from "@/app/lib/hooks/useTransactions";
import { useBudgetStatus, useCategoryBudgets } from "@/app/lib/hooks/useBudget";
import { useLukaStore } from "@/app/lib/store";
import { api, type BankAccountRow } from "@/app/lib/api";

// Lazy-load chart components (~200KB Recharts bundle)
const SpendingChart = dynamic(
  () => import("./components/SpendingChart").then((m) => ({ default: m.SpendingChart })),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-slate-100 rounded-xl" /> },
);
const CategoryDonut = dynamic(
  () => import("./components/CategoryDonut").then((m) => ({ default: m.CategoryDonut })),
  { ssr: false, loading: () => <div className="h-[200px] animate-pulse bg-slate-100 rounded-xl" /> },
);

function getCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthKey(iso: string): string {
  return iso.split("T")[0].slice(0, 7);
}

/** Normalize a transaction amount to its currency's standard unit (dollars/pesos).
 *  Gmail stores USD in cents; all other sources store in dollars/pesos directly. */
function normalizeTxnAmount(t: { amount: number; currency: string; source: string }): number {
  const raw = Number(t.amount);
  if ((t.currency ?? "CLP") === "USD" && t.source === "gmail") return raw / 100;
  return raw;
}

export default function DashboardPage() {
  const name = useLukaStore((s) => s.userFullName) ?? "tú";
  const householdId = useLukaStore((s) => s.householdId);

  // ── Controls ──
  const currentMonth = getCurrentMonth();
  const [selectedMonth, setSelectedMonth] = useState(currentMonth);
  const [selectedCurrency, setSelectedCurrency] = useState("CLP");

  // Default currency from user preference
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  useEffect(() => {
    if (me?.preferred_currency) setSelectedCurrency(me.preferred_currency);
  }, [me?.preferred_currency]);

  const isViewingPast = selectedMonth !== currentMonth;

  // ── Data ──
  const { data: myTxns = [] } = useMyTransactions();
  const { data: monthlySpending = [] } = useMonthlySpending();
  const { data: budget } = useBudgetStatus(selectedMonth);
  const { data: catBudgets } = useCategoryBudgets(selectedMonth);
  const { data: accounts = [] } = useQuery<BankAccountRow[]>({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

  // ── Derived: filter transactions by month + currency ──
  const monthTxns = useMemo(
    () => myTxns.filter(
      (t) => getMonthKey(t.transaction_date) === selectedMonth
        && (t.currency ?? "CLP") === selectedCurrency
    ),
    [myTxns, selectedMonth, selectedCurrency]
  );

  // Cash flow (normalized to standard currency unit)
  const income = useMemo(
    () => monthTxns.filter((t) => normalizeTxnAmount(t) > 0).reduce((s, t) => s + normalizeTxnAmount(t), 0),
    [monthTxns]
  );
  const expenses = useMemo(
    () => monthTxns.filter((t) => normalizeTxnAmount(t) < 0).reduce((s, t) => s + Math.abs(normalizeTxnAmount(t)), 0),
    [monthTxns]
  );
  const net = income - expenses;

  // Category breakdown (top 5 + Otros)
  const categoryData = useMemo(() => {
    const map: Record<string, number> = {};
    monthTxns
      .filter((t) => normalizeTxnAmount(t) < 0)
      .forEach((t) => {
        const cat = t.category ?? "Otros";
        map[cat] = (map[cat] ?? 0) + Math.abs(normalizeTxnAmount(t));
      });
    const sorted = Object.entries(map)
      .map(([category, amount]) => ({ category, amount }))
      .sort((a, b) => b.amount - a.amount);
    if (sorted.length <= 5) return sorted;
    const top5 = sorted.slice(0, 5);
    const overflowTotal = sorted.slice(5).reduce((s, e) => s + e.amount, 0);
    if (overflowTotal === 0) return top5;
    const othersIdx = top5.findIndex((e) => e.category === "Otros");
    if (othersIdx >= 0) {
      return top5.map((e, i) => i === othersIdx ? { ...e, amount: e.amount + overflowTotal } : e);
    }
    return [...top5, { category: "Otros", amount: overflowTotal }];
  }, [monthTxns]);

  // Recent transactions (latest 5 for selected month/currency)
  const recentTxns = useMemo(
    () => [...monthTxns]
      .sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime())
      .slice(0, 5),
    [monthTxns]
  );

  // ── Greeting ──
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
          <p className="text-sm text-luka-muted mt-0.5">Aquí está tu resumen financiero</p>
        </div>
        <div className="flex items-center gap-2">
          <MonthSelector value={selectedMonth} onChange={setSelectedMonth} currentMonth={currentMonth} />
          <CurrencyToggle value={selectedCurrency} onChange={setSelectedCurrency} />
        </div>
      </div>

      {/* Banner for past month */}
      {isViewingPast && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm text-blue-700 text-center">
          Viendo datos de {new Date(Number(selectedMonth.split("-")[0]), Number(selectedMonth.split("-")[1]) - 1).toLocaleDateString("es-CL", { month: "long", year: "numeric" })}
        </div>
      )}

      {/* ── Section 1: Balance + Cash Flow ── */}
      <div className={`grid gap-4 ${
        isViewingPast
          ? "grid-cols-1 sm:grid-cols-3"
          : "grid-cols-1 sm:grid-cols-3 md:grid-cols-4"
      }`}>
        {!isViewingPast && (
          <BalanceCard accounts={accounts} currency={selectedCurrency} />
        )}
        <CashFlowCards
          income={income}
          expenses={expenses}
          net={net}
          currency={selectedCurrency}
        />
      </div>

      {/* ── Section 2: Spending Trend ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-luka-dark">Tendencia de gastos</h2>
            <p className="text-xs text-luka-muted mt-0.5">Personal vs. compartido</p>
          </div>
          <div className="flex gap-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
              Personal
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
              Compartido
            </span>
          </div>
        </div>
        <div className="h-[140px] md:h-[200px]">
          <SpendingChart data={monthlySpending} currency={selectedCurrency} />
        </div>
      </div>

      {/* ── Section 3: Category Donut + Budget Bars ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Category donut */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-luka-dark">Por categoría</h2>
            <p className="text-xs text-luka-muted mt-0.5">
              {isViewingPast
                ? new Date(Number(selectedMonth.split("-")[0]), Number(selectedMonth.split("-")[1]) - 1).toLocaleDateString("es-CL", { month: "long" })
                : "Este mes"
              }
            </p>
          </div>
          {categoryData.length > 0 ? (
            <CategoryDonut data={categoryData} currency={selectedCurrency} />
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center gap-2">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                <BarChart3 size={18} className="text-slate-400" />
              </div>
              <p className="text-xs text-luka-muted">Sin datos aún</p>
            </div>
          )}
        </div>

        {/* Budget bars */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-5">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-luka-dark">Gasto por categoría</h2>
            <p className="text-xs text-luka-muted mt-0.5">Top 5 categorías</p>
          </div>
          {categoryData.length > 0 ? (
            <BudgetBars
              categories={categoryData.slice(0, 5)}
              categoryBudgets={catBudgets?.budgets ?? []}
              budget={budget}
              currency={selectedCurrency}
            />
          ) : (
            <div className="h-[200px] flex flex-col items-center justify-center gap-2">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                <BarChart3 size={18} className="text-slate-400" />
              </div>
              <p className="text-xs text-luka-muted">Sin datos aún</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Section 4: Recent Transactions ── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-luka-dark">Últimas transacciones</h2>
            <p className="text-xs text-luka-muted mt-0.5">Movimientos recientes</p>
          </div>
          <a href="/transactions" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
            Ver todas →
          </a>
        </div>
        <RecentTransactions transactions={recentTxns} compact={true} />
      </div>
    </div>
  );
}
