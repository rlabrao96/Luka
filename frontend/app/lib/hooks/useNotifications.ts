import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/app/lib/api";

type NotificationItem = Awaited<ReturnType<typeof api.getNotifications>>[number];

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.getNotifications(),
    staleTime: 30 * 1000,
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.getUnreadCount(),
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000, // Poll every 30s for badge updates
  });
}

export function useUpdateNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.updateNotification(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useDeleteNotification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      try {
        return await api.deleteNotification(id);
      } catch (err) {
        // The row is already gone server-side — that's the desired state.
        // Don't fail the mutation: let the cache update so the UI self-heals.
        if (err instanceof ApiError && err.status === 404) return { ok: true };
        throw err;
      }
    },
    onMutate: async (id: string) => {
      // Apply the optimistic update first so the UI updates instantly,
      // then cancel any in-flight refetch so it can't overwrite us.
      const prev = queryClient.getQueryData<NotificationItem[]>(["notifications"]);
      if (prev) {
        queryClient.setQueryData<NotificationItem[]>(
          ["notifications"],
          prev.filter((n) => n.id !== id),
        );
      }
      await queryClient.cancelQueries({ queryKey: ["notifications"] });
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) queryClient.setQueryData(["notifications"], ctx.prev);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
