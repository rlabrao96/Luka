"use client";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { PaceBlock } from "@/app/lib/api";

interface Props {
  pace: PaceBlock;
}

function formatCLP(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
}

export default function PaceChart({ pace }: Props) {
  const { daily_points, today_day, days_in_month, spendable_budget, delta, on_track } = pace;

  // Build chart data: actual points + dashed pace line for full month
  const chartData = Array.from({ length: days_in_month }, (_, i) => {
    const day = i + 1;
    const actual = daily_points.find((p) => p.day === day);
    const paceValue = Math.round((spendable_budget * day) / days_in_month);
    return {
      day,
      actual:
        actual
          ? actual.cumulative_spent
          : day <= today_day
            ? (daily_points.at(-1)?.cumulative_spent ?? 0)
            : null,
      pace: paceValue,
    };
  });

  const calloutColor = on_track ? "text-emerald-600" : "text-red-500";
  const calloutText = on_track
    ? `${formatCLP(Math.abs(delta))} bajo el ritmo`
    : `${formatCLP(Math.abs(delta))} sobre el ritmo`;

  if (spendable_budget === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-gray-400">
        Conecta tu banco para ver el gráfico de ritmo
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className={`text-sm font-semibold text-right ${calloutColor}`}>{calloutText}</div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#64748B" }}
            ticks={[1, 5, 10, 15, 20, 25, days_in_month]}
          />
          <YAxis hide />
          <Tooltip
            formatter={(val: number) => formatCLP(val)}
            labelFormatter={(d) => `Día ${d}`}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          {/* Dashed pace line */}
          <Line
            type="linear"
            dataKey="pace"
            stroke="#CBD5E1"
            strokeDasharray="4 4"
            dot={false}
            strokeWidth={1.5}
          />
          {/* Actual spending line — color by on_track */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke={on_track ? "#10B981" : "#EF4444"}
            dot={false}
            strokeWidth={2.5}
            connectNulls={false}
          />
          {/* Today marker */}
          <ReferenceLine x={today_day} stroke="#94A3B8" strokeDasharray="2 2" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
