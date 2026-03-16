"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHouseholdSummary, usePartnerStats } from "@/app/lib/hooks/useHousehold";
import { useLukaStore } from "@/app/lib/store";
import { Shield } from "lucide-react";

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function ContributionBar({ name, amount, total }: { name: string; amount: number; total: number }) {
  const pct = total > 0 ? Math.round((amount / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium text-luka-dark">{name}</span>
        <span className="text-luka-muted">{CLP(amount)} ({pct}%)</span>
      </div>
      <div className="w-full bg-luka-light rounded-full h-2.5">
        <div className="bg-luka-primary h-2.5 rounded-full" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function HouseholdPage() {
  const { data: summary = [] } = useHouseholdSummary();
  const { data: partnerStats } = usePartnerStats();
  const myName = useLukaStore((s) => s.userFullName) ?? "Tú";

  const total = summary.reduce((sum, r) => sum + r.total_paid, 0);
  const partnerRow = summary[1];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-luka-dark">Mi Hogar</h2>

      {/* Monthly Contributions */}
      <Card className="bg-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-luka-dark">
            Contribuciones este mes — {CLP(total)} total
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {summary.map((row) => (
            <ContributionBar
              key={row.user_id}
              name={row.full_name}
              amount={row.total_paid}
              total={total}
            />
          ))}
        </CardContent>
      </Card>

      {/* Partner Stats (aggregate only) */}
      {partnerStats && (
        <Card className="bg-white border border-luka-light">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-sm font-semibold text-luka-dark">
                Resumen de {partnerRow?.full_name ?? myName}
              </CardTitle>
              <Shield size={14} className="text-luka-muted" />
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-luka-muted">Total gastado</span>
              <span className="font-semibold text-luka-dark">{CLP(partnerStats.total_spent)}</span>
            </div>
            <div className="border-t border-slate-100 pt-3">
              <p className="text-xs text-luka-muted mb-2 font-medium uppercase tracking-wide">Por categoría</p>
              {(partnerStats.by_category ?? []).map(({ category, amount }) => (
                <div key={category} className="flex justify-between text-sm py-1">
                  <span className="text-luka-dark">{category}</span>
                  <span className="text-luka-muted">{CLP(amount)}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-luka-muted flex items-center gap-1 pt-1">
              <Shield size={11} /> No se muestran transacciones individuales por privacidad.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
