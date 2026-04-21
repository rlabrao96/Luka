"use client";
import { useId, useMemo } from "react";
import { TrendingUp } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";
import { formatMajorAmount, formatMajorAmountCompact, isZeroDecimalCurrency } from "@/app/lib/currency";

interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
  currency?: string;
}

export function SpendingChart({ data, currency = "CLP" }: SpendingChartProps) {
  const uid          = useId().replace(/:/g, "");
  const personalId   = `personal-${uid}`;
  const compartidoId = `compartido-${uid}`;

  // Non-zero-decimal currencies are stored in minor units (cents);
  // normalize to major units before rendering so axes + tooltips agree.
  const normalized = useMemo(() => {
    if (isZeroDecimalCurrency(currency)) return data;
    return data.map((d) => ({
      ...d,
      personal: d.personal / 100,
      compartido: d.compartido / 100,
    }));
  }, [data, currency]);

  const fmtAxis = (v: number) => {
    const sign = v < 0 ? "-" : "";
    return `${sign}${formatMajorAmountCompact(Math.abs(v), currency)}`;
  };

  const fmtTooltip = (v: number) => formatMajorAmount(v, currency);

  if (normalized.length === 0) {
    return (
      <div className="h-full min-h-[140px] flex flex-col items-center justify-center gap-2">
        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
          <TrendingUp size={18} className="text-slate-400" />
        </div>
        <p className="text-xs text-slate-400">Sin datos de tendencia aún</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={normalized} margin={{ top: 4, right: 8, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id={personalId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#2563EB" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
          </linearGradient>
          <linearGradient id={compartidoId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#38BDF8" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#38BDF8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
        <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
        <YAxis
          tickFormatter={fmtAxis}
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          axisLine={false}
          tickLine={false}
          width={56}
        />
        <Tooltip
          contentStyle={{ borderRadius: "12px", border: "1px solid #E2E8F0", fontSize: 12 }}
          formatter={(v) => [fmtTooltip(Number(v)), ""]}
        />
        <Area type="monotone" dataKey="personal"   name="Personal"    stroke="#2563EB" fill={`url(#${personalId})`}   strokeWidth={2} dot={false} />
        <Area type="monotone" dataKey="compartido" name="Compartido"  stroke="#38BDF8" fill={`url(#${compartidoId})`} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
