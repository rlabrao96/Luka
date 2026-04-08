"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings, UserPlus } from "lucide-react";
import {
  useHouseholdSummary,
  useCategoryBreakdown,
  useSettlement,
  useSplitRatio,
  useHouseholdMembers,
} from "@/app/lib/hooks/useHousehold";
import { useLukaStore } from "@/app/lib/store";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import RatioSettingsModal from "./RatioSettingsModal";
import InviteModal from "./InviteModal";
import MemberCard from "./MemberCard";

function fmt(n: number, currency: string = "CLP") {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? Math.abs(n) / 100 : Math.abs(n);
  const formatted = currency === "USD"
    ? `US$${displayVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `$${Math.round(displayVal).toLocaleString("es-CL")}`;
  return n < 0 ? `(${formatted})` : formatted;
}

const MONTH_NAMES = [
  "Enero","Febrero","Marzo","Abril","Mayo","Junio",
  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
];

function getLast6Months() {
  const now = new Date();
  const months: { value: string; label: string }[] = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`,
    });
  }
  return months;
}

const MEMBER_COLORS = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6"];

export default function CompartidoPage() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const [selectedMonth, setSelectedMonth] = useState<string | undefined>();
  const [ratioModalOpen, setRatioModalOpen] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [currency, setCurrency] = useState("CLP");

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.getMe });
  const { data: summary = [], isLoading: loadingSummary } = useHouseholdSummary(currency);
  const { data: breakdown = [], isLoading: loadingBreakdown } = useCategoryBreakdown(selectedMonth, currency);
  const { data: settlement } = useSettlement(selectedMonth, currency);
  const { data: splitRatio } = useSplitRatio();
  const { data: membersData } = useHouseholdMembers();

  const monthOptions = getLast6Months();
  const now = new Date();
  const displayMonth = selectedMonth
    ? monthOptions.find((m) => m.value === selectedMonth)?.label ?? selectedMonth
    : `${MONTH_NAMES[now.getMonth()]} ${now.getFullYear()}`;

  const preferredCurrency = me?.preferred_currency;
  useEffect(() => { if (preferredCurrency) setCurrency(preferredCurrency); }, [preferredCurrency]);

  const ratio = splitRatio?.split_ratio ?? [];
  const members = membersData?.members ?? [];
  const pendingInvites = membersData?.pending_invites ?? [];
  const isOwner = members.some((m) => m.user_id === userId && m.role === "owner");
  const settlementEnabled = settlement?.settlement_enabled ?? true;

  const memberBalances = useMemo(() => {
    const balances: Record<string, number> = {};
    if (!settlement?.transfers) return balances;
    for (const t of settlement.transfers) {
      balances[t.from_user_id] = (balances[t.from_user_id] ?? 0) - t.amount;
      balances[t.to_user_id] = (balances[t.to_user_id] ?? 0) + t.amount;
    }
    return balances;
  }, [settlement]);

  const totalShared = summary.reduce((sum, r) => sum + r.shared_paid, 0);

  const breakdownTotalByMember: Record<string, number> = {};
  let breakdownGrandTotal = 0;
  for (const row of breakdown) {
    breakdownGrandTotal += row.total;
    for (const mt of row.member_totals) {
      breakdownTotalByMember[mt.user_id] = (breakdownTotalByMember[mt.user_id] ?? 0) + mt.amount;
    }
  }

  const memberOrder = summary.map((s) => s.user_id);
  const memberNameMap: Record<string, string> = {};
  for (const s of summary) memberNameMap[s.user_id] = s.full_name;

  if (loadingSummary) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <p className="text-sm text-luka-muted">Cargando...</p>
      </div>
    );
  }

  // Show empty state if no household, or solo with no pending invites
  if (!householdId || (members.length <= 1 && pendingInvites.length === 0)) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <Card className="bg-white">
          <CardContent className="py-16 text-center space-y-4">
            <p className="text-sm text-luka-muted">No tienes un grupo compartido</p>
            <Button onClick={() => setInviteModalOpen(true)} className="bg-luka-primary hover:bg-blue-700">
              <UserPlus size={16} className="mr-2" />
              Agregar mi primer miembro
            </Button>
          </CardContent>
        </Card>
        <InviteModal open={inviteModalOpen} onOpenChange={setInviteModalOpen} householdId={householdId} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Compartido</h2>
          <p className="text-sm text-luka-muted mt-0.5">Gastos compartidos y balance del grupo</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={selectedMonth ?? ""} onChange={(e) => setSelectedMonth(e.target.value || undefined)}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Mes actual</option>
            {monthOptions.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <CurrencyToggle value={currency} onChange={setCurrency} />
          {!settlementEnabled && (
            <button onClick={() => setRatioModalOpen(true)}
              className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors" title="Configurar ratios">
              <Settings size={16} />
            </button>
          )}
          {isOwner && members.length < 5 && (
            <Button onClick={() => setInviteModalOpen(true)} size="sm" className="bg-luka-primary hover:bg-blue-700">
              <UserPlus size={14} className="mr-1.5" /> Agregar miembro
            </Button>
          )}
        </div>
      </div>

      {/* Member cards */}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {summary.map((member, i) => (
          <MemberCard key={member.user_id} name={member.full_name} amount={member.shared_paid}
            percentage={totalShared > 0 ? Math.round((member.shared_paid / totalShared) * 100) : 0}
            color={MEMBER_COLORS[i % MEMBER_COLORS.length]} balance={memberBalances[member.user_id]}
            settlementEnabled={settlementEnabled} currency={currency} isOwner={isOwner}
            memberId={members.find((m) => m.user_id === member.user_id)?.member_id}
            memberRole={members.find((m) => m.user_id === member.user_id)?.role}
            isSelf={member.user_id === userId} />
        ))}
        {pendingInvites.map((invite) => (
          <div key={invite.id} className="flex-shrink-0 w-48 rounded-xl border-2 border-dashed border-slate-300 p-4 text-center opacity-50">
            <div className="w-9 h-9 rounded-full bg-slate-200 text-slate-400 flex items-center justify-center mx-auto mb-2 text-sm font-bold">?</div>
            <p className="text-xs font-medium text-slate-400 truncate">{invite.invited_email ?? "Invitación pendiente"}</p>
            <p className="text-xs text-slate-400 mt-1">⏳ Pendiente</p>
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm px-5 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-luka-primary">Total compartido — {displayMonth}</p>
        <p className="text-2xl font-bold text-luka-dark">{fmt(totalShared, currency)}</p>
      </div>

      {/* Settlement */}
      {settlementEnabled && settlement && settlement.transfers.length > 0 && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-blue-900">Transferencias sugeridas</h3>
            <button onClick={() => setRatioModalOpen(true)}
              className="text-xs text-luka-primary font-medium border border-blue-300 rounded-lg px-3 py-1 hover:bg-blue-100 transition-colors">
              ⚙ Ratios ({ratio.join("/")})
            </button>
          </div>
          {settlement.transfers.map((t, i) => (
            <div key={i} className="bg-white rounded-lg px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-xs font-bold">{t.from_user_name.charAt(0)}</span>
                <span>{t.from_user_name}</span>
                <span className="text-slate-400">→</span>
                <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center text-xs font-bold">{t.to_user_name.charAt(0)}</span>
                <span>{t.to_user_name}</span>
              </div>
              <span className="font-bold text-luka-dark">{fmt(t.amount, currency)}</span>
            </div>
          ))}
        </div>
      )}
      {settlementEnabled && settlement && settlement.transfers.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
          <p className="text-sm font-medium text-emerald-800">Están equilibrados ✓</p>
          <button onClick={() => setRatioModalOpen(true)}
            className="text-xs text-emerald-700 font-medium border border-emerald-300 rounded-lg px-3 py-1 hover:bg-emerald-100 transition-colors">
            ⚙ Ratios ({ratio.join("/")})
          </button>
        </div>
      )}

      {/* Category breakdown */}
      <Card className="bg-white">
        <CardContent className="py-5">
          <h3 className="text-sm font-semibold text-luka-dark mb-4">Desglose por categoría</h3>
          {loadingBreakdown ? (
            <p className="text-sm text-luka-muted">Cargando...</p>
          ) : breakdown.length === 0 ? (
            <p className="text-sm text-luka-muted">Sin gastos compartidos este mes.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left py-2 pr-4 font-medium text-slate-500">Categoría</th>
                    {memberOrder.map((uid) => (
                      <th key={uid} className="text-right py-2 px-4 font-medium text-slate-500">
                        {memberNameMap[uid]?.split(" ")[0] ?? "Miembro"}
                      </th>
                    ))}
                    <th className="text-right py-2 pl-4 font-medium text-slate-500">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row) => {
                    const mtMap: Record<string, { amount: number; pct: number }> = {};
                    for (const mt of row.member_totals) mtMap[mt.user_id] = { amount: mt.amount, pct: mt.pct };
                    return (
                      <tr key={row.category} className="border-b border-slate-50">
                        <td className="py-3 pr-4">
                          <div className="font-medium text-slate-700">{row.category}</div>
                          <div className="flex h-1 rounded-full overflow-hidden mt-1 max-w-[120px]">
                            {memberOrder.map((uid, i) => (
                              <div key={uid} style={{ width: `${mtMap[uid]?.pct ?? 0}%`, backgroundColor: MEMBER_COLORS[i % MEMBER_COLORS.length] }} />
                            ))}
                          </div>
                        </td>
                        {memberOrder.map((uid) => (
                          <td key={uid} className="text-right py-3 px-4">
                            <div className="font-medium text-slate-700">{fmt(mtMap[uid]?.amount ?? 0, currency)}</div>
                            <div className="text-xs text-slate-400">{mtMap[uid]?.pct ?? 0}%</div>
                          </td>
                        ))}
                        <td className="text-right py-3 pl-4">
                          <div className="font-bold text-slate-800">{fmt(row.total, currency)}</div>
                          <div className="text-xs text-slate-400">{row.pct_of_overall}%</div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-slate-200">
                    <td className="py-3 pr-4 font-bold text-slate-800">Total</td>
                    {memberOrder.map((uid, i) => (
                      <td key={uid} className="text-right py-3 px-4 font-bold" style={{ color: MEMBER_COLORS[i % MEMBER_COLORS.length] }}>
                        {fmt(breakdownTotalByMember[uid] ?? 0, currency)}
                      </td>
                    ))}
                    <td className="text-right py-3 pl-4 font-bold text-slate-800">{fmt(breakdownGrandTotal, currency)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <RatioSettingsModal open={ratioModalOpen} onOpenChange={setRatioModalOpen}
        currentRatio={ratio} members={members} settlementEnabled={settlementEnabled} />
      <InviteModal open={inviteModalOpen} onOpenChange={setInviteModalOpen} householdId={householdId} />
    </div>
  );
}
