"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export function ProfileSection({
  user,
}: {
  user: { full_name: string; email: string; phone_whatsapp: string | null };
}) {
  const [name, setName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone_whatsapp ?? "");
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();
  const setUser = useLukaStore((s) => s.setUser);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateProfile({
        full_name: name,
        phone_whatsapp: phone || undefined,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setUser(data.id, data.full_name);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const hasChanges = name !== user.full_name || phone !== (user.phone_whatsapp ?? "");

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Perfil
      </h3>
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Nombre</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Email</label>
          <p className="px-3 py-2.5 text-sm text-slate-400 bg-slate-50 rounded-xl">
            {user.email}
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">WhatsApp</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+56 9 1234 5678"
            className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={!hasChanges || mutation.isPending}
          className="w-full sm:w-auto px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-blue-700 transition-colors"
        >
          {mutation.isPending ? "Guardando..." : saved ? "Guardado" : "Guardar cambios"}
        </button>
        {mutation.isError && (
          <p className="text-xs text-red-500 mt-1">Error al guardar. Intenta de nuevo.</p>
        )}
      </div>
    </div>
  );
}
