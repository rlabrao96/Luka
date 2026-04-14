import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export type CreateCuotaPayload = {
  merchant_name: string;
  total_amount: number;
  currency: "CLP" | "USD";
  installments_total: number;
  first_cuota_date: string; // YYYY-MM-DD
  split_type?: "personal" | "shared";
  origin_transaction_id?: string | null;
};

export function useCuotas(scope: "personal" | "household" = "personal") {
  return useQuery({
    queryKey: ["cuotas", scope],
    queryFn: () => api.listCuotas(scope),
  });
}

export function useCreateCuota() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateCuotaPayload) => api.createCuota(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cuotas"] });
      // Cuotas feed the budget v2 cuotas summary — refresh that too.
      qc.invalidateQueries({ queryKey: ["budget-v2"] });
    },
  });
}

export function useCancelCuota() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cuotaId: string) => api.cancelCuota(cuotaId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cuotas"] });
      qc.invalidateQueries({ queryKey: ["budget-v2"] });
    },
  });
}
