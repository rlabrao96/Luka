"use client";

import type { TripBalance, TripSettlement } from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";

const ZERO_THRESHOLD = 0.005;

export function Avatar({ name, muted = false }: { name: string; muted?: boolean }) {
  const letter = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      className={
        "h-7 w-7 shrink-0 rounded-full flex items-center justify-center text-[11px] font-semibold " +
        (muted ? "bg-slate-100 text-slate-400" : "bg-blue-50 text-blue-700")
      }
    >
      {letter}
    </div>
  );
}

export function BalanceRow({
  balance,
  leftAt,
  isMe,
  currency,
}: {
  balance: TripBalance;
  leftAt: string | null;
  isMe: boolean;
  currency: string;
}) {
  const net = Number(balance.net_in_base);
  const isZero = Math.abs(net) < ZERO_THRESHOLD;
  const isCreditor = !isZero && net > 0;
  const isDebtor = !isZero && net < 0;
  const hasLeft = leftAt !== null;

  let label: string;
  let className: string;
  if (isZero) {
    label = "Saldo $0";
    className = "text-slate-400";
  } else if (isCreditor) {
    label = isMe
      ? `Te deben ${formatMajorAmount(net, currency)}`
      : `+${formatMajorAmount(net, currency)}`;
    className = "text-emerald-600";
  } else {
    label = isMe
      ? `Debes ${formatMajorAmount(Math.abs(net), currency)}`
      : `−${formatMajorAmount(Math.abs(net), currency)}`;
    className = "text-red-600";
  }

  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="flex items-center gap-2 min-w-0">
        <Avatar name={balance.attendee_display_name ?? "?"} muted={hasLeft} />
        <div className="min-w-0">
          <p
            className={
              "text-sm truncate " +
              (hasLeft
                ? "text-slate-400 line-through"
                : "text-luka-dark font-medium")
            }
          >
            {balance.attendee_display_name ?? "—"}
            {isMe && !hasLeft && (
              <span className="text-slate-400 font-normal"> (yo)</span>
            )}
          </p>
          {hasLeft && (
            <span className="inline-block mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">
              Salió
            </span>
          )}
        </div>
      </div>
      <p
        className={`text-sm font-semibold tabular-nums shrink-0 ${className} ${
          hasLeft && (isCreditor || isDebtor) ? "opacity-70" : ""
        }`}
      >
        {label}
      </p>
    </li>
  );
}

export function SettlementRow({
  settlement,
  fromName,
  toName,
}: {
  settlement: TripSettlement;
  fromName: string;
  toName: string;
}) {
  const date = new Date(settlement.settled_at);
  const dateStr = date.toLocaleDateString("es", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return (
    <li className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm text-luka-dark min-w-0 truncate">
          <span className="font-medium">{fromName}</span>
          <span className="text-slate-500"> pagó </span>
          <span className="font-semibold tabular-nums">
            {formatMajorAmount(Number(settlement.amount), settlement.currency)}
          </span>
          <span className="text-slate-500"> a </span>
          <span className="font-medium">{toName}</span>
        </p>
        <p className="text-[11px] text-slate-400 mt-0.5">{dateStr}</p>
      </div>
      {settlement.write_off && (
        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 bg-slate-100 rounded px-1.5 py-0.5 shrink-0">
          Ajuste
        </span>
      )}
    </li>
  );
}
