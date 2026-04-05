import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useCallback } from "react";

export function useMerchantReview(jobId: string) {
  return useQuery({
    queryKey: ["merchant-review", jobId],
    queryFn: () => api.getReviewCards(jobId),
    enabled: !!jobId,
    staleTime: Infinity, // Cards don't change during review
  });
}

export function useReviewStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["merchant-review", "status", jobId],
    queryFn: () => api.getReviewStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" ? 3000 : false;
    },
  });
}

/**
 * Optimistic approve/skip: advances immediately, fires API in background.
 * Shows a toast on error so the user knows something failed.
 */
export function useOptimisticReview(jobId: string) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: ({ canonicalId, data }: { canonicalId: string; data: { display_name?: string; category?: string; action: string } }) =>
      api.approveMerchant(jobId, canonicalId, data),
    onError: (_error, variables) => {
      console.error(`Failed to save merchant ${variables.canonicalId}`, _error);
    },
    onSettled: () => {
      // Invalidate after all pending mutations settle
      if (mutation.isPending) return;
      queryClient.invalidateQueries({ queryKey: ["merchant-review", jobId] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const submit = useCallback(
    (canonicalId: string, data: { display_name?: string; category?: string; action: string }) => {
      mutation.mutate({ canonicalId, data });
    },
    [mutation]
  );

  return { submit };
}

export function useSkipReview(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.skipReview(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["merchant-review"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}
