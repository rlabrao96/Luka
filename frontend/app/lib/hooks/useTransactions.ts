import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, BulkActionKind, MatchCandidate, PendingTransactions, Transaction } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

function getSince(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().split("T")[0]; // YYYY-MM-DD
}

export function useMyTransactions(opts?: { month?: string; limit?: number }) {
  const since = getSince();
  return useQuery({
    queryKey: ["transactions", "mine", since, opts?.month ?? null, opts?.limit ?? null],
    queryFn: () => api.getMyTransactions(since, opts),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDashboardSummary(month?: string, currency?: string) {
  return useQuery({
    queryKey: ["dashboard-summary", month, currency],
    queryFn: () => api.getDashboardSummary(month!, currency!),
    enabled: !!month && !!currency,
    staleTime: 60 * 1000,
  });
}

export function useSharedTransactions() {
  const householdId = useLukaStore((s) => s.householdId);
  const since = getSince();
  return useQuery({
    queryKey: ["transactions", "shared", householdId, since],
    queryFn: () => api.getSharedTransactions(householdId!, since),
    enabled: !!householdId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMonthlySpending(currency?: string) {
  const householdId = useLukaStore((s) => s.householdId);
  return useQuery({
    queryKey: ["transactions", "monthly-summary", householdId, currency],
    queryFn: () => api.getMonthlySpending(householdId!, currency),
    enabled: !!householdId,
  });
}

export function usePendingTransactions() {
  return useQuery({
    queryKey: ["transactions", "pending"],
    queryFn: () => api.getPendingTransactions(),
    staleTime: 30 * 1000,
  });
}

// ── Phase 3 consolidation: match / link / dismiss / bulk ────────────
//
// All mutations invalidate both ["transactions"] and ["transactions","pending"]
// in `onSettled` so the cache reconciles with server state even when the
// optimistic update diverges (review finding #14).

export function useMatchCandidates(
  pendingId: string | null,
  windowDays: number = 7,
  intent: "consolidate" | "transfer" | "reimbursement" = "consolidate",
  q?: string,
) {
  return useQuery<MatchCandidate[]>({
    queryKey: ["transactions", "match-candidates", pendingId, windowDays, intent, q ?? ""],
    queryFn: () => api.getMatchCandidates(pendingId!, { windowDays, intent, q }),
    enabled: !!pendingId,
    staleTime: 30 * 1000,
  });
}

export function useReimbursementCandidates(
  anchorId: string | null,
  windowDays: number,
  q?: string,
) {
  return useMatchCandidates(anchorId, windowDays, "reimbursement", q);
}

export function useUpdateTransactionDate() {
  const queryClient = useQueryClient();
  return useMutation<
    { ok: boolean },
    Error,
    { transactionId: string; transactionDate: string },
    { previousByKey: Map<unknown, Transaction[] | undefined> }
  >({
    mutationFn: ({ transactionId, transactionDate }) =>
      api.updateTransactionDate(transactionId, transactionDate),
    onMutate: async ({ transactionId, transactionDate }) => {
      // Optimistically patch the date on array-shaped caches (mine/shared).
      // The backend stores UTC midnight; we mirror that here so re-rendered
      // dates match what the server will emit.
      await queryClient.cancelQueries({ queryKey: ["transactions"] });
      const isoDateTime = `${transactionDate}T00:00:00+00:00`;
      const filter = {
        predicate: (q: { queryKey: readonly unknown[] }) => {
          const [root, bucket] = q.queryKey as unknown as [string, string];
          return root === "transactions" && (bucket === "mine" || bucket === "shared");
        },
      };
      const snapshot = queryClient.getQueriesData<Transaction[]>(filter);
      const previousByKey = new Map<unknown, Transaction[] | undefined>();
      for (const [key, value] of snapshot) previousByKey.set(key, value);
      queryClient.setQueriesData<Transaction[]>(filter, (old) =>
        Array.isArray(old)
          ? old.map((t) =>
              t.id === transactionId ? { ...t, transaction_date: isoDateTime } : t,
            )
          : old,
      );
      return { previousByKey };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previousByKey) {
        for (const [key, value] of ctx.previousByKey.entries()) {
          queryClient.setQueryData(key as readonly unknown[], value);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useLinkTransfer() {
  const queryClient = useQueryClient();
  return useMutation<
    { transfer_pair_id: string; transaction_ids: string[] },
    Error,
    { transactionId: string; counterpartId: string }
  >({
    mutationFn: ({ transactionId, counterpartId }) =>
      api.linkTransfer(transactionId, counterpartId),
    onSettled: () => {
      // Pairing changes which rows show as a single grouped card and removes
      // both legs from spend/income totals — invalidate everything.
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useLinkReimbursement() {
  const queryClient = useQueryClient();
  return useMutation<
    { reimbursement_group_id: string; transaction_ids: string[] },
    Error,
    { transactionId: string; counterpartIds: string[] }
  >({
    mutationFn: ({ transactionId, counterpartIds }) =>
      api.linkReimbursement(transactionId, counterpartIds),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useUnlinkReimbursement() {
  const queryClient = useQueryClient();
  return useMutation<{ unlinked: number }, Error, { groupId: string }>({
    mutationFn: ({ groupId }) => api.unlinkReimbursement(groupId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
}

export function useLinkTransaction() {
  const queryClient = useQueryClient();
  return useMutation<
    Transaction,
    Error,
    { pendingId: string; bankTransactionId: string }
  >({
    mutationFn: ({ pendingId, bankTransactionId }) =>
      api.linkTransaction(pendingId, bankTransactionId),
    onMutate: async ({ pendingId }) => {
      // Optimistically remove the pending row so the UI feels instant.
      const queryKey = ["transactions", "pending"];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PendingTransactions>(queryKey);
      queryClient.setQueryData<PendingTransactions | undefined>(
        queryKey,
        (old) => {
          if (!old) return old;
          const drop = (list: Transaction[]) =>
            list.filter((t) => t.id !== pendingId);
          return {
            awaiting_reconciliation: drop(old.awaiting_reconciliation),
            needs_classification: drop(old.needs_classification),
            unmatched_email: drop(old.unmatched_email),
          };
        },
      );
      return { previous } as { previous: PendingTransactions | undefined };
    },
    onError: (_err, _vars, ctx) => {
      const context = ctx as { previous?: PendingTransactions } | undefined;
      if (context?.previous) {
        queryClient.setQueryData(["transactions", "pending"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    },
  });
}

export function useDismissTransaction() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id: string) => api.dismissTransaction(id),
    onMutate: async (id) => {
      const queryKey = ["transactions", "pending"];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PendingTransactions>(queryKey);
      queryClient.setQueryData<PendingTransactions | undefined>(
        queryKey,
        (old) => {
          if (!old) return old;
          const drop = (list: Transaction[]) => list.filter((t) => t.id !== id);
          return {
            awaiting_reconciliation: drop(old.awaiting_reconciliation),
            needs_classification: drop(old.needs_classification),
            unmatched_email: drop(old.unmatched_email),
          };
        },
      );
      return { previous } as { previous: PendingTransactions | undefined };
    },
    onError: (_err, _vars, ctx) => {
      const context = ctx as { previous?: PendingTransactions } | undefined;
      if (context?.previous) {
        queryClient.setQueryData(["transactions", "pending"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    },
  });
}

export function useDeleteTransaction() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id: string) => api.deleteTransaction(id),
    onMutate: async (id) => {
      const queryKey = ["transactions", "pending"];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PendingTransactions>(queryKey);
      queryClient.setQueryData<PendingTransactions | undefined>(
        queryKey,
        (old) => {
          if (!old) return old;
          const drop = (list: Transaction[]) => list.filter((t) => t.id !== id);
          return {
            awaiting_reconciliation: drop(old.awaiting_reconciliation),
            needs_classification: drop(old.needs_classification),
            unmatched_email: drop(old.unmatched_email),
          };
        },
      );
      return { previous } as { previous: PendingTransactions | undefined };
    },
    onError: (_err, _vars, ctx) => {
      const context = ctx as { previous?: PendingTransactions } | undefined;
      if (context?.previous) {
        queryClient.setQueryData(["transactions", "pending"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    },
  });
}

export function useCategoryMatchingCount(
  transactionId: string | null,
  category: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["transactions", "category-matching-count", transactionId, category],
    queryFn: () => api.getCategoryMatchingCount(transactionId!, category),
    enabled: !!transactionId && enabled,
    staleTime: 60 * 1000,
  });
}

export function useUpdateCategoryBulk() {
  const queryClient = useQueryClient();
  return useMutation<
    { ok: boolean; updated_count: number },
    Error,
    { transactionId: string; category: string | null }
  >({
    mutationFn: ({ transactionId, category }) =>
      api.updateTransactionCategory(transactionId, category, {
        apply_to_all_matching: true,
      }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
      queryClient.invalidateQueries({
        queryKey: ["transactions", "category-matching-count"],
      });
    },
  });
}

export function useMerchantNameMatchingCount(
  transactionId: string | null,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["transactions", "merchant-name-matching-count", transactionId],
    queryFn: () => api.getMerchantNameMatchingCount(transactionId!),
    enabled: !!transactionId && enabled,
    staleTime: 60 * 1000,
  });
}

export function useUpdateMerchantName() {
  const queryClient = useQueryClient();
  return useMutation<
    { ok: boolean; updated_count: number },
    Error,
    {
      transactionId: string;
      rawMerchantName?: string | null;
      merchantId?: string | null;
      applyToAllMatching?: boolean;
    }
  >({
    mutationFn: ({ transactionId, rawMerchantName, merchantId, applyToAllMatching }) =>
      api.updateMerchantName(transactionId, {
        raw_merchant_name: rawMerchantName,
        merchant_id: merchantId,
        apply_to_all_matching: applyToAllMatching ?? false,
      }),
    onMutate: async ({ transactionId, rawMerchantName, applyToAllMatching }) => {
      const queryKey = ["transactions", "pending"];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PendingTransactions>(queryKey);
      // Optimistic rename for the anchor row only — bulk updates can touch
      // many rows and we'd rather refetch than reconcile a sprawling cache
      // patch. The `onSettled` invalidation handles the rest.
      if (rawMerchantName != null && !applyToAllMatching) {
        queryClient.setQueryData<PendingTransactions | undefined>(
          queryKey,
          (old) => {
            if (!old) return old;
            const patch = (list: Transaction[]) =>
              list.map((t) =>
                t.id === transactionId
                  ? { ...t, raw_merchant_name: rawMerchantName }
                  : t,
              );
            return {
              awaiting_reconciliation: patch(old.awaiting_reconciliation),
              needs_classification: patch(old.needs_classification),
              unmatched_email: patch(old.unmatched_email),
            };
          },
        );
      }
      return { previous } as { previous: PendingTransactions | undefined };
    },
    onError: (_err, _vars, ctx) => {
      const context = ctx as { previous?: PendingTransactions } | undefined;
      if (context?.previous) {
        queryClient.setQueryData(["transactions", "pending"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
      queryClient.invalidateQueries({
        queryKey: ["transactions", "merchant-name-matching-count"],
      });
    },
  });
}

export function useBulkAction() {
  const queryClient = useQueryClient();
  return useMutation<
    { processed: number },
    Error,
    { transactionIds: string[]; action: BulkActionKind }
  >({
    mutationFn: ({ transactionIds, action }) =>
      api.bulkAction(transactionIds, action),
    onMutate: async ({ transactionIds }) => {
      const queryKey = ["transactions", "pending"];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PendingTransactions>(queryKey);
      const idSet = new Set(transactionIds);
      queryClient.setQueryData<PendingTransactions | undefined>(
        queryKey,
        (old) => {
          if (!old) return old;
          const drop = (list: Transaction[]) =>
            list.filter((t) => !idSet.has(t.id));
          return {
            awaiting_reconciliation: drop(old.awaiting_reconciliation),
            needs_classification: drop(old.needs_classification),
            unmatched_email: drop(old.unmatched_email),
          };
        },
      );
      return { previous } as { previous: PendingTransactions | undefined };
    },
    onError: (_err, _vars, ctx) => {
      const context = ctx as { previous?: PendingTransactions } | undefined;
      if (context?.previous) {
        queryClient.setQueryData(["transactions", "pending"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transactions", "pending"] });
    },
  });
}
