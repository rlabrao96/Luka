"use client";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLukaStore } from "@/app/lib/store";
import { api } from "@/app/lib/api";

function getMonthParam(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function BudgetPrefetcher() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!householdId) return;
    const month = getMonthParam(new Date());

    queryClient.prefetchQuery({
      queryKey: ["personalBudget", householdId, month],
      queryFn: () => api.getPersonalBudget(householdId, month),
      staleTime: 5 * 60 * 1000, // don't re-fetch if already fresh within 5 min
    });
    queryClient.prefetchQuery({
      queryKey: ["allocation", householdId, month],
      queryFn: () => api.getAllocation(householdId, month),
      staleTime: 5 * 60 * 1000,
    });
  }, [householdId, queryClient]);

  return null;
}
