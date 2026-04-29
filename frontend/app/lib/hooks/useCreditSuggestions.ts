import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, CreditSuggestionItem } from "@/app/lib/api";

const QK = ["credit-suggestions"] as const;

export function useCreditSuggestions() {
  return useQuery({
    queryKey: QK,
    queryFn: () => api.getCreditSuggestions(),
    staleTime: 30 * 1000,
  });
}

export function useConfirmCreditSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.confirmCreditSuggestion(id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: QK });
      const prev = qc.getQueryData<CreditSuggestionItem[]>(QK);
      if (prev) {
        qc.setQueryData<CreditSuggestionItem[]>(
          QK,
          prev.filter((s) => s.id !== id),
        );
      }
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(QK, ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: QK });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["pending-transactions"] });
    },
  });
}

export function useDismissCreditSuggestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.dismissCreditSuggestion(id),
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: QK });
      const prev = qc.getQueryData<CreditSuggestionItem[]>(QK);
      if (prev) {
        qc.setQueryData<CreditSuggestionItem[]>(
          QK,
          prev.filter((s) => s.id !== id),
        );
      }
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(QK, ctx.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: QK });
    },
  });
}
