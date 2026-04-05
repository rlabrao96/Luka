"use client";
import { useRouter } from "next/navigation";
import { Store, CheckCircle, AlertTriangle, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNotifications, useUpdateNotification, useDeleteNotification } from "@/app/lib/hooks/useNotifications";
import { api } from "@/app/lib/api";
import { cn } from "@/lib/utils";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days}d`;
}

const ICONS: Record<string, typeof Store> = {
  merchant_review: Store,
};

export default function NotificationsPage() {
  const router = useRouter();
  const { data: notifications = [], isLoading } = useNotifications();
  const updateNotification = useUpdateNotification();
  const deleteNotification = useDeleteNotification();
  const queryClient = useQueryClient();

  const dismissReview = useMutation({
    mutationFn: (jobId: string) => api.dismissReview(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const handleDelete = (notif: (typeof notifications)[0]) => {
    deleteNotification.mutate(notif.id);
  };

  const handleReview = (notif: (typeof notifications)[0]) => {
    const jobId = notif.payload?.sync_job_id;
    if (jobId) {
      updateNotification.mutate({ id: notif.id, status: "read" });
      router.push(`/transactions/review/${jobId}`);
    }
  };

  const handleDismiss = (notif: (typeof notifications)[0]) => {
    const jobId = notif.payload?.sync_job_id;
    if (jobId) {
      dismissReview.mutate(jobId);
    } else {
      deleteNotification.mutate(notif.id);
    }
  };

  const handleMarkAllRead = () => {
    notifications
      .filter((n) => n.status === "unread")
      .forEach((n) => updateNotification.mutate({ id: n.id, status: "read" }));
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-slate-200 rounded w-48" />
        <div className="h-24 bg-slate-100 rounded-xl" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-luka-dark">Notificaciones</h1>
        {notifications.some((n) => n.status === "unread") && (
          <button
            onClick={handleMarkAllRead}
            className="text-sm text-luka-primary hover:underline"
          >
            Marcar todas leidas
          </button>
        )}
      </div>

      {notifications.length === 0 ? (
        <div className="text-center py-12 text-luka-muted">
          No tienes notificaciones
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((notif) => {
            const Icon = ICONS[notif.type] ?? AlertTriangle;
            const isUnread = notif.status === "unread";
            const isDone = notif.status === "actioned" || notif.status === "dismissed";

            return (
              <div
                key={notif.id}
                className={cn(
                  "rounded-xl p-4 transition-colors",
                  isUnread
                    ? "bg-blue-50 border border-blue-200"
                    : isDone
                      ? "bg-slate-50 opacity-60"
                      : "bg-white border border-slate-200"
                )}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={cn(
                      "w-9 h-9 rounded-lg flex items-center justify-center shrink-0",
                      isUnread ? "bg-luka-primary text-white" : "bg-slate-200 text-slate-500"
                    )}
                  >
                    {isDone ? <CheckCircle size={18} /> : <Icon size={18} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={cn("text-sm font-semibold", isUnread ? "text-luka-dark" : "text-slate-500")}>
                      {notif.title}
                    </p>
                    {notif.payload?.bank_name && (
                      <p className="text-xs text-luka-muted mt-0.5">
                        {notif.payload.bank_name}
                        {notif.payload.transaction_count
                          ? ` — ${notif.payload.transaction_count} transacciones importadas`
                          : ""}
                      </p>
                    )}
                    <p className="text-[10px] text-slate-400 mt-1">
                      {timeAgo(notif.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {isUnread && <div className="w-2 h-2 bg-luka-primary rounded-full" />}
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(notif); }}
                      className="text-slate-300 hover:text-red-400 transition-colors p-1"
                      title="Eliminar"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {!isDone && notif.type === "merchant_review" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => handleReview(notif)}
                      className="px-4 py-2 bg-luka-primary text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Revisar comercios
                    </button>
                    <button
                      onClick={() => handleDismiss(notif)}
                      className="px-4 py-2 border border-slate-200 text-xs text-slate-500 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      Omitir
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
