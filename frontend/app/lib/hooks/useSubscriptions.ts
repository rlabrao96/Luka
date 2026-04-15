import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type SubscriptionOverrideBody,
  type SubscriptionsResponse,
} from "@/app/lib/api";

const QUERY_KEY = ["subscriptions", "detected"] as const;

export function useSubscriptions() {
  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
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
    mutationFn: (body: SubscriptionOverrideBody) =>
      api.upsertSubscriptionOverride(body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: QUERY_KEY });
      const previous = qc.getQueryData<SubscriptionsResponse>(QUERY_KEY);

      if (previous) {
        qc.setQueryData<SubscriptionsResponse>(QUERY_KEY, {
          ...previous,
          items: previous.items.map((item) =>
            item.merchant_name === body.merchant_key
              ? {
                  ...item,
                  ...(body.status != null && { status: body.status }),
                  ...(body.category != null && { category: body.category }),
                  ...(body.next_charge_day != null && {
                    next_charge_day: body.next_charge_day,
                  }),
                  ...(body.split_type != null && {
                    split_type: body.split_type,
                  }),
                }
              : item,
          ),
        });
      }

      return { previous };
    },
    onError: (_err, _body, context) => {
      if (context?.previous) {
        qc.setQueryData(QUERY_KEY, context.previous);
      }
    },
    onSettled: () => {
      // Short delay (300ms) buffers any PgBouncer transaction-pool edge case
      // where the read connection hasn't seen the cascade commit yet. The
      // optimistic update keeps the UI instant; this just reconciles in the
      // background without making the user wait the full 2s the old delay
      // imposed.
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["subscriptions"] });
        qc.invalidateQueries({ queryKey: ["budget-v2"] });
      }, 300);
    },
  });
}
