"use client";
import BudgetSankey from "./BudgetSankey";

const fakePayload = {
  nodes: [
    { id: "income", label: "Ingresos", value: 1800000 },
    { id: "known_bills", label: "Gastos fijos", value: 520000 },
    { id: "cuotas", label: "Cuotas del mes", value: 120000 },
    { id: "savings_target", label: "Meta de ahorro", value: 300000 },
    { id: "spendable", label: "Disponible", value: 860000 },
    { id: "spent_restaurants", label: "Restaurantes", value: 142000, risk: true },
    { id: "spent_groceries", label: "Supermercado", value: 180000, risk: true },
    { id: "spent_other", label: "Otros", value: 95000 },
  ],
  links: [
    { source: "income", target: "known_bills", value: 520000 },
    { source: "income", target: "cuotas", value: 120000 },
    { source: "income", target: "savings_target", value: 300000 },
    { source: "income", target: "spendable", value: 860000 },
    { source: "spendable", target: "spent_restaurants", value: 142000 },
    { source: "spendable", target: "spent_groceries", value: 180000 },
    { source: "spendable", target: "spent_other", value: 95000 },
  ],
};

export default function SankeyDev() {
  return <BudgetSankey nodes={fakePayload.nodes} links={fakePayload.links} currency="CLP" />;
}
