"use client";

import Link from "next/link";
import { Archive } from "lucide-react";
import type { Trip } from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";
import { formatTripDateRange } from "@/app/lib/months";

interface TripCardProps {
  trip: Trip;
}

/**
 * Compact list-row card for a trip. Shows name + dates + the caller's net
 * balance ("Te deben" / "Debes" / "Sin saldo") in the trip's base currency.
 *
 * Decimal fields (your_net_balance) cross the wire as strings — Number(...)
 * before doing arithmetic. Zero-saldo tolerance is ±$0.01 to match the
 * server's smart-settle epsilon.
 */
export default function TripCard({ trip }: TripCardProps) {
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

  const isArchived = trip.status === "archived";

  return (
    <Link
      href={`/viajes/${trip.id}`}
      className="block rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-[var(--shadow-card)] transition-all hover:border-luka-primary hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-semibold text-luka-dark truncate">
              {trip.name}
            </p>
            {isArchived && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                <Archive size={10} />
                Archivado
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {formatTripDateRange(trip.start_date, trip.end_date)}
          </p>
        </div>
        <p className={`text-sm font-semibold tabular-nums shrink-0 ${balanceClass}`}>
          {balanceLabel}
        </p>
      </div>
    </Link>
  );
}
