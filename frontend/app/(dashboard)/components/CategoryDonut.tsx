"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { formatMajorAmount } from "@/app/lib/currency";

const COLORS = [
  "#2563EB", // blue — primary
  "#10B981", // emerald
  "#F59E0B", // amber
  "#8B5CF6", // violet
  "#EF4444", // red
  "#94A3B8", // slate — Otros
];

interface CategoryDonutProps {
  data: Array<{ category: string; amount: number }>;
  currency?: string;
}

export function CategoryDonut({ data, currency = "CLP" }: CategoryDonutProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  /** Amounts are pre-normalized to standard currency unit. */
  const fmtAmount = (v: number) => formatMajorAmount(Number(v), currency);

  // Recharts Pie requires positive values — use absolute amounts for rendering
  const chartData = data.map((d) => ({ ...d, amount: Math.abs(Number(d.amount)) }));
  const total = data.reduce((s, d) => s + Number(d.amount), 0);
  const absTotal = chartData.reduce((s, d) => s + d.amount, 0);
  const active = activeIndex !== null ? data[activeIndex] : null;

  return (
    <div className="flex flex-col gap-2">
      {/* Donut with fixed center total */}
      <div className="relative mt-2" style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="amount"
              nameKey="category"
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={85}
              paddingAngle={2}
              strokeWidth={0}
              onMouseEnter={(_, index) => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
            >
              {chartData.map((_, i) => (
                <Cell
                  key={i}
                  fill={COLORS[i % COLORS.length]}
                  opacity={activeIndex === null || activeIndex === i ? 1 : 0.35}
                  style={{ cursor: "pointer", transition: "opacity 0.2s ease" }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Center label — permanently shows total */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none pb-1">
          <p className="text-[9.5px] font-semibold uppercase tracking-widest text-slate-400 mb-0.5">
            Total
          </p>
          <p className="text-sm font-bold text-slate-800 tabular-nums leading-tight">
            {fmtAmount(total)}
          </p>
        </div>
      </div>

      {/* Hover info panel — appears below donut */}
      <div
        className={`rounded-lg px-3 py-2 border transition-all duration-150 ${
          active
            ? "bg-white border-slate-100 shadow-sm opacity-100"
            : "opacity-0 border-transparent pointer-events-none"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: active ? COLORS[activeIndex! % COLORS.length] : "transparent" }}
            />
            <span className="text-xs font-semibold text-slate-800 truncate">
              {active ? active.category : "Placeholder"}
            </span>
          </div>
          <div className="text-right shrink-0">
            <p className="text-xs font-bold text-slate-800 tabular-nums">
              {fmtAmount(active ? Number(active.amount) : 0)}
            </p>
            <p className="text-[10px] text-slate-400">
              {active ? ((Math.abs(Number(active.amount)) / absTotal) * 100).toFixed(1) : "0.0"}% del total
            </p>
          </div>
        </div>
      </div>

      {/* Custom legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-2 justify-center pb-2">
        {data.map((entry, i) => (
          <div
            key={entry.category}
            className="flex items-center gap-1.5 cursor-pointer pb-1"
            onMouseEnter={() => setActiveIndex(i)}
            onMouseLeave={() => setActiveIndex(null)}
          >
            <div
              className="w-2.5 h-2.5 rounded-full shrink-0 transition-opacity"
              style={{
                backgroundColor: COLORS[i % COLORS.length],
                opacity: activeIndex === null || activeIndex === i ? 1 : 0.35,
              }}
            />
            <span
              className="text-[11px] font-medium text-slate-600 transition-opacity"
              style={{ opacity: activeIndex === null || activeIndex === i ? 1 : 0.45 }}
            >
              {entry.category}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
