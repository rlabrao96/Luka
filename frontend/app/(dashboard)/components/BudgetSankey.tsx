"use client";
import { useCallback, useMemo } from "react";
import { Sankey, Tooltip, ResponsiveContainer, Rectangle, Layer } from "recharts";
import { formatMoney, type Currency } from "@/app/lib/format";
import { useBreakpoint } from "@/app/lib/hooks/useBreakpoint";
import {
  colorFor,
  isDrillable,
  type BudgetFlowNode,
  type BudgetFlowLink,
} from "@/app/(dashboard)/components/budgetFlow";

type Node = BudgetFlowNode;
type Link = BudgetFlowLink;

interface Props {
  nodes: Node[];
  links: Link[];
  currency: Currency;
  onNodeClick?: (node: Node) => void;
  activeNodeId?: string | null;
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

function EmptyState() {
  return (
    <div className="flex h-[160px] w-full items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center">
      <p className="text-xs text-slate-400">
        Sin datos suficientes para este mes. Registra ingresos o gastos para ver el flujo.
      </p>
    </div>
  );
}

export default function BudgetSankey({
  nodes,
  links,
  currency,
  onNodeClick,
  activeNodeId,
}: Props) {
  const narrow = useBreakpoint("sm");
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
    () => Math.max(360, maxColumnCount * 56 + 104),
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
      const isBelowLabel = node.kind === "bill";

      if (isHubLike) {
        anchor = "middle";
        labelX = x + width / 2;
        labelY = Math.max(y - 18, 10);
        valueY = labelY + 12;
      } else if (isBelowLabel) {
        // "Bill" nodes (Gastos fijos pendientes) often have tiny rectangles
        // once paid subscriptions drop out. Rendering the label BELOW keeps
        // it away from the adjacent Level 1 → Level 2 flow paths that would
        // otherwise run through a right-side label.
        anchor = "middle";
        labelX = x + width / 2;
        labelY = y + height + 14;
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

      const drillable = onNodeClick !== undefined && isDrillable(node);
      const active = activeNodeId === node.id;
      const handleClick = drillable
        ? (e: React.MouseEvent<SVGGElement>) => {
            e.stopPropagation();
            onNodeClick?.(node);
          }
        : undefined;
      return (
        <Layer
          key={`node-${index}`}
          style={drillable ? { cursor: "pointer" } : undefined}
          onClick={handleClick}
        >
          {/* Larger invisible hit target so clicks land on thin rects + labels. */}
          {drillable && (
            <Rectangle
              x={x - 4}
              y={y - 4}
              width={width + 8}
              height={height + 8}
              fill="transparent"
              fillOpacity={0}
            />
          )}
          <Rectangle
            x={x}
            y={y}
            width={width}
            height={height}
            fill={colorFor(node)}
            fillOpacity={active ? 1 : 0.9}
            stroke={active ? "#0f172a" : undefined}
            strokeWidth={active ? 2 : 0}
          />
          {(() => {
            // Labels can embed `\n` to render on multiple SVG lines. This keeps
            // a long label like "Gastos fijos pendientes" from crowding narrow
            // below-label positioning.
            const lines = node.label.split("\n");
            const baseDy = isHubLike || isBelowLabel ? "0" : "0.35em";
            // When wrapping, push the value below the last label line.
            const valueOffset = (lines.length - 1) * 13;
            return (
              <>
                <text
                  x={labelX}
                  y={labelY}
                  dy={baseDy}
                  textAnchor={anchor}
                  className="text-xs font-medium fill-slate-700"
                >
                  {lines.map((ln, i) => (
                    <tspan key={i} x={labelX} dy={i === 0 ? baseDy : "1.1em"}>
                      {ln}
                    </tspan>
                  ))}
                </text>
                <text
                  x={labelX}
                  y={valueY + valueOffset}
                  dy={isHubLike || isBelowLabel ? "0" : undefined}
                  textAnchor={anchor}
                  className="text-[11px] font-medium fill-slate-600 tabular-nums"
                >
                  {formatMoney(node.value, currency)}
                </text>
              </>
            );
          })()}
        </Layer>
      );
    },
    [safeNodes, isTerminal, isPassThrough, currency, onNodeClick, activeNodeId]
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
          className="min-w-[360px] sm:min-w-[560px] md:min-w-[800px]"
          style={{ height: chartHeight }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <Sankey
              data={data}
              // Tighter margins on narrow viewports so the chart body
              // doesn't collapse under 150px left+right label gutters.
              margin={
                narrow
                  ? { top: 24, right: 72, bottom: 40, left: 72 }
                  : { top: 28, right: 150, bottom: 44, left: 150 }
              }
              nodePadding={narrow ? 20 : 32}
              nodeWidth={16}
              linkCurvature={0.5}
              // Fewer relaxation passes on narrow viewports — the layout is
              // simpler there and 64 iterations is wasted work on a phone. (B5)
              iterations={narrow ? 32 : 64}
              // `align="left"` pins each node to its earliest possible column
              // (shortest path from a source). The default `justify` pushes
              // ALL terminal nodes to the rightmost column — which dragged
              // `gastos_fijos` / `cuotas` (level-2 terminals) across the
              // chart alongside the level-3 breakdown.
              align="left"
              // Recharts re-sorts nodes within each column by ascending Y on
              // every relaxation iteration when `sort=true` (the default),
              // which overrides our backend emission order. `sort=false`
              // keeps the order as emitted — the Level-3 builder emits
              // `spent_remaining` first so "Aún disponible" pins to the top.
              sort={false}
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
