"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PersonalBudgetResponse } from "@/app/lib/api";

interface Props {
  budget: PersonalBudgetResponse;
}

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full bg-gray-100 rounded-full h-2">
      <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function barColor(pct: number | null): string {
  if (!pct) return "bg-blue-600";
  if (pct > 90) return "bg-red-500";
  if (pct > 70) return "bg-yellow-400";
  return "bg-blue-600";
}

export default function WaterfallCards({ budget }: Props) {
  const { household, personal, mode } = budget;

  return (
    <div className="space-y-3">
      {/* Household card — waterfall mode only */}
      {mode === "waterfall" && household && (
        <Card className="bg-white rounded-xl shadow-[var(--shadow-card)]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-gray-800">Hogar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {household.deposited !== null ? (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Depositado</span>
                  <span className="text-gray-800 font-medium">{CLP(household.deposited)}</span>
                </div>
                <ProgressBar
                  value={household.spent}
                  max={household.deposited}
                  color={barColor(household.percent_used)}
                />
                <div className="flex justify-between text-xs text-gray-400">
                  <span>
                    Gastado: {CLP(household.spent)} ({household.percent_used ?? 0}%)
                  </span>
                  <span
                    className={
                      household.available !== null && household.available >= 0
                        ? "text-emerald-600 text-lg font-bold"
                        : "text-red-500 text-lg font-bold"
                    }
                  >
                    {household.available !== null
                      ? household.available >= 0
                        ? `Disponible: ${CLP(household.available)}`
                        : `Excedido: ${CLP(Math.abs(household.available))}`
                      : null}
                  </span>
                </div>
              </>
            ) : (
              <p className="text-sm text-gray-500">
                Gastos compartidos:{" "}
                <span className="text-gray-800 font-medium">{CLP(household.spent)}</span>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Personal card */}
      <Card className="bg-white rounded-xl shadow-[var(--shadow-card)]">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-gray-800">Personal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Techo</span>
            <span
              className={
                personal.ceiling_clamped ? "text-red-500 font-medium" : "text-gray-800 font-medium"
              }
            >
              {personal.ceiling_clamped
                ? "Transferencias superan ingresos"
                : CLP(personal.ceiling)}
            </span>
          </div>

          {!personal.ceiling_clamped && personal.ceiling > 0 && (
            <div className="space-y-2">
              {/* Hogar-tagged bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Hogar</span>
                  <span>{CLP(personal.breakdown.household)}</span>
                </div>
                <ProgressBar
                  value={personal.breakdown.household}
                  max={personal.ceiling}
                  color="bg-sky-400"
                />
              </div>
              {/* Personal bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-400">
                  <span>Personal</span>
                  <span>{CLP(personal.breakdown.personal)}</span>
                </div>
                <ProgressBar
                  value={personal.breakdown.personal}
                  max={personal.ceiling}
                  color="bg-blue-600"
                />
              </div>
            </div>
          )}

          <div
            className={`text-lg font-bold text-right ${
              personal.available >= 0 ? "text-emerald-600" : "text-red-500"
            }`}
          >
            {personal.available >= 0
              ? `Disponible: ${CLP(personal.available)}`
              : `Excedido: ${CLP(Math.abs(personal.available))}`}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
