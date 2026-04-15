"use client";
import { Sankey, Tooltip, ResponsiveContainer, Rectangle, Layer } from "recharts";
import { formatMoney, type Currency } from "@/app/lib/format";

type Node = {
  id: string;
  label: string;
  value: number;
  risk?: boolean;
  // Budget v3 rank-based fields (optional — absent on v2 responses)
  level?: number | null;
  kind?: "source" | "hub" | "allocation" | "spent" | null;
  member_id?: string | null;
};
type Link = { source: string; target: string; value: number };

interface Props {
  nodes: Node[];
  links: Link[];
  currency: Currency;
}

const NODE_COLOR = {
  income: "#2563EB",
  known_bills: "#94A3B8",
  cuotas: "#F59E0B",
  savings_target: "#10B981",
  spendable: "#60A5FA",
  other: "#CBD5E1",
  risk: "#EF4444",
};

function colorFor(node: Node): string {
  if (node.risk) return NODE_COLOR.risk;
  // v3: prefer kind-based color when available
  if (node.kind === "hub") return "#2563EB";
  if (node.kind === "source") return "#60A5FA";
  if (node.kind === "allocation") return "#93C5FD";
  if (node.kind === "spent") return "#BFDBFE";
  // v2 fallback: id-based color
  if (node.id in NODE_COLOR) return NODE_COLOR[node.id as keyof typeof NODE_COLOR];
  return NODE_COLOR.other;
}

export default function BudgetSankey({ nodes, links, currency }: Props) {
  // Recharts Sankey divides layout by total flow — zero-sum input causes NaN
  // path attributes and collapses the ResponsiveContainer to -1 dimensions.
  // Guard here so a user with no income yet gets a friendly empty state.
  const totalFlow = links.reduce((sum, l) => sum + (Number.isFinite(l.value) ? l.value : 0), 0);
  if (nodes.length === 0 || links.length === 0 || totalFlow <= 0) {
    return (
      <div className="flex h-[160px] w-full items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center">
        <p className="text-xs text-slate-400">
          Sin datos suficientes para este mes. Registra ingresos o gastos para ver el flujo.
        </p>
      </div>
    );
  }

  const idToIndex = new Map(nodes.map((n, i) => [n.id, i]));
  const safeNodes = nodes.filter((n) => Number.isFinite(n.value) && n.value > 0);
  const safeIds = new Set(safeNodes.map((n) => n.id));
  const safeLinks = links.filter(
    (l) =>
      Number.isFinite(l.value) &&
      l.value > 0 &&
      safeIds.has(l.source) &&
      safeIds.has(l.target)
  );
  if (safeLinks.length === 0) {
    return (
      <div className="flex h-[160px] w-full items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center">
        <p className="text-xs text-slate-400">
          Sin datos suficientes para este mes. Registra ingresos o gastos para ver el flujo.
        </p>
      </div>
    );
  }
  const safeIdToIndex = new Map(safeNodes.map((n, i) => [n.id, i]));
  const data = {
    nodes: safeNodes.map((n) => ({ name: n.label, ...n })),
    links: safeLinks.map((l) => ({
      source: safeIdToIndex.get(l.source)!,
      target: safeIdToIndex.get(l.target)!,
      value: l.value,
    })),
  };

  // Terminal nodes = nodes that never appear as a link source. Their rectangles
  // sit on the right edge of the Sankey, so their labels must be rendered to
  // the LEFT of the rectangle (with textAnchor="end") to stay inside the
  // chart bounds. Non-terminal nodes (income, spendable) keep right-side labels.
  const sourceIds = new Set(safeLinks.map((l) => l.source));
  const isTerminal = new Set(safeNodes.filter((n) => !sourceIds.has(n.id)).map((n) => n.id));

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[720px] h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={data}
            nodePadding={24}
            nodeWidth={16}
            linkCurvature={0.5}
            iterations={32}
            node={((props: any) => {
              const { x, y, width, height, index } = props;
              const node = safeNodes[index];
              if (!node || !Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(width) || !Number.isFinite(height)) {
                return <Layer key={`node-${index}`} />;
              }
              // Rank-based label placement (v3): use `level` field when present.
              // Backward-compat fallback (v2): use terminal-detection heuristic.
              let labelX: number;
              let labelY: number = y + height / 2;
              let anchor: "start" | "end" | "middle";
              let valueY: number = labelY + 14;

              if (node.level === undefined || node.level === null) {
                // v2 fallback: terminal nodes label left, non-terminal label right
                const terminal = isTerminal.has(node.id);
                labelX = terminal ? x - 6 : x + width + 6;
                anchor = terminal ? "end" : "start";
              } else if (node.level === 0) {
                // Sources: label on the LEFT
                anchor = "end";
                labelX = x - 6;
              } else if (node.level === 1) {
                // Hub: label ABOVE, centered. Clamp to viewport so the label
                // never clips when the hub is the topmost element in its column.
                anchor = "middle";
                labelX = x + width / 2;
                labelY = Math.max(y - 18, 10);
                valueY = labelY + 12;
              } else {
                // Level 2 (allocations) and level 3 (breakdown): label on the RIGHT
                anchor = "start";
                labelX = x + width + 6;
              }

              return (
                <Layer key={`node-${index}`}>
                  <Rectangle x={x} y={y} width={width} height={height} fill={colorFor(node)} fillOpacity={0.9} />
                  <text
                    x={labelX}
                    y={labelY}
                    dy={node.level === 1 ? "0" : "0.35em"}
                    textAnchor={anchor}
                    className="text-xs fill-slate-700"
                  >
                    {node.label}
                  </text>
                  <text
                    x={labelX}
                    y={valueY}
                    dy={node.level === 1 ? "0" : undefined}
                    textAnchor={anchor}
                    className="text-[10px] fill-slate-400 tabular-nums"
                  >
                    {formatMoney(node.value, currency)}
                  </text>
                </Layer>
              );
            }) as any}
            link={{ stroke: "#CBD5E1", strokeOpacity: 0.4 }}
          >
            <Tooltip
              formatter={((value: unknown, _name: unknown, props: any) => {
                const payload = props?.payload as Node | undefined;
                const label = payload?.label ?? "Valor";
                return [formatMoney(Number(value), currency), label];
              }) as any}
            />
          </Sankey>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
