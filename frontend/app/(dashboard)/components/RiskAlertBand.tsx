"use client";
import { formatMoney, type Currency } from "@/app/lib/format";
import type { BudgetV2RiskCategory } from "@/app/lib/api";

export function RiskAlertBand({
  riskCategories,
  currency,
}: {
  riskCategories: BudgetV2RiskCategory[];
  currency: Currency;
}) {
  const alertsToShow = riskCategories.filter((c) => c.alert);
  if (alertsToShow.length === 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-[var(--shadow-card)] space-y-2"
    >
      {alertsToShow.map((rc) => (
        <p key={rc.name} className="text-sm text-amber-900">
          <span aria-hidden="true">⚠️ </span>
          <span className="font-semibold">{rc.name}</span> va al{" "}
          <span className="tabular-nums">{Math.round(rc.p_overshoot * 100)}%</span> · Al ritmo
          actual cerraría en{" "}
          <span className="tabular-nums">{formatMoney(rc.projected_final, currency)}</span>{" "}
          (límite <span className="tabular-nums">{formatMoney(rc.cap, currency)}</span>).
        </p>
      ))}
    </div>
  );
}
