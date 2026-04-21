import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, BulkActionKind, MatchCandidate, PendingTransactions, Transaction } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

function getSince(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().split("T")[0]; // YYYY-MM-DD
}

export function useMyTransactions() {
  const since = getSince();
  return useQuery({
    queryKey: ["transactions", "mine", since],
    queryFn: () => api.getMyTransactions(since),
    staleTime: 5 * 60 * 1000,
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
) {
  return useQuery<MatchCandidate[]>({
    queryKey: ["transactions", "match-candidates", pendingId, windowDays],
    queryFn: () => api.getMatchCandidates(pendingId!, windowDays),
    enabled: !!pendingId,
    staleTime: 30 * 1000,
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
