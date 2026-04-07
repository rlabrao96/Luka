import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SubscriptionOverrideBody } from "@/app/lib/api";

export function useSubscriptions() {
  const { data, isLoading } = useQuery({
    queryKey: ["subscriptions", "detected"],
    queryFn: () => api.getSubscriptions(),
    staleTime: 5 * 60_000,
  });
  return { data, isLoading };
}

export function useRefreshSubscriptions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.refreshSubscriptions(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}

export function useSubscriptionOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SubscriptionOverrideBody) => api.upsertSubscriptionOverride(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
}
