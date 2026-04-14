"use client";
import { Sankey, Tooltip, ResponsiveContainer, Rectangle, Layer } from "recharts";
import { formatMoney, type Currency } from "@/app/lib/format";

type Node = { id: string; label: string; value: number; risk?: boolean };
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
  if (node.id in NODE_COLOR) return NODE_COLOR[node.id as keyof typeof NODE_COLOR];
  return NODE_COLOR.other;
}

export default function BudgetSankey({ nodes, links, currency }: Props) {
  const idToIndex = new Map(nodes.map((n, i) => [n.id, i]));
  const data = {
    nodes: nodes.map((n) => ({ name: n.label, ...n })),
    links: links.map((l) => ({
      source: idToIndex.get(l.source)!,
      target: idToIndex.get(l.target)!,
      value: l.value,
    })),
  };

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
              const node = nodes[index];
              return (
                <Layer key={`node-${index}`}>
                  <Rectangle x={x} y={y} width={width} height={height} fill={colorFor(node)} fillOpacity={0.9} />
                  <text x={x + width + 6} y={y + height / 2} dy="0.35em" className="text-xs fill-slate-700">
                    {node.label}
                  </text>
                  <text x={x + width + 6} y={y + height / 2 + 14} className="text-[10px] fill-slate-400 tabular-nums">
                    {formatMoney(node.value, currency)}
                  </text>
                </Layer>
              );
            }) as any}
            link={{ stroke: "#CBD5E1", strokeOpacity: 0.4 }}
          >
            <Tooltip formatter={((value: unknown) => formatMoney(Number(value), currency)) as any} />
          </Sankey>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
