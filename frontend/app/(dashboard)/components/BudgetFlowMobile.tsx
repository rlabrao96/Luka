"use client";
import { useMemo } from "react";
import {
  colorFor,
  isDrillable,
  type BudgetFlowNode,
  type BudgetFlowLink,
} from "@/app/(dashboard)/components/budgetFlow";
import { formatMoney, type Currency } from "@/app/lib/format";
import { cn } from "@/lib/utils";

// Phone-native rendering of the budget money flow. Recharts' Sankey cannot
// reflow onto a 375px viewport, so on mobile we render the SAME node/link data
// as a vertical, scannable layout: income hub at the top, one row per
// allocation (children of the hub) with a proportion bar, and the terminal
// category breakdown nested under each allocation. Props mirror BudgetSankey so
// the page can swap the two purely on breakpoint.
interface Props {
  nodes: BudgetFlowNode[];
  links: BudgetFlowLink[];
  currency: Currency;
  onNodeClick?: (node: BudgetFlowNode) => void;
  activeNodeId?: string | null;
}

function EmptyState() {
  return (
    <div className="flex min-h-[160px] w-full items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50/50 px-6 text-center">
      <p className="text-xs text-slate-400">
        Sin datos suficientes para este mes. Registra ingresos o gastos para ver el flujo.
      </p>
    </div>
  );
}

function FlowRow({
  node,
  pct,
  currency,
  onNodeClick,
  active,
  size,
}: {
  node: BudgetFlowNode;
  pct: number;
  currency: Currency;
  onNodeClick?: (node: BudgetFlowNode) => void;
  active: boolean;
  size: "lg" | "sm";
}) {
  const drillable = !!onNodeClick && isDrillable(node);
  // Backend labels can embed "\n" for the SVG multi-line layout; flatten here.
  const label = node.label.replace(/\n/g, " ");
  const color = colorFor(node);
  const width = Math.max(0, Math.min(100, pct));

  const interactive = drillable
    ? {
        role: "button" as const,
        tabIndex: 0,
        "aria-pressed": active,
        onClick: () => onNodeClick?.(node),
        onKeyDown: (e: React.KeyboardEvent<HTMLDivElement>) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onNodeClick?.(node);
          }
        },
      }
    : {};

  return (
    <div
      {...interactive}
      className={cn(
        "rounded-lg px-2.5 transition-colors",
        size === "lg" ? "min-h-11 py-2" : "min-h-10 py-1.5",
        drillable && "cursor-pointer hover:bg-slate-50 active:bg-slate-100",
        active && "bg-blue-50 ring-1 ring-luka-primary/40"
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={cn(
            "truncate",
            size === "lg"
              ? "text-sm font-medium text-luka-dark"
              : "text-xs text-slate-600"
          )}
        >
          {label}
        </span>
        <span
          className={cn(
            "shrink-0 tabular-nums",
            size === "lg"
              ? "text-sm font-semibold text-luka-dark"
              : "text-xs font-medium text-slate-500"
          )}
        >
          {formatMoney(node.value, currency)}
        </span>
      </div>
      <div
        className={cn(
          "mt-1 w-full overflow-hidden rounded-full bg-slate-100",
          size === "lg" ? "h-1.5" : "h-1"
        )}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function BudgetFlowMobile({
  nodes,
  links,
  currency,
  onNodeClick,
  activeNodeId,
}: Props) {
  const { hub, sources, allocations, childrenOf } = useMemo(() => {
    // Only positive-value nodes/links participate (mirrors BudgetSankey).
    const valid = nodes.filter((n) => Number.isFinite(n.value) && n.value > 0);
    const byId = new Map(valid.map((n) => [n.id, n]));
    const order = new Map(valid.map((n, i) => [n.id, i]));
    const safeLinks = links.filter(
      (l) =>
        Number.isFinite(l.value) &&
        l.value > 0 &&
        byId.has(l.source) &&
        byId.has(l.target)
    );

    // Adjacency: source id -> child nodes, ordered by backend emission order so
    // "Disponible" / "Aún disponible" pin to the top exactly like the Sankey.
    const childIds = new Map<string, string[]>();
    for (const l of safeLinks) {
      const arr = childIds.get(l.source) ?? [];
      arr.push(l.target);
      childIds.set(l.source, arr);
    }
    const childrenOf = new Map<string, BudgetFlowNode[]>();
    for (const [src, tgts] of childIds) {
      const seen = new Set<string>();
      const kids = tgts
        .filter((id) => (seen.has(id) ? false : (seen.add(id), true)))
        .map((id) => byId.get(id)!)
        .sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0));
      childrenOf.set(src, kids);
    }

    const hub = valid.find((n) => n.kind === "hub") ?? null;
    const sources = hub
      ? Array.from(
          new Set(
            safeLinks.filter((l) => l.target === hub.id).map((l) => l.source)
          )
        )
          .map((id) => byId.get(id)!)
          .sort((a, b) => (order.get(a.id) ?? 0) - (order.get(b.id) ?? 0))
      : [];
    const allocations = hub ? childrenOf.get(hub.id) ?? [] : [];
    return { hub, sources, allocations, childrenOf };
  }, [nodes, links]);

  if (!hub || hub.value <= 0 || allocations.length === 0) {
    return <EmptyState />;
  }

  const hubValue = hub.value;

  return (
    <div className="space-y-3">
      {/* Income summary — hub total + the sources that feed it. */}
      <div className="rounded-xl border border-blue-100 bg-blue-50/50 px-3 py-2.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-luka-primary">
            {hub.label}
          </span>
          <span className="text-lg font-bold tabular-nums text-luka-dark">
            {formatMoney(hubValue, currency)}
          </span>
        </div>
        {sources.length > 0 && (
          <ul className="mt-1.5 space-y-0.5">
            {sources.map((s) => (
              <li
                key={s.id}
                className="flex items-baseline justify-between gap-2 text-xs text-slate-500"
              >
                <span className="truncate">{s.label.replace(/\n/g, " ")}</span>
                <span className="shrink-0 tabular-nums">
                  {formatMoney(s.value, currency)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Allocations (hub children) + their nested terminal categories. */}
      <div className="space-y-1.5">
        {allocations.map((alloc) => {
          const terminals = childrenOf.get(alloc.id) ?? [];
          return (
            <div key={alloc.id}>
              <FlowRow
                node={alloc}
                pct={(alloc.value / hubValue) * 100}
                currency={currency}
                onNodeClick={onNodeClick}
                active={activeNodeId === alloc.id}
                size="lg"
              />
              {terminals.length > 0 && (
                <div className="ml-3 mt-0.5 space-y-0.5 border-l border-slate-100 pl-2">
                  {terminals.map((t) => (
                    <FlowRow
                      key={t.id}
                      node={t}
                      pct={alloc.value > 0 ? (t.value / alloc.value) * 100 : 0}
                      currency={currency}
                      onNodeClick={onNodeClick}
                      active={activeNodeId === t.id}
                      size="sm"
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
