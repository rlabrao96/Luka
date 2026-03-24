"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function NotificationsSection() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api.getNotificationPreferences(),
  });

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => api.updateNotificationPreferences(enabled),
    onMutate: async (enabled) => {
      await queryClient.cancelQueries({ queryKey: ["notification-preferences"] });
      const previous = queryClient.getQueryData(["notification-preferences"]);
      queryClient.setQueryData(["notification-preferences"], { whatsapp_enabled: enabled });
      return { previous };
    },
    onError: (_err, _enabled, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["notification-preferences"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-preferences"] });
    },
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse mb-4" />
        <div className="h-6 w-48 bg-slate-100 rounded animate-pulse" />
      </div>
    );
  }

  const enabled = data?.whatsapp_enabled ?? true;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Notificaciones
      </h3>
      <label className="flex items-center justify-between cursor-pointer min-h-[44px]">
        <span className="text-sm text-slate-700">Notificaciones por WhatsApp</span>
        <button
          role="switch"
          aria-checked={enabled}
          onClick={() => mutation.mutate(!enabled)}
          className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
            enabled ? "bg-blue-600" : "bg-slate-200"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${
              enabled ? "translate-x-[22px]" : "translate-x-[2px]"
            } mt-[2px]`}
          />
        </button>
      </label>
    </div>
  );
}
