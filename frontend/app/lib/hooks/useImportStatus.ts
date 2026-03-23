import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useImportStatus(householdId: string | null) {
  const { data } = useQuery({
    queryKey: ["import-status", householdId],
    queryFn: () => api.getImportStatus(householdId!),
    enabled: !!householdId,
    // Poll every 5s while importing, 60s when idle
    refetchInterval: (query) => (query.state.data?.importing ? 5000 : 60_000),
  });

  return { importing: data?.importing ?? false };
}
