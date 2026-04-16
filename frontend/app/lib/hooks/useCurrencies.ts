// frontend/app/lib/hooks/useCurrencies.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type UserCurrency } from "@/app/lib/api";

export function useCurrencies() {
  return useQuery<UserCurrency[]>({
    queryKey: ["currencies"],
    queryFn: () => api.getCurrencies(),
    staleTime: 60_000,
  });
}

export function useAddCurrency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api.addCurrency(code),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["currencies"] }),
  });
}

export function useDeleteCurrency() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => api.deleteCurrency(code),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["currencies"] }),
  });
}
