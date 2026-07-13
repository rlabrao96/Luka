// Shared budget-flow primitives used by BOTH the desktop Sankey
// (`BudgetSankey.tsx`) and the mobile flow view (`BudgetFlowMobile.tsx`).
//
// Kept in a Recharts-free module on purpose: BudgetFlowMobile must not
// transitively pull the ~40KB Recharts bundle just to reuse `colorFor` /
// `isDrillable`, so these live here rather than being exported from
// BudgetSankey.tsx (which imports recharts at module top).

export type BudgetFlowNode = {
  id: string;
  label: string;
  value: number;
  risk?: boolean;
  level?: number | null;
  kind?:
    | "source"
    | "hub"
    | "allocation"
    | "bill"
    | "spent"
    | "unused"
    | "deficit"
    | null;
  member_id?: string | null;
};

export type BudgetFlowLink = { source: string; target: string; value: number };

// Nodes that have no per-transaction breakdown — don't dress them up as
// clickable. Keep in sync with the backend `skip` set in
// `v2_service.get_node_drilldown`.
const NON_DRILLABLE: ReadonlySet<string> = new Set([
  "ingresos_hogar",
  "ingresos_personales",
  "disponible_personal",
  "otras_fuentes",
  "deficit_personal",
  "spent_remaining",
  "gastos_fijos",
  "gastos_fijos_personal",
  "cuotas",
  "cuotas_personal",
  "gasto_personal",
]);

export function isDrillable(node: BudgetFlowNode): boolean {
  if (NON_DRILLABLE.has(node.id)) return false;
  if (node.id.startsWith("member_")) return false;
  return true;
}

export function colorFor(node: BudgetFlowNode): string {
  // Red ramp for money that is out / at risk:
  //   risk=true  → #EF4444 (red-500, overshoot alert)
  //   bill       → #F87171 (red-400, committed but unpaid this month)
  //   spent      → #FCA5A5 (red-300, already spent in a category)
  if (node.risk) return "#EF4444";
  if (node.kind === "bill") return "#F87171";
  if (node.kind === "spent") return "#FCA5A5";
  // Unused = money still available (spent_remaining / "Aún disponible").
  // Green so users visually separate "good, room to spend" from the red ramp.
  if (node.kind === "unused") return "#10B981";
  // Deficit = synthetic plug when outflows exceed real income. Amber so
  // users immediately see it's not real revenue.
  if (node.kind === "deficit") return "#F59E0B";
  if (node.kind === "hub") return "#2563EB";
  if (node.kind === "source") return "#60A5FA";
  if (node.kind === "allocation") return "#93C5FD";
  return "#CBD5E1";
}
