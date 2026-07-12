"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Plus, Sparkles } from "lucide-react";
import {
  api,
  type TripDetail,
  type TripSettleSuggestion,
} from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";
import MarkSettledDialog, {
  type MarkSettledPrefill,
} from "./MarkSettledDialog";
import { Avatar, BalanceRow, SettlementRow } from "./SaldosRows";
import { useNotifications } from "@/app/lib/hooks/useNotifications";
import { useConfirmSettlementSuggestion } from "@/app/lib/hooks/useTrips";

interface SaldosTabProps {
  trip: TripDetail;
}

/**
 * Saldos tab — three sections:
 *   A) Balance grid per attendee (sorted creditors → debtors)
 *   B) Plan de pago (smart-settle suggestions) + ad-hoc "Registrar pago"
 *   C) Movimientos (settlement history)
 *
 * Decimal fields cross the wire as strings; Number(...) for math.
 * Auto-detected chips: settle-suggestion rows that match a
 * trip_settlement_suggestion notification (a real transaction the backend
 * detected) get a one-tap 'Auto-detectado' confirm using the linked txn.
 */
export default function SaldosTab({ trip }: SaldosTabProps) {
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const myAttendeeId = useMemo(() => {
    if (!me) return null;
    return trip.attendees.find((a) => a.user_id === me.id)?.id ?? null;
  }, [me, trip.attendees]);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [prefill, setPrefill] = useState<MarkSettledPrefill | undefined>();
  const { data: notifications = [] } = useNotifications();
  const confirmSuggestion = useConfirmSettlementSuggestion();

  // Auto-detected settlements: unactioned trip_settlement_suggestion
  // notifications for THIS trip, keyed by from→to so we can attach a one-tap
  // confirm chip to the matching smart-settle row.
  const autoDetected = useMemo(() => {
    const map = new Map<string, { transaction_id: string; amount: string; currency: string }>();
    for (const n of notifications) {
      if (n.type !== "trip_settlement_suggestion") continue;
      if (n.status === "actioned" || n.status === "dismissed") continue;
      const p = n.payload as unknown as {
        trip_id?: string;
        from_attendee_id?: string;
        to_attendee_id?: string;
        transaction_id?: string;
        suggested_amount?: string;
        currency?: string;
      } | null;
      if (!p || p.trip_id !== trip.id || !p.transaction_id) continue;
      map.set(`${p.from_attendee_id}-${p.to_attendee_id}`, {
        transaction_id: p.transaction_id,
        amount: p.suggested_amount ?? "0",
        currency: p.currency ?? trip.base_currency,
      });
    }
    return map;
  }, [notifications, trip.id, trip.base_currency]);

  function nameOf(attendeeId: string): string {
    return (
      trip.attendees.find((a) => a.id === attendeeId)?.display_name ?? "—"
    );
  }

  function leftAtOf(attendeeId: string): string | null {
    return trip.attendees.find((a) => a.id === attendeeId)?.left_at ?? null;
  }

  function openAdHoc() {
    setPrefill(undefined);
    setDialogOpen(true);
  }

  function openFromSuggestion(s: TripSettleSuggestion) {
    setPrefill({
      from_attendee_id: s.from_attendee_id,
      to_attendee_id: s.to_attendee_id,
      amount: Number(s.amount).toFixed(2),
      currency: s.currency,
    });
    setDialogOpen(true);
  }

  const sortedBalances = useMemo(
    () =>
      [...trip.balances].sort(
        (a, b) => Number(b.net_in_base) - Number(a.net_in_base),
      ),
    [trip.balances],
  );

  const sortedSettlements = useMemo(
    () =>
      [...trip.settlements].sort(
        (a, b) =>
          new Date(b.settled_at).getTime() - new Date(a.settled_at).getTime(),
      ),
    [trip.settlements],
  );

  return (
    <div className="space-y-4">
      {/* A) Balance grid */}
      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-100">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Saldos por persona
          </p>
        </div>
        {sortedBalances.length === 0 ? (
          <p className="text-xs text-slate-400 px-4 py-6 text-center">
            Aún no hay saldos para mostrar.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {sortedBalances.map((b) => (
              <BalanceRow
                key={b.attendee_id}
                balance={b}
                leftAt={leftAtOf(b.attendee_id)}
                isMe={b.attendee_id === myAttendeeId}
                currency={trip.base_currency}
              />
            ))}
          </ul>
        )}
      </section>

      {/* B) Plan de pago */}
      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Plan de pago
          </p>
          <button
            type="button"
            onClick={openAdHoc}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-luka-primary hover:underline"
          >
            <Plus size={12} />
            Registrar pago
          </button>
        </div>
        {trip.settle_suggestions.length === 0 ? (
          <div className="px-4 py-8 text-center space-y-1.5">
            <div className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
              <Check size={16} />
            </div>
            <p className="text-sm font-semibold text-luka-dark">
              Cuentas saldadas
            </p>
            <p className="text-xs text-slate-500">No hay deudas pendientes.</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {trip.settle_suggestions.map((s, idx) => (
              <li
                key={`${s.from_attendee_id}-${s.to_attendee_id}-${idx}`}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Avatar name={nameOf(s.from_attendee_id)} />
                  <span className="text-slate-400 text-xs">→</span>
                  <Avatar name={nameOf(s.to_attendee_id)} />
                  <p className="text-sm text-luka-dark min-w-0 truncate">
                    <span className="font-medium">
                      {nameOf(s.from_attendee_id)}
                    </span>
                    <span className="text-slate-500"> paga </span>
                    <span className="font-semibold tabular-nums">
                      {formatMajorAmount(Number(s.amount), s.currency)}
                    </span>
                    <span className="text-slate-500"> a </span>
                    <span className="font-medium">
                      {nameOf(s.to_attendee_id)}
                    </span>
                  </p>
                </div>
                {(() => {
                  const auto = autoDetected.get(
                    `${s.from_attendee_id}-${s.to_attendee_id}`,
                  );
                  if (auto) {
                    return (
                      <button
                        type="button"
                        disabled={confirmSuggestion.isPending}
                        onClick={() =>
                          confirmSuggestion.mutate({
                            trip_id: trip.id,
                            transaction_id: auto.transaction_id,
                            from_attendee_id: s.from_attendee_id,
                            to_attendee_id: s.to_attendee_id,
                            amount: auto.amount,
                            currency: auto.currency,
                          })
                        }
                        className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 shrink-0"
                        title="Detectamos una transacción que salda este pago"
                      >
                        <Sparkles size={12} />
                        Auto-detectado · Confirmar
                      </button>
                    );
                  }
                  return (
                    <button
                      type="button"
                      onClick={() => openFromSuggestion(s)}
                      className="text-[11px] font-semibold text-luka-primary hover:underline shrink-0"
                    >
                      Marcar como pagado
                    </button>
                  );
                })()}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* C) Movimientos */}
      {sortedSettlements.length > 0 && (
        <section className="rounded-xl border border-slate-200 bg-white">
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Movimientos
            </p>
          </div>
          <ul className="divide-y divide-slate-100">
            {sortedSettlements.map((s) => (
              <SettlementRow
                key={s.id}
                settlement={s}
                fromName={nameOf(s.from_attendee_id)}
                toName={nameOf(s.to_attendee_id)}
              />
            ))}
          </ul>
        </section>
      )}

      <MarkSettledDialog
        tripId={trip.id}
        trip={trip}
        prefill={prefill}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  );
}
