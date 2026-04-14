"use client";
import type { BudgetV2RunwayBlock } from "@/app/lib/api";

export function RunwayCard({ runway }: { runway: BudgetV2RunwayBlock }) {
  const atRisk = runway.alert;
  const border = atRisk ? "border-red-200 bg-red-50" : "border-slate-100 bg-white";
  const label = atRisk ? "text-red-700" : "text-luka-dark";

  return (
    <div className={`rounded-xl border p-4 shadow-[var(--shadow-card)] ${border}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Próximo sueldo
      </p>
      <p className={`text-lg font-bold tabular-nums ${label}`}>
        {runway.days_to_payday} días
      </p>
      <p className="text-xs text-slate-500 mt-1 tabular-nums">
        Runway actual: {runway.days_remaining} días
      </p>
    </div>
  );
}
