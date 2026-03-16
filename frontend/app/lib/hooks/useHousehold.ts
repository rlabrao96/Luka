import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function useHouseholdSummary() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "summary", householdId],
    queryFn: () => api.getHouseholdSummary(householdId!),
    enabled: !!householdId,
  });
}

export function usePartnerStats() {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["household", "partner-stats", householdId],
    queryFn: () => api.getPartnerStats(householdId!),
    enabled: !!householdId,
  });
}
