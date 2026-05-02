"use client";

import Link from "next/link";
import { ArrowLeft, Archive } from "lucide-react";
import type { TripDetail } from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";
import { formatTripDateRange } from "@/app/lib/months";

interface TripHeaderProps {
  trip: TripDetail;
}

/**
 * Header for the trip detail page. Shows the trip name, dates, base currency
 * badge, archived chip, and the caller's net balance (color-coded the same way
 * as TripCard so the metric stays consistent across list + detail).
 */
export default function TripHeader({ trip }: TripHeaderProps) {
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
    <header className="space-y-3">
      <Link
        href="/viajes"
        className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-luka-primary transition-colors"
      >
        <ArrowLeft size={14} />
        Viajes
      </Link>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-luka-dark tracking-tight truncate">
              {trip.name}
            </h1>
            {isArchived && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                <Archive size={10} />
                Archivado
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <p className="text-sm text-slate-500">
              {formatTripDateRange(trip.start_date, trip.end_date)}
            </p>
            <span className="inline-flex items-center text-[10px] font-semibold uppercase tracking-wide text-slate-600 bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded">
              {trip.base_currency}
            </span>
          </div>
        </div>
        <p className={`text-sm font-semibold tabular-nums shrink-0 ${balanceClass}`}>
          {balanceLabel}
        </p>
      </div>
    </header>
  );
}
