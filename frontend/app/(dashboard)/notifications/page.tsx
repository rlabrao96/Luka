"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Store, CheckCircle, AlertTriangle, Trash2, CheckCheck, TrendingUp, BellRing, BarChart3, CreditCard, Tags } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNotifications, useUpdateNotification, useDeleteNotification } from "@/app/lib/hooks/useNotifications";
import { api, type NotificationItem } from "@/app/lib/api";
type NotificationItemPayload = NotificationItem["payload"];
import { cn } from "@/lib/utils";
import { formatStoredAmount } from "@/app/lib/currency";
import { resolveAppLocale } from "@/app/lib/locale";
import { PageHeader } from "../components/PageHeader";
import { PorClasificar } from "../components/PorClasificar";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

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
  monthly_recap: BarChart3,
  subscription_price_increase: TrendingUp,
  subscription_upcoming_charge: BellRing,
  new_account_detected: CreditCard,
  charge_attributed: CreditCard,
  attribution_rejected: CreditCard,
  attribution_removed: CreditCard,
  pending_card_classification: Tags,
};

/** Per-type subtitle under the notification title. Titles already carry the
 *  human summary; this adds the useful detail from the payload. */
function NotifDetail({ notif }: { notif: { type: string; payload: NotificationItemPayload } }) {
  const p = notif.payload;
  if (!p) return null;
  if (notif.type === "monthly_recap" && p.body) {
    // The recap body is a multi-line WhatsApp-style summary; render the
    // lines after the title (skip the first line, which is the title).
    const lines = p.body.split("\n").slice(1).filter(Boolean);
    return (
      <div className="mt-1.5 space-y-0.5">
        {lines.map((line, i) => (
          <p key={i} className="text-xs text-slate-600 leading-snug">
            {line}
          </p>
        ))}
      </div>
    );
  }
  if (notif.type === "subscription_price_increase" && p.previous_amount && p.new_amount) {
    const ccy = p.currency ?? "CLP";
    return (
      <p className="mt-0.5 text-xs text-luka-muted">
        {formatStoredAmount(Number(p.previous_amount), ccy)} →{" "}
        <span className="font-semibold text-amber-600">
          {formatStoredAmount(Number(p.new_amount), ccy)}
        </span>
      </p>
    );
  }
  if (notif.type === "subscription_upcoming_charge" && p.charge_date) {
    const when = new Date(p.charge_date).toLocaleDateString(resolveAppLocale(), {
      day: "numeric",
      month: "long",
    });
    return <p className="mt-0.5 text-xs text-luka-muted">Cargo estimado el {when}</p>;
  }
  if (notif.type === "new_account_detected") {
    return (
      <p className="mt-0.5 text-xs text-luka-muted">
        {p.account_label ? <span className="font-medium">{p.account_label}</span> : null}
        {p.account_label ? " · " : ""}Si es de tu pareja, márcala para que sus gastos no cuenten
        como tuyos.
      </p>
    );
  }
  if (notif.type === "charge_attributed" && p.merchant && p.amount != null) {
    const ccy = p.currency ?? "CLP";
    return (
      <p className="mt-0.5 text-xs text-luka-muted">
        <span className="font-medium">{p.merchant}</span> ·{" "}
        {formatStoredAmount(Number(p.amount), ccy)}
      </p>
    );
  }
  if (notif.type === "attribution_rejected") {
    return <p className="mt-0.5 text-xs text-luka-muted">Vuelve a tus gastos.</p>;
  }
  if (notif.type === "attribution_removed") {
    return <p className="mt-0.5 text-xs text-luka-muted">Se quitó de tus gastos.</p>;
  }
  if (notif.type === "pending_card_classification") {
    const n = p.count ?? 0;
    return (
      <p className="mt-0.5 text-xs text-luka-muted">
        {n} {n === 1 ? "cargo" : "cargos"} en tu tarjeta compartida esperan clasificación.
      </p>
    );
  }
  return null;
}

export default function NotificationsPage() {
  const router = useRouter();
  const { data: notifications = [], isLoading } = useNotifications();
  const updateNotification = useUpdateNotification();
  const deleteNotification = useDeleteNotification();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<(typeof notifications)[0] | null>(null);

  // Prefetch review cards for all merchant_review notifications
  useEffect(() => {
    notifications
      .filter((n) => n.type === "merchant_review" && n.payload?.sync_job_id)
      .forEach((n) => {
        const jobId = n.payload!.sync_job_id as string;
        queryClient.prefetchQuery({
          queryKey: ["merchant-review", jobId],
          queryFn: () => api.getReviewCards(jobId),
          staleTime: 30 * 1000,
        });
      });
  }, [notifications, queryClient]);

  const dismissReview = useMutation({
    mutationFn: (jobId: string) => api.dismissReview(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  // new_account_detected: classify the freshly-detected account. "De mi pareja"
  // flips it to partner (its spending drops out of the owner's totals); "Es mía"
  // just acknowledges. Either way the notification is marked actioned.
  const classifyNewAccount = useMutation({
    mutationFn: async ({ notif, asPartner }: { notif: NotificationItem; asPartner: boolean }) => {
      const p = notif.payload;
      if (asPartner && p?.account_id && p?.household_id) {
        await api.updateBankAccount(p.account_id, p.household_id, { account_type: "partner" });
      }
      await api.updateNotification(notif.id, "actioned");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  // charge_attributed: the recipient confirms ("Confirmar" → acknowledge, keeps
  // the charge attributed to them) or rejects ("No es mío" → reject, the
  // charge reverts to the sender's own ledger). Either way the notification
  // is marked actioned.
  const respondToAttribution = useMutation({
    mutationFn: async ({ notif, accept }: { notif: NotificationItem; accept: boolean }) => {
      const attributionId = notif.payload?.attribution_id;
      if (!attributionId) return;
      if (accept) {
        await api.acknowledgeAttribution(attributionId);
      } else {
        await api.rejectAttribution(attributionId);
      }
      await api.updateNotification(notif.id, "actioned");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const handleDelete = (notif: (typeof notifications)[0]) => {
    // Warn if the user is deleting a merchant_review notification that still
    // has pending merchants to review (i.e. not yet actioned/dismissed).
    const needsConfirm =
      notif.type === "merchant_review" &&
      notif.status !== "actioned" &&
      notif.status !== "dismissed";
    if (needsConfirm) {
      setPendingDelete(notif);
      return;
    }
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
    <div className="space-y-6">
      <PageHeader
        title="Notificaciones"
        subtitle="Alertas y actividad reciente"
        actions={
          notifications.some((n) => n.status === "unread") ? (
            <button
              onClick={handleMarkAllRead}
              aria-label="Marcar todas leídas"
              className="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-slate-200 bg-white hover:border-luka-primary hover:-translate-y-px transition-all shadow-[var(--shadow-card)] text-xs font-semibold text-slate-700"
            >
              <CheckCheck size={14} />
              <span>Marcar leídas</span>
            </button>
          ) : undefined
        }
      />

      {/* Shared-card charges awaiting the four-way sort. Self-hides when empty.
          Lives here (the notification center) rather than the dashboard. */}
      <PorClasificar />

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
                    <NotifDetail notif={notif} />
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

                {!isDone && notif.type === "new_account_detected" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => classifyNewAccount.mutate({ notif, asPartner: true })}
                      disabled={classifyNewAccount.isPending}
                      className="px-4 py-2 bg-purple-600 text-white text-xs font-semibold rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                    >
                      Es de mi pareja
                    </button>
                    <button
                      onClick={() => classifyNewAccount.mutate({ notif, asPartner: false })}
                      disabled={classifyNewAccount.isPending}
                      className="px-4 py-2 border border-slate-200 text-xs text-slate-500 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      Es mía
                    </button>
                  </div>
                )}

                {!isDone && notif.type === "charge_attributed" && (
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => respondToAttribution.mutate({ notif, accept: true })}
                      disabled={respondToAttribution.isPending || !notif.payload?.attribution_id}
                      className="px-4 py-2 bg-purple-600 text-white text-xs font-semibold rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
                    >
                      Confirmar
                    </button>
                    <button
                      onClick={() => respondToAttribution.mutate({ notif, accept: false })}
                      disabled={respondToAttribution.isPending || !notif.payload?.attribution_id}
                      className="px-4 py-2 border border-slate-200 text-xs text-slate-500 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      No es mío
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <AlertDialog open={!!pendingDelete} onOpenChange={(v) => { if (!v) setPendingDelete(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar sin revisar?</AlertDialogTitle>
            <AlertDialogDescription>
              Aún tienes comercios por revisar en esta notificación. Si la eliminas, perderás acceso rápido a esa revisión. Puedes usar &quot;Omitir&quot; para descartarla correctamente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingDelete) deleteNotification.mutate(pendingDelete.id);
                setPendingDelete(null);
              }}
              className="bg-red-500 hover:bg-red-600 text-white"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
