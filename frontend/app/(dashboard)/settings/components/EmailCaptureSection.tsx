"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, Mail, RefreshCw } from "lucide-react";
import { api } from "@/app/lib/api";
import { resolveAppLocale } from "@/app/lib/locale";

function relativeHours(iso: string | null): string | null {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 1) return "hace menos de 1 h";
  if (hours < 48) return `hace ${hours} h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} días`;
}

export function EmailCaptureSection() {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["email-watch-status"],
    queryFn: () => api.getEmailWatchStatus(),
    staleTime: 60 * 1000,
  });

  const relink = useMutation({
    mutationFn: () => api.setupEmailWatch(),
    onSettled: () => qc.invalidateQueries({ queryKey: ["email-watch-status"] }),
  });

  if (status.isPending || !status.data) return null;

  const s = status.data;
  const healthy = s.tokens_connected && s.watch_active;
  const lastCapture = relativeHours(s.last_email_transaction_at);
  const providerLabel = s.provider === "outlook" ? "Outlook" : "Gmail";
  const expiry = s.watch_expiry
    ? new Date(s.watch_expiry).toLocaleDateString(resolveAppLocale(), {
        day: "numeric",
        month: "short",
      })
    : null;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Captura de correos
      </h3>
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            healthy ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"
          }`}
        >
          {healthy ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-luka-dark flex items-center gap-1.5">
            <Mail size={14} className="text-slate-400" />
            {providerLabel}
            {healthy ? (
              <span className="text-emerald-600 text-xs font-semibold">activo</span>
            ) : (
              <span className="text-amber-600 text-xs font-semibold">
                {s.tokens_connected ? "vigilancia vencida" : "sin conexión"}
              </span>
            )}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {healthy && lastCapture && `Última transacción capturada ${lastCapture}.`}
            {healthy && !lastCapture && "Aún no capturamos transacciones desde tu correo."}
            {healthy && expiry && ` Vigilancia renovada hasta el ${expiry}.`}
            {!healthy &&
              s.tokens_connected &&
              "La vigilancia de tu correo venció — reconéctala para seguir capturando gastos automáticamente."}
            {!healthy &&
              !s.tokens_connected &&
              "Google revocó el acceso a tu correo. Cierra sesión y vuelve a entrar con Google para reconectar."}
          </p>
          {!healthy && s.tokens_connected && (
            <button
              type="button"
              onClick={() => relink.mutate()}
              disabled={relink.isPending}
              className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-luka-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              <RefreshCw size={13} className={relink.isPending ? "animate-spin" : ""} />
              {relink.isPending ? "Reconectando…" : "Reconectar"}
            </button>
          )}
          {relink.isError && (
            <p className="mt-1.5 text-xs text-red-600">
              No pudimos reconectar. Cierra sesión y vuelve a entrar con Google.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
