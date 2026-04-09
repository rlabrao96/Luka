"use client";
import { useId, useMemo } from "react";
import { TrendingUp } from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";

interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
  currency?: string;
}

export function SpendingChart({ data, currency = "CLP" }: SpendingChartProps) {
  const uid          = useId().replace(/:/g, "");
  const personalId   = `personal-${uid}`;
  const compartidoId = `compartido-${uid}`;

  // USD is stored in cents throughout the DB (Plaid convention); normalize
  // to whole dollars before the chart ever sees the values so the Area
  // heights, Y-axis ticks, and tooltip all agree.
  const normalized = useMemo(() => {
    if (currency !== "USD") return data;
    return data.map((d) => ({
      ...d,
      personal: d.personal / 100,
      compartido: d.compartido / 100,
    }));
  }, [data, currency]);

  // Compact axis labels that handle negatives cleanly. Recharts calls this
  // with the raw (already-normalized) numeric value per tick.
  const fmtAxis = (v: number) => {
    const sign = v < 0 ? "-" : "";
    const n = Math.abs(v);
    const prefix = currency === "USD" ? "US$" : "$";
    if (n >= 1_000_000) return `${sign}${prefix}${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${sign}${prefix}${Math.round(n / 1000)}k`;
    return `${sign}${prefix}${Math.round(n)}`;
  };

  const fmtTooltip = (v: number) => {
    if (currency === "USD") {
      return `US$${v.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    }
    return `$${Math.round(v).toLocaleString("es-CL")}`;
  };

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
