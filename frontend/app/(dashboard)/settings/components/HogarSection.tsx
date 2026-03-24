"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function HogarSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);

  const { data: summary } = useQuery({
    queryKey: ["household-summary", householdId],
    queryFn: () => api.getHouseholdSummary(householdId!),
    enabled: !!householdId,
  });

  const members = summary ?? [];
  const isCoupleHousehold = members.length > 1;
  const sorted = [...members].sort((a: any, b: any) =>
    a.user_id === userId ? -1 : b.user_id === userId ? 1 : 0
  );

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
        {sorted.map((member) => (
          <div key={member.user_id} className="flex items-center justify-between">
            <span className="text-sm text-slate-500">
              {member.user_id === userId ? "Tú" : "Pareja"}
            </span>
            <div className="text-right">
              <p className="text-sm font-medium text-slate-700">{member.full_name}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
