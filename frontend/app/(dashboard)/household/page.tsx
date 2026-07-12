"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
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
import { CurrencyToggle } from "@/app/(dashboard)/components/CurrencyToggle";
import { formatStoredAmount } from "@/app/lib/currency";
import { usePrimaryCurrency } from "@/app/lib/hooks/useCurrencies";
import RatioSettingsModal from "./RatioSettingsModal";
import InviteModal from "./InviteModal";
import MemberCard from "./MemberCard";
import { EquityReport } from "./EquityReport";
import { useLeaveHousehold } from "@/app/lib/hooks/useHousehold";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { localeForCurrency } from "@/app/lib/locale";
import { MonthSelector } from "../components/MonthSelector";
import { PageHeader } from "../components/PageHeader";
import { currentMonthKey, getLastNMonths } from "@/app/lib/months";

function fmt(n: number, currency: string = "CLP") {
  const formatted = formatStoredAmount(n, currency);
  return n < 0 ? `(${formatted})` : formatted;
}

const MEMBER_COLORS = ["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6"];

export default function CompartidoPage() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const nowKey = currentMonthKey();
  const [selectedMonth, setSelectedMonth] = useState<string>(nowKey);
  const [ratioModalOpen, setRatioModalOpen] = useState(false);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [justJoined, setJustJoined] = useState(false);
  const leaveHousehold = useLeaveHousehold();
  const router = useRouter();

  // Confirmation banner after accepting an invite (flag set on the invite page).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (sessionStorage.getItem("luka_joined_group")) {
      sessionStorage.removeItem("luka_joined_group");
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time on-mount read of sessionStorage (unavailable during SSR render)
      setJustJoined(true);
      const t = setTimeout(() => setJustJoined(false), 6000);
      return () => clearTimeout(t);
    }
  }, []);
  const primaryCurrency = usePrimaryCurrency();
  const [currency, setCurrency] = useState("");

  const { data: summary = [], isLoading: loadingSummary } = useHouseholdSummary(currency);
  const { data: breakdown = [], isLoading: loadingBreakdown } = useCategoryBreakdown(selectedMonth, currency);
  const { data: settlement } = useSettlement(selectedMonth, currency);
  const { data: splitRatio } = useSplitRatio();
  const { data: membersData } = useHouseholdMembers();

  const locale = localeForCurrency(currency);
  const monthOptions = getLastNMonths(locale, 12, { month: "long", year: "numeric" });
  const displayMonth =
    monthOptions.find((m) => m.key === selectedMonth)?.label ?? selectedMonth;

  useEffect(() => {
    if (!currency && primaryCurrency) setCurrency(primaryCurrency);
  }, [primaryCurrency, currency]);

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

  // Build amount lookup from summary (members with transactions)
  const summaryByUser: Record<string, { shared_paid: number }> = {};
  for (const s of summary) summaryByUser[s.user_id] = { shared_paid: s.shared_paid };

  const breakdownTotalByMember: Record<string, number> = {};
  let breakdownGrandTotal = 0;
  for (const row of breakdown) {
    breakdownGrandTotal += row.total;
    for (const mt of row.member_totals) {
      breakdownTotalByMember[mt.user_id] = (breakdownTotalByMember[mt.user_id] ?? 0) + mt.amount;
    }
  }

  // Use members (from membership data) as source of truth — not summary (transaction data)
  // Members with 0 transactions still appear
  const memberOrder = members.map((m) => m.user_id);
  const memberNameMap: Record<string, string> = {};
  for (const m of members) memberNameMap[m.user_id] = m.full_name;

  if (loadingSummary) {
    return (
      <div className="space-y-6">
        <PageHeader title="Compartido" subtitle="Gastos compartidos y balance del grupo" />
        <p className="text-sm text-luka-muted">Cargando...</p>
      </div>
    );
  }

  // Show empty state if no household, or solo with no pending invites
  if (!householdId || (members.length <= 1 && pendingInvites.length === 0)) {
    return (
      <div className="space-y-6">
        <PageHeader title="Compartido" subtitle="Gastos compartidos y balance del grupo" />
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
      {justJoined && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
          <span aria-hidden="true">🎉</span>
          ¡Te uniste al grupo! Ahora comparten gastos en Luka.
        </div>
      )}
      <PageHeader
        title="Compartido"
        subtitle="Gastos compartidos y balance del grupo"
        controls={
          <>
            {currency && <CurrencyToggle value={currency} onChange={setCurrency} />}
            <MonthSelector
              value={selectedMonth}
              onChange={setSelectedMonth}
              currentMonth={nowKey}
              currency={currency || undefined}
              size="md"
            />
          </>
        }
        actions={
          !settlementEnabled ? (
            <button
              onClick={() => setRatioModalOpen(true)}
              aria-label="Configurar ratios"
              className="w-9 h-9 rounded-lg border border-slate-200 bg-white hover:border-luka-primary hover:-translate-y-px transition-all shadow-[var(--shadow-card)] flex items-center justify-center"
            >
              <Settings size={16} className="text-slate-700" />
            </button>
          ) : undefined
        }
      />

      {/* Member cards — rendered from members (membership), not summary (transactions).
           "Agregar miembro" lives at the END of the carousel as a dashed add-card —
           contextual to the members it creates, and keeps the header free of big CTAs. */}
      <div className="flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory">
        {members.map((member, i) => {
          const amount = summaryByUser[member.user_id]?.shared_paid ?? 0;
          return (
            <MemberCard key={member.user_id} name={member.full_name} amount={amount}
              percentage={totalShared > 0 ? Math.round((amount / totalShared) * 100) : 0}
              color={MEMBER_COLORS[i % MEMBER_COLORS.length]} balance={memberBalances[member.user_id]}
              settlementEnabled={settlementEnabled} currency={currency} isOwner={isOwner}
              memberId={member.member_id}
              memberRole={member.role}
              isSelf={member.user_id === userId} />
          );
        })}
        {pendingInvites.map((invite) => (
          <div key={invite.id} className="flex-shrink-0 w-48 rounded-xl border-2 border-dashed border-slate-300 p-4 text-center opacity-50">
            <div className="w-9 h-9 rounded-full bg-slate-200 text-slate-400 flex items-center justify-center mx-auto mb-2 text-sm font-bold">?</div>
            <p className="text-xs font-medium text-slate-400 truncate">{invite.invited_email ?? "Invitación pendiente"}</p>
            <p className="text-xs text-slate-400 mt-1">⏳ Pendiente</p>
          </div>
        ))}
        {isOwner && members.length + pendingInvites.length < 5 && (
          <button
            type="button"
            onClick={() => setInviteModalOpen(true)}
            className="flex-shrink-0 w-48 rounded-xl border-2 border-dashed border-luka-primary/30 hover:border-luka-primary hover:bg-luka-primary/5 transition-colors p-4 flex flex-col items-center justify-center gap-2 text-luka-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
            aria-label="Agregar miembro"
          >
            <div className="w-9 h-9 rounded-full bg-luka-primary/10 flex items-center justify-center">
              <UserPlus size={18} />
            </div>
            <p className="text-xs font-semibold">Agregar miembro</p>
          </button>
        )}
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
            <>
              {/* Mobile: stacked cards — avoids nested horizontal scroll */}
              <div className="sm:hidden space-y-3">
                {breakdown.map((row) => {
                  const mtMap: Record<string, { amount: number; pct: number }> = {};
                  for (const mt of row.member_totals) mtMap[mt.user_id] = { amount: mt.amount, pct: mt.pct };
                  return (
                    <div key={row.category} className="rounded-lg border border-slate-100 p-3 bg-white">
                      <div className="flex items-baseline justify-between gap-2 mb-2">
                        <p className="font-semibold text-slate-700 text-sm truncate">{row.category}</p>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-bold text-slate-800 tabular-nums">{fmt(row.total, currency)}</p>
                          <p className="text-[10px] text-slate-400">{row.pct_of_overall}% del total</p>
                        </div>
                      </div>
                      <div className="flex h-1 rounded-full overflow-hidden mb-2">
                        {memberOrder.map((uid, i) => (
                          <div key={uid} style={{ width: `${mtMap[uid]?.pct ?? 0}%`, backgroundColor: MEMBER_COLORS[i % MEMBER_COLORS.length] }} />
                        ))}
                      </div>
                      <div className="space-y-1">
                        {memberOrder.map((uid, i) => (
                          <div key={uid} className="flex items-center justify-between text-xs">
                            <span className="flex items-center gap-1.5 text-slate-600">
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: MEMBER_COLORS[i % MEMBER_COLORS.length] }} />
                              {memberNameMap[uid]?.split(" ")[0] ?? "Miembro"}
                            </span>
                            <span className="tabular-nums">
                              <span className="font-medium text-slate-700">{fmt(mtMap[uid]?.amount ?? 0, currency)}</span>
                              <span className="text-slate-400 ml-1">({mtMap[uid]?.pct ?? 0}%)</span>
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
                <div className="rounded-lg border-2 border-slate-200 p-3 bg-slate-50">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Total</p>
                  {memberOrder.map((uid, i) => (
                    <div key={uid} className="flex justify-between text-xs py-0.5">
                      <span style={{ color: MEMBER_COLORS[i % MEMBER_COLORS.length] }} className="font-semibold">
                        {memberNameMap[uid]?.split(" ")[0] ?? "Miembro"}
                      </span>
                      <span className="font-bold tabular-nums">{fmt(breakdownTotalByMember[uid] ?? 0, currency)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-sm mt-2 pt-2 border-t border-slate-200">
                    <span className="font-bold text-slate-700">Total</span>
                    <span className="font-bold text-slate-800 tabular-nums">{fmt(breakdownGrandTotal, currency)}</span>
                  </div>
                </div>
              </div>

              {/* Desktop: table layout */}
              <div className="hidden sm:block overflow-x-auto">
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
            </>
          )}
        </CardContent>
      </Card>

      {currency && <EquityReport currency={currency} />}

      {members.length > 1 && (
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setLeaveOpen(true)}
            className="text-xs font-medium text-red-500 hover:text-red-600 hover:underline"
          >
            Salir del grupo
          </button>
        </div>
      )}

      <AlertDialog open={leaveOpen} onOpenChange={setLeaveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Salir del grupo?</AlertDialogTitle>
            <AlertDialogDescription>
              Volverás a tener una cuenta individual. Tus cuentas bancarias
              vinculadas a este grupo se desactivarán.
              {isOwner
                ? " Como eres administrador, promoveremos al miembro más antiguo para que el grupo siga teniendo uno."
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={leaveHousehold.isPending}
              onClick={() => {
                leaveHousehold.mutate(undefined, {
                  onSuccess: () => {
                    setLeaveOpen(false);
                    router.push("/");
                  },
                  onError: () => setLeaveOpen(false),
                });
              }}
              className="bg-red-500 hover:bg-red-600 text-white"
            >
              {leaveHousehold.isPending ? "Saliendo…" : "Salir"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Modals */}
      <RatioSettingsModal open={ratioModalOpen} onOpenChange={setRatioModalOpen}
        currentRatio={ratio} members={members} settlementEnabled={settlementEnabled} />
      <InviteModal open={inviteModalOpen} onOpenChange={setInviteModalOpen} householdId={householdId} />
    </div>
  );
}
