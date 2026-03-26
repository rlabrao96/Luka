import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useSyncStatus(bankCode: string) {
  return useQuery({
    queryKey: ["sync-status", bankCode],
    queryFn: () => api.getSyncStatus(bankCode),
    refetchInterval: (query) =>
      query.state.data?.current_job_id ? 3000 : false,
    enabled: !!bankCode,
  });
}

export function useBankConnections() {
  return useQuery({
    queryKey: ["bank-connections"],
    queryFn: () => api.getBankConnections(),
  });
}
