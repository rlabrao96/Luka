import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

function getSince(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().split("T")[0]; // YYYY-MM-DD
}

export function useMyTransactions() {
  const since = getSince();
  return useQuery({
    queryKey: ["transactions", "mine", since],
    queryFn: () => api.getMyTransactions(since),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSharedTransactions() {
  const householdId = useLukaStore((s) => s.householdId);
  const since = getSince();
  return useQuery({
    queryKey: ["transactions", "shared", householdId, since],
    queryFn: () => api.getSharedTransactions(householdId!, since),
    enabled: !!householdId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMonthlySpending() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["transactions", "monthly-summary", householdId],
    queryFn: () => api.getMonthlySpending(householdId!),
    enabled: !!householdId,
  });
}
