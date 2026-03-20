"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

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
  
  // Custom tooltip for clean professional overlay
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const { category, amount } = payload[0].payload;
      const pct = total > 0 ? ((amount / total) * 100).toFixed(1) : "0.0";
      return (
        <div className="bg-white px-3 py-2 rounded-lg border border-slate-100 shadow-sm flex flex-col gap-1">
          <p className="text-xs font-semibold text-slate-700">{category}</p>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900">{CLP(amount)}</span>
            <span className="text-[10px] text-slate-400 font-medium">({pct}%)</span>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Donut with fixed center total */}
      <div className="relative mt-2" style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "transparent" }} />
            <Pie
              data={data}
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
              {data.map((_, i) => (
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
            {CLP(total)}
          </p>
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
