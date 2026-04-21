"use client";
import { useCallback, useMemo } from "react";
import { Sankey, Tooltip, ResponsiveContainer, Rectangle, Layer } from "recharts";
import { formatMoney, type Currency } from "@/app/lib/format";

type Node = {
  id: string;
  label: string;
  value: number;
  risk?: boolean;
  level?: number | null;
  kind?: "source" | "hub" | "allocation" | "spent" | "deficit" | null;
  member_id?: string | null;
};
type Link = { source: string; target: string; value: number };

interface Props {
  nodes: Node[];
  links: Link[];
  currency: Currency;
}

type RechartsNodeProps = {
  x: number;
  y: number;
  width: number;
  height: number;
  index: number;
};

type RechartsTooltipPayload = {
  payload?: (Node & { source?: number; target?: number }) | undefined;
};

function colorFor(node: Node): string {
  if (node.risk) return "#EF4444";
  // Deficit = synthetic "income" plug when outflows exceed real income.
  // Amber so users immediately see it's not real revenue.
  if (node.kind === "deficit") return "#F59E0B";
  if (node.kind === "hub") return "#2563EB";
  if (node.kind === "source") return "#60A5FA";
  if (node.kind === "allocation") return "#93C5FD";
  if (node.kind === "spent") return "#BFDBFE";
  return "#CBD5E1";
}

function EmptyState() {
  return (
    <div className="flex h-[160px] w-full items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center">
      <p className="text-xs text-slate-400">
        Sin datos suficientes para este mes. Registra ingresos o gastos para ver el flujo.
      </p>
    </div>
  );
}

export default function BudgetSankey({ nodes, links, currency }: Props) {
  // Recharts Sankey divides layout by total flow — zero-sum input causes NaN
  // path attributes and collapses the ResponsiveContainer to -1 dimensions.
  const totalFlow = useMemo(
    () => links.reduce((sum, l) => sum + (Number.isFinite(l.value) ? l.value : 0), 0),
    [links]
  );

  const { safeNodes, data, isTerminal, isPassThrough, maxColumnCount } = useMemo(() => {
    const safe = nodes.filter((n) => Number.isFinite(n.value) && n.value > 0);
    const safeIds = new Set(safe.map((n) => n.id));
    const safeLinks = links.filter(
      (l) =>
        Number.isFinite(l.value) &&
        l.value > 0 &&
        safeIds.has(l.source) &&
        safeIds.has(l.target)
    );
    const safeIdToIndex = new Map(safe.map((n, i) => [n.id, i]));
    const sourceIds = new Set(safeLinks.map((l) => l.source));
    const targetIds = new Set(safeLinks.map((l) => l.target));
    const terminal = new Set(safe.filter((n) => !sourceIds.has(n.id)).map((n) => n.id));
    // Pass-through hubs: nodes that are both a destination of incoming flows
    // AND a source of outgoing flows. In the Luka v3 budget, `disponible_hogar`
    // fits this shape (receives from `ingresos_hogar`, emits to spent-category
    // nodes). Side labels would interleave with those outgoing flows, so we
    // render their labels above the rectangle like the level-1 hub.
    const passThrough = new Set(
      safe.filter((n) => sourceIds.has(n.id) && targetIds.has(n.id)).map((n) => n.id)
    );

    // Count nodes per level to size the chart vertically — terminal columns
    // with many allocation/spent rows were previously squashed into a fixed
    // 360px height, causing flow lines to overlap.
    const levelCounts = new Map<number, number>();
    for (const n of safe) {
      const lvl = n.level ?? (terminal.has(n.id) ? 99 : 0);
      levelCounts.set(lvl, (levelCounts.get(lvl) ?? 0) + 1);
    }
    const maxCol = Math.max(1, ...levelCounts.values());

    return {
      safeNodes: safe,
      data: {
        nodes: safe.map((n) => ({ name: n.label, ...n })),
        links: safeLinks.map((l) => ({
          source: safeIdToIndex.get(l.source)!,
          target: safeIdToIndex.get(l.target)!,
          value: l.value,
        })),
      },
      isTerminal: terminal,
      isPassThrough: passThrough,
      maxColumnCount: maxCol,
    };
  }, [nodes, links]);

  const chartHeight = useMemo(
    () => Math.max(360, maxColumnCount * 56 + 80),
    [maxColumnCount]
  );

  const nodeRenderer = useCallback(
    (props: RechartsNodeProps) => {
      const { x, y, width, height, index } = props;
      const node = safeNodes[index];
      if (
        !node ||
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        !Number.isFinite(width) ||
        !Number.isFinite(height)
      ) {
        return <Layer key={`node-${index}`} />;
      }

      let labelX: number;
      let labelY: number = y + height / 2;
      let anchor: "start" | "end" | "middle";
      let valueY: number = labelY + 14;

      // Pass-through hubs (any level that both receives and emits flows) get
      // labels centered above the rectangle — this keeps the label out of
      // the outgoing flow paths that would otherwise overlap with side labels.
      const isHubLike = node.level === 1 || isPassThrough.has(node.id);

      if (isHubLike) {
        anchor = "middle";
        labelX = x + width / 2;
        labelY = Math.max(y - 18, 10);
        valueY = labelY + 12;
      } else if (node.level === 0) {
        // Source column: label to the LEFT of the rectangle. Margin.left on
        // the Sankey reserves space so labels don't clip out of the SVG.
        anchor = "end";
        labelX = x - 6;
      } else if (node.level === undefined || node.level === null) {
        // v2 fallback: terminal nodes label left, non-terminal label right
        const terminal = isTerminal.has(node.id);
        labelX = terminal ? x - 6 : x + width + 6;
        anchor = terminal ? "end" : "start";
      } else {
        // Terminal level 2+ sits on the right edge. Margin.right reserves
        // ~140px so labels stay inside the SVG viewport.
        anchor = "start";
        labelX = x + width + 6;
      }

      return (
        <Layer key={`node-${index}`}>
          <Rectangle
            x={x}
            y={y}
            width={width}
            height={height}
            fill={colorFor(node)}
            fillOpacity={0.9}
          />
          <text
            x={labelX}
            y={labelY}
            dy={isHubLike ? "0" : "0.35em"}
            textAnchor={anchor}
            className="text-xs font-medium fill-slate-700"
          >
            {node.label}
          </text>
          <text
            x={labelX}
            y={valueY}
            dy={isHubLike ? "0" : undefined}
            textAnchor={anchor}
            className="text-[11px] font-medium fill-slate-600 tabular-nums"
          >
            {formatMoney(node.value, currency)}
          </text>
        </Layer>
      );
    },
    [safeNodes, isTerminal, isPassThrough, currency]
  );

  const tooltipFormatter = useCallback(
    (value: unknown, _name: unknown, props: RechartsTooltipPayload) => {
      const payload = props?.payload;
      if (payload && payload.source !== undefined && payload.target !== undefined) {
        const srcIdx = Number(payload.source);
        const tgtIdx = Number(payload.target);
        const src = safeNodes[srcIdx]?.label ?? "";
        const tgt = safeNodes[tgtIdx]?.label ?? "";
        return [formatMoney(Number(value), currency), `${src} → ${tgt}`];
      }
      const label = payload?.label ?? "Valor";
      return [formatMoney(Number(value), currency), label];
    },
    [safeNodes, currency]
  );

  if (nodes.length === 0 || links.length === 0 || totalFlow <= 0 || data.links.length === 0) {
    return <EmptyState />;
  }

  // Accessible text summary for screen readers. Picks a hub node (level 1) for
  // the total and a handful of top flows so assistive tech gets the gist.
  const hub = safeNodes.find((n) => n.level === 1);
  const summaryParts: string[] = [];
  if (hub) summaryParts.push(`Total: ${formatMoney(hub.value, currency)}.`);
  for (const n of safeNodes.filter((n) => n.level === 2).slice(0, 5)) {
    summaryParts.push(`${n.label}: ${formatMoney(n.value, currency)}.`);
  }
  const ariaSummary = summaryParts.join(" ");

  return (
    <figure
      role="img"
      aria-label={ariaSummary || "Flujo del presupuesto"}
      className="w-full"
    >
      <div className="w-full overflow-x-auto">
        <div
          className="min-w-[560px] md:min-w-[800px]"
          style={{ height: chartHeight }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <Sankey
              data={data}
              margin={{ top: 28, right: 150, bottom: 20, left: 150 }}
              nodePadding={32}
              nodeWidth={16}
              linkCurvature={0.5}
              iterations={64}
              // `align="left"` pins each node to its earliest possible column
              // (shortest path from a source). The default `justify` pushes
              // ALL terminal nodes to the rightmost column — which dragged
              // `gastos_fijos` / `cuotas` (level-2 terminals) across the
              // chart alongside the level-3 breakdown. With `left`, they sit
              // in the same column as `disponible_hogar`.
              align="left"
              node={nodeRenderer as unknown as undefined}
              link={{ stroke: "#CBD5E1", strokeOpacity: 0.35 }}
            >
              <Tooltip formatter={tooltipFormatter as unknown as undefined} />
            </Sankey>
          </ResponsiveContainer>
        </div>
      </div>
      {/* Visually-hidden table fallback for screen readers and users who
          can't parse the SVG. Same data as the Sankey, linearly. */}
      <figcaption className="sr-only">
        <table>
          <caption>Flujo del presupuesto</caption>
          <thead>
            <tr>
              <th>Categoría</th>
              <th>Monto</th>
            </tr>
          </thead>
          <tbody>
            {safeNodes.map((n) => (
              <tr key={n.id}>
                <td>{n.label}</td>
                <td>{formatMoney(n.value, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </figcaption>
    </figure>
  );
}
