"use client";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface SpendingChartProps {
  data: Array<{ month: string; personal: number; compartido: number }>;
}

const CLP = (v: number) => `$${(v / 1000).toFixed(0)}k`;

export function SpendingChart({ data }: SpendingChartProps) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="personal" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2563EB" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="compartido" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#38BDF8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={CLP} tick={{ fontSize: 11 }} width={40} />
        <Tooltip formatter={(v) => [`$${Number(v).toLocaleString("es-CL")}`, ""]} />
        <Legend />
        <Area type="monotone" dataKey="personal" name="Personal" stroke="#2563EB" fill="url(#personal)" strokeWidth={2} />
        <Area type="monotone" dataKey="compartido" name="Compartido" stroke="#38BDF8" fill="url(#compartido)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
