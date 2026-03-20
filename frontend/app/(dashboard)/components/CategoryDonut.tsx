"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";

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
}

const CLP = (v: number) => `$${Math.round(Number(v)).toLocaleString("es-CL")}`;

export function CategoryDonut({ data }: CategoryDonutProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const total = data.reduce((s, d) => s + Number(d.amount), 0);
  const active = activeIndex !== null ? data[activeIndex] : null;

  return (
    <div className="flex flex-col gap-2">
      {/* Donut with center total */}
      <div className="relative" style={{ height: 190 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="amount"
              nameKey="category"
              cx="50%"
              cy="50%"
              innerRadius={58}
              outerRadius={82}
              paddingAngle={2}
              strokeWidth={0}
              onMouseEnter={(_, index) => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
            >
              {data.map((_, i) => (
                <Cell
                  key={i}
                  fill={COLORS[i % COLORS.length]}
                  opacity={activeIndex === null || activeIndex === i ? 1 : 0.35}
                  style={{ cursor: "pointer", transition: "opacity 0.15s" }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-slate-400">
            {active ? active.category : "Total"}
          </p>
          <p className="text-sm font-bold text-luka-dark tabular-nums leading-tight">
            {CLP(active ? Number(active.amount) : total)}
          </p>
          {active && (
            <p className="text-[10px] text-slate-400 mt-0.5">
              {((Number(active.amount) / total) * 100).toFixed(1)}%
            </p>
          )}
        </div>
      </div>

      {/* Hover info panel — appears below donut */}
      <div
        className={`rounded-lg px-3 py-2 border transition-all duration-150 ${
          active
            ? "bg-white border-slate-100 shadow-sm opacity-100"
            : "opacity-0 border-transparent"
        }`}
        style={{ minHeight: 40 }}
      >
        {active && (
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <div
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: COLORS[activeIndex! % COLORS.length] }}
              />
              <span className="text-xs font-semibold text-luka-dark truncate">
                {active.category}
              </span>
            </div>
            <div className="text-right shrink-0">
              <p className="text-xs font-bold text-luka-dark tabular-nums">
                {CLP(Number(active.amount))}
              </p>
              <p className="text-[10px] text-slate-400">
                {((Number(active.amount) / total) * 100).toFixed(1)}% del total
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Custom legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1.5 justify-center pt-1">
        {data.map((entry, i) => (
          <div
            key={entry.category}
            className="flex items-center gap-1 cursor-pointer"
            onMouseEnter={() => setActiveIndex(i)}
            onMouseLeave={() => setActiveIndex(null)}
          >
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{
                backgroundColor: COLORS[i % COLORS.length],
                opacity: activeIndex === null || activeIndex === i ? 1 : 0.35,
              }}
            />
            <span
              className="text-[10px] text-slate-600 transition-colors"
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
