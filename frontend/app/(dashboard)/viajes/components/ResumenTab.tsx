"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { TripDetail, TripSettleSuggestion } from "@/app/lib/api";
import { api } from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";
import MarkSettledDialog, {
  type MarkSettledPrefill,
} from "./MarkSettledDialog";
import TripSuggestionsBanner from "./TripSuggestionsBanner";

interface ResumenTabProps {
  trip: TripDetail;
}

/**
 * Resumen tab — totals + your share + your balance + top settle suggestions.
 *
 * Decimal fields cross the wire as strings; Number(...) before arithmetic.
 * Display name lookup goes through `attendees` so we can resolve
 * `from_attendee_id` / `to_attendee_id` on settle suggestions to a real name.
 */
export default function ResumenTab({ trip }: ResumenTabProps) {
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const myAttendeeId = useMemo(() => {
    if (!me) return null;
    const mine = trip.attendees.find((a) => a.user_id === me.id);
    return mine?.id ?? null;
  }, [me, trip.attendees]);

  const total = useMemo(
    () => trip.expenses.reduce((s, e) => s + Number(e.amount), 0),
    [trip.expenses],
  );

  const yourShare = useMemo(() => {
    if (!myAttendeeId) return 0;
    let sum = 0;
    for (const exp of trip.expenses) {
      for (const split of exp.splits) {
        if (split.attendee_id === myAttendeeId) {
          sum += Number(split.share_amount);
        }
      }
    }
    return sum;
  }, [trip.expenses, myAttendeeId]);

  const net = Number(trip.your_net_balance);
  const isZero = Math.abs(net) < 0.01;
  const isCreditor = !isZero && net > 0;
  let balanceLabel: string;
  let balanceClass: string;
  if (isZero) {
    balanceLabel = "Sin saldo";
    balanceClass = "text-slate-400";
  } else if (isCreditor) {
    balanceLabel = `Te deben ${formatMajorAmount(net, trip.base_currency)}`;
    balanceClass = "text-emerald-600";
  } else {
    balanceLabel = `Debes ${formatMajorAmount(net, trip.base_currency)}`;
    balanceClass = "text-red-600";
  }

  function nameOf(attendeeId: string): string {
    return (
      trip.attendees.find((a) => a.id === attendeeId)?.display_name ?? "—"
    );
  }

  const topSuggestions = trip.settle_suggestions.slice(0, 3);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [prefill, setPrefill] = useState<MarkSettledPrefill | undefined>();

  function openFromSuggestion(s: TripSettleSuggestion) {
    setPrefill({
      from_attendee_id: s.from_attendee_id,
      to_attendee_id: s.to_attendee_id,
      amount: Number(s.amount).toFixed(2),
      currency: s.currency,
    });
    setDialogOpen(true);
  }

  return (
    <div className="space-y-4">
      <TripSuggestionsBanner trip={trip} />
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <StatCard
          label="Total gastado"
          value={formatMajorAmount(total, trip.base_currency)}
        />
        <StatCard
          label="Tu parte"
          value={formatMajorAmount(yourShare, trip.base_currency)}
        />
        <StatCard label="Tu saldo" value={balanceLabel} valueClass={balanceClass} />
      </div>

      {/* Settle suggestions */}
      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-100">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Sugerencias para saldar
          </p>
        </div>
        {topSuggestions.length === 0 ? (
          <p className="text-xs text-slate-400 px-4 py-6 text-center">
            Todo está saldado.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {topSuggestions.map((s, idx) => (
              <li
                key={`${s.from_attendee_id}-${s.to_attendee_id}-${idx}`}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <p className="text-sm text-luka-dark min-w-0 truncate">
                  <span className="font-medium">{nameOf(s.from_attendee_id)}</span>
                  <span className="text-slate-500"> paga a </span>
                  <span className="font-medium">{nameOf(s.to_attendee_id)}</span>
                  <span className="text-slate-500"> · </span>
                  <span className="font-semibold tabular-nums">
                    {formatMajorAmount(Number(s.amount), s.currency)}
                  </span>
                </p>
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

function StatCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
        {label}
      </p>
      <p
        className={`text-lg font-semibold tabular-nums mt-1 ${valueClass ?? "text-luka-dark"}`}
      >
        {value}
      </p>
    </div>
  );
}
