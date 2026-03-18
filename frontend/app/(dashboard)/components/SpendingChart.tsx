"use client";
import { useId } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";

interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
}

const CLP = (v: number) => `$${(v / 1000).toFixed(0)}k`;

export function SpendingChart({ data }: SpendingChartProps) {
  const uid          = useId().replace(/:/g, "");
  const personalId   = `personal-${uid}`;
  const compartidoId = `compartido-${uid}`;

  if (data.length === 0) {
    return (
      <div className="h-[200px] flex flex-col items-center justify-center gap-2">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
          <span className="text-xl">📈</span>
        </div>
        <p className="text-xs text-slate-400">Sin datos de tendencia aún</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
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
        <YAxis tickFormatter={CLP} tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} width={36} />
        <Tooltip
          contentStyle={{ borderRadius: "12px", border: "1px solid #E2E8F0", fontSize: 12 }}
          formatter={(v) => [`$${Number(v).toLocaleString("es-CL")}`, ""]}
        />
        <Area type="monotone" dataKey="personal"   name="Personal"    stroke="#2563EB" fill={`url(#${personalId})`}   strokeWidth={2} dot={false} />
        <Area type="monotone" dataKey="compartido" name="Compartido"  stroke="#38BDF8" fill={`url(#${compartidoId})`} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
