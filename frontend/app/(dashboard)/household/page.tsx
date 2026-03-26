"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Pencil } from "lucide-react";
import {
  useHouseholdSummary,
  useCategoryBreakdown,
  useSettlement,
  useSplitRatio,
} from "@/app/lib/hooks/useHousehold";
import { useLukaStore } from "@/app/lib/store";
import SplitRatioModal from "./SplitRatioModal";

function fmt(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

function getLast6Months(): { value: string; label: string }[] {
  const now = new Date();
  const months: { value: string; label: string }[] = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
    months.push({ value, label });
  }
  return months;
}

function currentMonthLabel(): string {
  const now = new Date();
  return `${MONTH_NAMES[now.getMonth()]} ${now.getFullYear()}`;
}

export default function HouseholdPage() {
  const householdId = useLukaStore((s) => s.householdId);
  const [selectedMonth, setSelectedMonth] = useState<string | undefined>(undefined);
  const [splitModalOpen, setSplitModalOpen] = useState(false);

  const { data: summary = [], isLoading: loadingSummary } = useHouseholdSummary();
  const { data: breakdown = [], isLoading: loadingBreakdown } = useCategoryBreakdown(selectedMonth);
  const { data: settlement, isLoading: loadingSettlement } = useSettlement(selectedMonth);
  const { data: splitRatio } = useSplitRatio();

  const monthOptions = getLast6Months();
  const displayMonth = selectedMonth
    ? monthOptions.find((m) => m.value === selectedMonth)?.label ?? selectedMonth
    : currentMonthLabel();

  // Loading state
  if (loadingSummary) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Mi Hogar</h2>
          <p className="text-sm text-luka-muted mt-0.5">Contribuciones y resumen del grupo</p>
        </div>
        <p className="text-sm text-luka-muted">Cargando...</p>
      </div>
    );
  }

  // Empty state — no household
  if (!householdId || summary.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Mi Hogar</h2>
          <p className="text-sm text-luka-muted mt-0.5">Contribuciones y resumen del grupo</p>
        </div>
        <Card className="bg-white">
          <CardContent className="py-10 text-center">
            <p className="text-sm text-luka-muted">
              No perteneces a un hogar todavia.<br />
              Invita a tu pareja desde Configuracion.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Derived data
  const totalShared = summary.reduce((sum, r) => sum + r.shared_paid, 0);
  const memberNames: [string, string] = [
    summary[0]?.full_name ?? "Miembro 1",
    summary[1]?.full_name ?? "Miembro 2",
  ];
  const memberAmounts = [summary[0]?.shared_paid ?? 0, summary[1]?.shared_paid ?? 0];
  const memberPcts = totalShared > 0
    ? memberAmounts.map((a) => Math.round((a / totalShared) * 100))
    : [0, 0];
  const ratio = splitRatio?.split_ratio ?? [50, 50];

  // Category breakdown totals for footer
  const breakdownTotalByMember = [0, 0];
  let breakdownGrandTotal = 0;
  for (const row of breakdown) {
    breakdownGrandTotal += row.total;
    for (let i = 0; i < 2; i++) {
      breakdownTotalByMember[i] += row.member_totals[i]?.amount ?? 0;
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Mi Hogar</h2>
        <p className="text-sm text-luka-muted mt-0.5">Contribuciones y resumen del grupo</p>
      </div>

      {/* 1. Hero Card */}
      <Card className="bg-white">
        <CardContent className="py-6 text-center space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Gastos compartidos — {displayMonth}
          </p>
          <p className="text-3xl font-bold text-luka-dark">{fmt(totalShared)}</p>

          {/* Member summaries */}
          <div className="flex justify-center gap-8">
            {[0, 1].map((i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: i === 0 ? "#3B82F6" : "#EC4899" }}
                />
                <span className="text-slate-600">{memberNames[i]}</span>
                <span className="font-semibold text-slate-800">
                  {fmt(memberAmounts[i])}
                </span>
                <span className="text-slate-400">({memberPcts[i]}%)</span>
              </div>
            ))}
          </div>

          {/* Contribution bar */}
          <div className="flex h-3 rounded-full overflow-hidden mx-auto max-w-md">
            <div
              className="transition-all"
              style={{ width: `${memberPcts[0]}%`, backgroundColor: "#3B82F6" }}
            />
            <div
              className="transition-all"
              style={{ width: `${memberPcts[1]}%`, backgroundColor: "#EC4899" }}
            />
          </div>
        </CardContent>
      </Card>

      {/* 2. Month Selector */}
      <div>
        <select
          value={selectedMonth ?? ""}
          onChange={(e) => setSelectedMonth(e.target.value || undefined)}
          className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Mes actual</option>
          {monthOptions.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* 3. Category Breakdown Table */}
      <Card className="bg-white">
        <CardContent className="py-5">
          <h3 className="text-sm font-semibold text-luka-dark mb-4">Desglose por categoria</h3>

          {loadingBreakdown ? (
            <p className="text-sm text-luka-muted">Cargando...</p>
          ) : breakdown.length === 0 ? (
            <p className="text-sm text-luka-muted">Sin gastos compartidos este mes.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left py-2 pr-4 font-medium text-slate-500">Categoria</th>
                    <th className="text-right py-2 px-4 font-medium text-slate-500">{memberNames[0]}</th>
                    <th className="text-right py-2 px-4 font-medium text-slate-500">{memberNames[1]}</th>
                    <th className="text-right py-2 pl-4 font-medium text-slate-500">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row) => {
                    const m0 = row.member_totals[0];
                    const m1 = row.member_totals[1];
                    const m0pct = m0 ? m0.pct : 0;
                    const m1pct = m1 ? m1.pct : 0;
                    return (
                      <tr key={row.category} className="border-b border-slate-50">
                        {/* Category cell */}
                        <td className="py-3 pr-4">
                          <div className="font-medium text-slate-700">{row.category}</div>
                          <div className="flex h-1 rounded-full overflow-hidden mt-1 max-w-[120px]">
                            <div style={{ width: `${m0pct}%`, backgroundColor: "#3B82F6" }} />
                            <div style={{ width: `${m1pct}%`, backgroundColor: "#EC4899" }} />
                          </div>
                        </td>
                        {/* Member 1 */}
                        <td className="text-right py-3 px-4">
                          <div className="font-medium text-slate-700">{fmt(m0?.amount ?? 0)}</div>
                          <div className="text-xs text-slate-400">{m0pct}%</div>
                        </td>
                        {/* Member 2 */}
                        <td className="text-right py-3 px-4">
                          <div className="font-medium text-slate-700">{fmt(m1?.amount ?? 0)}</div>
                          <div className="text-xs text-slate-400">{m1pct}%</div>
                        </td>
                        {/* Total */}
                        <td className="text-right py-3 pl-4">
                          <div className="font-bold text-slate-800">{fmt(row.total)}</div>
                          <div className="text-xs text-slate-400">{row.pct_of_overall}%</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                {/* Footer totals */}
                <tfoot>
                  <tr className="border-t-2 border-slate-200">
                    <td className="py-3 pr-4 font-bold text-slate-800">Total</td>
                    <td className="text-right py-3 px-4 font-bold" style={{ color: "#3B82F6" }}>
                      {fmt(breakdownTotalByMember[0])}
                    </td>
                    <td className="text-right py-3 px-4 font-bold" style={{ color: "#EC4899" }}>
                      {fmt(breakdownTotalByMember[1])}
                    </td>
                    <td className="text-right py-3 pl-4 font-bold text-slate-800">
                      {fmt(breakdownGrandTotal)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 4. Settlement Card */}
      {!loadingSettlement && settlement && (
        <div
          className="rounded-xl p-5 text-white relative"
          style={{ background: "linear-gradient(135deg, #1E40AF, #2563EB)" }}
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-blue-200">
                Para equilibrar ({ratio[0]}/{ratio[1]})
              </p>
              {settlement.amount === 0 ? (
                <p className="text-lg font-semibold">Estan equilibrados</p>
              ) : (
                <p className="text-sm font-medium text-blue-100">
                  {settlement.from_user_name} debe transferir a {settlement.to_user_name}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {settlement.amount > 0 && (
                <p className="text-2xl font-bold">{fmt(settlement.amount)}</p>
              )}
              <button
                onClick={() => setSplitModalOpen(true)}
                className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                title="Editar split"
              >
                <Pencil size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Split Ratio Modal */}
      <SplitRatioModal
        open={splitModalOpen}
        onOpenChange={setSplitModalOpen}
        currentRatio={ratio}
        memberNames={memberNames}
      />
    </div>
  );
}
