"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useBudgetStatus } from "@/app/lib/hooks/useBudget";

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export default function BudgetsPage() {
  const { data: budget, isLoading } = useBudgetStatus();

  if (isLoading) return <p className="text-luka-muted">Cargando...</p>;

  if (!budget || budget.budgeted === 0) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-luka-dark">Presupuesto</h2>
        <Card className="bg-white">
          <CardContent className="py-10 text-center">
            <p className="text-luka-muted text-sm">
              No tienes una cuenta conjunta configurada aún.<br />
              Agrega una desde Configuración.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const pct = budget.percent_used;
  const barColor = pct > 90 ? "bg-luka-danger" : pct > 70 ? "bg-yellow-400" : "bg-luka-primary";

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-luka-dark">Presupuesto — Cuenta Conjunta</h2>
      <Card className="bg-white">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-luka-dark">
            {new Date(`${budget.month}-01`).toLocaleDateString("es-CL", { month: "long", year: "numeric", timeZone: "UTC" })}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Main progress */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm font-medium">
              <span className="text-luka-muted">Depositado</span>
              <span className="text-luka-dark">{CLP(budget.budgeted)}</span>
            </div>
            <div className="w-full bg-luka-light rounded-full h-3">
              <div
                className={`${barColor} h-3 rounded-full transition-all`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-luka-muted">
              <span>Gastado: {CLP(budget.spent)} ({Math.round(pct)}%)</span>
              <span className={budget.available < 0 ? "text-luka-danger font-semibold" : "text-luka-success font-semibold"}>
                {budget.available >= 0 ? `Disponible: ${CLP(budget.available)}` : `Excedido: ${CLP(Math.abs(budget.available))}`}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
