import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function useBudgetStatus(month?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["budget", householdId, month],
    queryFn: () => api.getBudgetStatus(householdId!, month),
    enabled: !!householdId,
  });
}

export function useSetBudget() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { bank_account_id: string; month: string; amount: number }) => {
      if (!householdId) throw new Error("No household selected");
      return api.setBudget(householdId, body);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budget"] }),
  });
}
