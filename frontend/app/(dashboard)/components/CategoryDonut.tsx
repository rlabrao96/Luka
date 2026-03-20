"use client";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

const COLORS = [
  "#2563EB", // blue-600 — primary
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
  return (
    <div style={{ width: "100%", height: 220 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="amount"
            nameKey="category"
            cx="50%"
            cy="42%"
            innerRadius={50}
            outerRadius={74}
            paddingAngle={3}
            strokeWidth={0}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ borderRadius: "12px", border: "1px solid #E2E8F0", fontSize: 11 }}
            formatter={(v) => [CLP(Number(v)), ""]}
          />
          <Legend
            iconType="circle"
            iconSize={7}
            wrapperStyle={{ fontSize: 10, paddingTop: 4 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
