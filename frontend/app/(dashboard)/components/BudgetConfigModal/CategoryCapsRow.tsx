"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Grid3x3 } from "lucide-react";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";
import { CategoryCapsEditor } from "./CategoryCapsEditor";

interface Props {
  expanded: boolean;
  onToggle: (id: "caps") => void;
  householdId: string | null;
  month: string;
  householdBudget: BudgetV2Response | undefined;
}

export function CategoryCapsRow({
  expanded,
  onToggle,
  householdId,
  month,
  householdBudget,
}: Props) {
  const [savedTick, setSavedTick] = useState(0);
  const budgets = useQuery({
    queryKey: ["category-budgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId as string, month),
    enabled: !!householdId,
  });

  const summary = useMemo(() => {
    const saved = budgets.data?.budgets?.filter((b) => b.amount > 0) ?? [];
    const count = saved.length;
    // Caps can mix currencies — summing amounts across CLP+USD would be
    // nonsense. Show the distinct-currency count in the secondary line instead.
    const currencies = new Set(saved.map((b) => b.currency ?? "CLP"));
    return { count, currencies };
  }, [budgets.data]);

  const valuePrimary =
    summary.count === 0
      ? "Sin topes"
      : `${summary.count} tope${summary.count === 1 ? "" : "s"} activo${summary.count === 1 ? "" : "s"}`;
  const valueUnit =
    summary.count === 0
      ? undefined
      : summary.currencies.size === 1
        ? `en ${[...summary.currencies][0]}`
        : `en ${summary.currencies.size} monedas`;

  return (
    <AccordionRow
      id="caps"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "caps")}
      icon={<Grid3x3 size={20} />}
      label="Topes por categoría"
      valuePrimary={valuePrimary}
      valueUnit={valueUnit}
      empty={summary.count === 0}
      savedTick={savedTick}
    >
      {householdId && (
        <CategoryCapsEditor
          householdId={householdId}
          month={month}
          householdBudget={householdBudget}
          onSaved={() => setSavedTick((n) => n + 1)}
        />
      )}
    </AccordionRow>
  );
}
