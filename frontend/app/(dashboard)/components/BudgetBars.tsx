"use client";
import type { BudgetStatus, CategoryBudgetItem } from "@/app/lib/api";
import { formatMajorAmount, formatMajorAmountCompact, isZeroDecimalCurrency } from "@/app/lib/currency";

interface CategorySpend {
  category: string;
  amount: number;
}

interface BudgetBarsProps {
  categories: CategorySpend[];
  categoryBudgets: CategoryBudgetItem[];
  budget: BudgetStatus | undefined;
  currency: string;
}

/** Amounts are pre-normalized to standard currency unit.
 *  Zero-decimal currencies (CLP, COP…) get compact abbreviations for large values. */
function fmt(n: number, currency: string): string {
  if (isZeroDecimalCurrency(currency) && Math.abs(n) >= 1_000) {
    return formatMajorAmountCompact(n, currency);
  }
  return formatMajorAmount(n, currency);
}

function pctColor(pct: number): string {
  if (pct >= 100) return "red";
  if (pct >= 80) return "amber";
  if (pct >= 50) return "blue";
  return "green";
}

function barBg(color: string): string {
  const map: Record<string, string> = {
    green: "bg-green-500", blue: "bg-blue-600", amber: "bg-amber-500", red: "bg-red-500",
  };
  return map[color] ?? "bg-blue-600";
}

function textColor(color: string): string {
  const map: Record<string, string> = {
    green: "text-green-600", blue: "text-blue-600", amber: "text-amber-600", red: "text-red-600",
  };
  return map[color] ?? "text-blue-600";
}

export function BudgetBars({ categories, categoryBudgets, budget, currency }: BudgetBarsProps) {
  if (categories.length === 0) return null;

  const budgetMap = new Map(categoryBudgets.map((b) => [b.category, b.amount]));

  return (
    <div className="space-y-4">
      {budget && budget.budgeted > 0 && (
        <div className="pb-3 border-b border-slate-100">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="font-semibold text-slate-700">Presupuesto total</span>
            <span className="text-slate-500">
              <span className={`font-bold ${textColor(pctColor(budget.percent_used))}`}>
                {Math.round(budget.percent_used)}%
              </span>
              {" "}· {fmt(budget.spent, currency)} / {fmt(budget.budgeted, currency)}
            </span>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barBg(pctColor(budget.percent_used))}`}
              style={{ width: `${Math.min(budget.percent_used, 100)}%` }}
            />
          </div>
        </div>
      )}

      {categories.map((cat) => {
        const catBudget = budgetMap.get(cat.category);
        const hasBudget = catBudget != null && catBudget > 0;
        const pct = hasBudget ? (cat.amount / catBudget) * 100 : 0;
        const color = hasBudget ? pctColor(pct) : "blue";

        return (
          <div key={cat.category}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-semibold text-slate-700">{cat.category}</span>
              <span className="text-slate-500">
                {hasBudget ? (
                  <>
                    <span className={`font-bold ${textColor(color)}`}>
                      {Math.round(pct)}%
                    </span>
                    {" "}· {fmt(cat.amount, currency)} / {fmt(catBudget, currency)}
                  </>
                ) : (
                  <span className="font-medium">{fmt(cat.amount, currency)}</span>
                )}
              </span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${barBg(color)}`}
                style={{ width: hasBudget ? `${Math.min(pct, 100)}%` : "100%" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
