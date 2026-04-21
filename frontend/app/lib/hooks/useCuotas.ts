import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export type CreateCuotaPayload = {
  merchant_name: string;
  total_amount: number;
  currency: string;
  installments_total: number;
  first_cuota_date: string; // YYYY-MM-DD
  split_type?: "personal" | "shared";
  origin_transaction_id?: string | null;
};

export function useCuotas(scope: "personal" | "household" = "personal") {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["cuotas", scope, scope === "household" ? householdId : null],
    queryFn: () => api.listCuotas(scope, householdId ?? undefined),
    enabled: scope === "personal" || !!householdId,
  });
}

export function useCreateCuota() {
  const qc = useQueryClient();
  const householdId = useLukaStore((s) => s.householdId);
  return useMutation({
    mutationFn: (payload: CreateCuotaPayload) => {
      if (!householdId) throw new Error("No household selected");
      return api.createCuota(householdId, payload);
    },
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
