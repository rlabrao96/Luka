"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";
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
 * Auto-detected chip on settle suggestions is Phase 7.7 (notifications).
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
                <button
                  type="button"
                  onClick={() => openFromSuggestion(s)}
                  className="text-[11px] font-semibold text-luka-primary hover:underline shrink-0"
                >
                  Marcar como pagado
                </button>
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
