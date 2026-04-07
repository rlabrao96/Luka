"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function CompartidoSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);

  const { data: summary } = useQuery({
    queryKey: ["household-summary", householdId],
    queryFn: () => api.getHouseholdSummary(householdId!),
    enabled: !!householdId,
  });

  const members = summary ?? [];
  const isCoupleHousehold = members.length > 1;
  const me = members.find((m) => m.user_id === userId);

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Compartido
      </h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">Tipo</span>
          <span className="text-sm font-medium text-slate-700">
            {isCoupleHousehold ? "Grupo" : "Individual"}
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

        {/* Members list */}
        {members.map((member) => {
          if (member.user_id === userId) return null; // Skip current user since shown above
          return (
            <div key={member.user_id} className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Miembro</span>
              <div className="text-right">
                <p className="text-sm font-medium text-slate-700">{member.full_name}</p>
                <p className="text-xs text-slate-400">{member.email}</p>
                <span className="text-xs text-emerald-600 font-medium">Activo</span>
              </div>
            </div>
          );
        })}

        {/* Invite info */}
        {!isCoupleHousehold && (
          <div className="pt-2 border-t border-slate-50">
            <p className="text-xs text-slate-400">
              Invita miembros desde la página Compartido
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
