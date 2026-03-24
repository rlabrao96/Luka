"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function HogarSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ["household-summary", householdId],
    queryFn: () => api.getHouseholdSummary(householdId!),
    enabled: !!householdId,
  });

  const inviteMutation = useMutation({
    mutationFn: () => api.invitePartner(householdId!, inviteEmail),
    onSuccess: (data) => {
      setInviteLink(`${window.location.origin}/invite/${data.token}`);
      setInviteEmail("");
    },
  });

  const members = summary ?? [];
  const isCoupleHousehold = members.length > 1;
  const me = members.find((m) => m.user_id === userId);
  const partner = members.find((m) => m.user_id !== userId);

  async function handleCopy() {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Hogar
      </h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">Tipo</span>
          <span className="text-sm font-medium text-slate-700">
            {isCoupleHousehold ? "Pareja" : "Individual"}
          </span>
        </div>

        {/* Current user */}
        {me && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Tu</span>
            <div className="text-right">
              <p className="text-sm font-medium text-slate-700">{me.full_name}</p>
              <p className="text-xs text-slate-400">{me.email}</p>
            </div>
          </div>
        )}

        {/* Partner (if exists) */}
        {partner && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Pareja</span>
            <div className="text-right">
              <p className="text-sm font-medium text-slate-700">{partner.full_name}</p>
              <p className="text-xs text-slate-400">{partner.email}</p>
              <span className="text-xs text-emerald-600 font-medium">Activo</span>
            </div>
          </div>
        )}

        {/* Invite partner (if no partner yet) */}
        {!isCoupleHousehold && !inviteLink && (
          <div className="pt-2 border-t border-slate-50 space-y-2">
            <p className="text-xs text-slate-400">Invita a tu pareja para compartir gastos</p>
            <div className="flex gap-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="Email de tu pareja"
                className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <button
                onClick={() => inviteMutation.mutate()}
                disabled={!inviteEmail || inviteMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-blue-700 transition-colors whitespace-nowrap"
              >
                {inviteMutation.isPending ? "Generando..." : "Invitar"}
              </button>
            </div>
            {inviteMutation.isError && (
              <p className="text-xs text-red-500">Error al generar invitación. Intenta de nuevo.</p>
            )}
          </div>
        )}

        {/* Invite link to copy/share */}
        {inviteLink && (
          <div className="pt-2 border-t border-slate-50 space-y-2">
            <p className="text-xs text-emerald-600 font-medium">
              Invitación creada. Comparte este enlace con tu pareja:
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={inviteLink}
                readOnly
                className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 truncate"
              />
              <button
                onClick={handleCopy}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors whitespace-nowrap"
              >
                {copied ? "Copiado" : "Copiar"}
              </button>
            </div>
            <p className="text-xs text-slate-400">
              El enlace expira en 7 días. Tu pareja debe iniciar sesión para aceptar.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
