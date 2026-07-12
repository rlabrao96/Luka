"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Scale } from "lucide-react";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { formatStoredAmount } from "@/app/lib/currency";

const MEMBER_COLORS = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6"];

const MONTH_LABELS = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];

function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return `${MONTH_LABELS[(m ?? 1) - 1]} ${String(y).slice(2)}`;
}

/** 6-month fairness trend: per member, how much they fronted beyond their
 *  ratio share of shared spending (positive = put in more than their share). */
export function EquityReport({ currency }: { currency: string }) {
  const householdId = useLukaStore((s) => s.householdId);
  const { data } = useQuery({
    queryKey: ["equity-report", householdId, currency],
    queryFn: () => api.getEquityReport(householdId!, currency),
    enabled: !!householdId && !!currency,
    staleTime: 5 * 60 * 1000,
  });

  if (!data || data.months.length === 0) return null;
  const monthsWithData = data.months.filter((m) => Number(m.total) > 0);
  if (monthsWithData.length === 0) return null;

  const memberNames = data.months[data.months.length - 1].members.map(
    (m) => m.full_name,
  );
  const maxAbsNet = Math.max(
    1,
    ...data.months.flatMap((mo) => mo.members.map((m) => Math.abs(Number(m.net)))),
  );

  return (
    <Card>
      <CardContent className="p-5">
        <div className="mb-1 flex items-center gap-2">
          <Scale size={16} className="text-luka-primary" />
          <h3 className="text-sm font-semibold text-luka-dark">Equidad del grupo</h3>
        </div>
        <p className="mb-4 text-xs text-slate-500">
          Cuánto aportó cada persona por sobre (o bajo) su parte del gasto
          compartido, según la proporción configurada.
        </p>

        <div className="mb-3 flex flex-wrap gap-3">
          {memberNames.map((name, i) => (
            <span key={name} className="flex items-center gap-1.5 text-xs text-slate-600">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: MEMBER_COLORS[i % MEMBER_COLORS.length] }}
              />
              {name}
            </span>
          ))}
        </div>

        <div className="space-y-2.5">
          {data.months.map((mo) => (
            <div key={mo.month} className="flex items-center gap-3">
              <span className="w-12 shrink-0 text-[11px] font-medium text-slate-500">
                {monthLabel(mo.month)}
              </span>
              <div className="flex-1 space-y-1">
                {mo.members.map((m, i) => {
                  const net = Number(m.net);
                  const widthPct = Math.min(100, (Math.abs(net) / maxAbsNet) * 100);
                  return (
                    <div key={m.user_id} className="flex items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${widthPct}%`,
                            background:
                              net >= 0
                                ? MEMBER_COLORS[i % MEMBER_COLORS.length]
                                : "#CBD5E1",
                          }}
                        />
                      </div>
                      <span
                        className={`w-24 shrink-0 text-right text-[11px] font-semibold tabular-nums ${
                          net > 0
                            ? "text-luka-dark"
                            : net < 0
                              ? "text-slate-400"
                              : "text-slate-300"
                        }`}
                      >
                        {net === 0
                          ? "—"
                          : `${net > 0 ? "+" : "−"}${formatStoredAmount(Math.abs(net), currency)}`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <p className="mt-3 text-[10px] leading-snug text-slate-400">
          + aportó más que su parte · − aportó menos. Los saldos de cada mes se
          resuelven con el ajuste de cuentas.
        </p>
      </CardContent>
    </Card>
  );
}
