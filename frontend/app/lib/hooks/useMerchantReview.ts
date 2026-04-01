import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useMerchantReview(jobId: string) {
  return useQuery({
    queryKey: ["merchant-review", jobId],
    queryFn: () => api.getReviewCards(jobId),
    enabled: !!jobId,
  });
}

export function useReviewStatus(jobId: string | null) {
  return useQuery({
    queryKey: ["merchant-review", "status", jobId],
    queryFn: () => api.getReviewStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      // Poll every 3s while processing, stop once ready/failed
      const status = query.state.data?.status;
      return status === "processing" ? 3000 : false;
    },
  });
}

export function useApproveMerchant(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ canonicalId, data }: { canonicalId: string; data: { display_name?: string; category?: string; action: string } }) =>
      api.approveMerchant(jobId, canonicalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["merchant-review", jobId] });
    },
  });
}

export function useSkipReview(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.skipReview(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["merchant-review"] });
    },
  });
}
