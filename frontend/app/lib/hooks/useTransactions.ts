import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function useMyTransactions(limit = 50) {
  return useQuery({
    queryKey: ["transactions", "mine", limit],
    queryFn: () => api.getMyTransactions(limit),
  });
}

export function useSharedTransactions(limit = 50) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["transactions", "shared", householdId, limit],
    queryFn: () => api.getSharedTransactions(householdId!, limit),
    enabled: !!householdId,
  });
}
