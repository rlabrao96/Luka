"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { useRouter } from "next/navigation";
import { createClient } from "@/app/lib/supabase/client";

export function DeleteAccountSection() {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const router = useRouter();
  const reset = useLukaStore((s) => s.reset);

  const mutation = useMutation({
    mutationFn: () => api.deleteAccount(),
    onSuccess: async () => {
      const supabase = createClient();
      await supabase.auth.signOut();
      reset();
      router.push("/login");
    },
  });

  const canDelete = confirmation === "ELIMINAR";

  return (
    <>
      <div className="bg-white rounded-xl border border-red-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Zona de peligro
        </h3>
        <p className="text-sm text-slate-500 mb-4">
          Al eliminar tu cuenta se borrarán permanentemente todos tus datos, transacciones y configuración.
        </p>
        <button
          onClick={() => setOpen(true)}
          className="px-5 py-2 text-sm text-red-600 font-medium border border-red-200 rounded-xl hover:bg-red-50 hover:border-red-300 transition-colors"
        >
          Eliminar cuenta
        </button>
      </div>

      <BottomSheet open={open} onClose={() => { setOpen(false); setConfirmation(""); }}>
        <div className="p-5 space-y-4">
          <h3 className="text-lg font-semibold text-slate-900">Eliminar cuenta</h3>
          <p className="text-sm text-slate-600">
            Esto es irreversible. Se eliminarán todos tus datos: transacciones, cuentas
            bancarias, presupuestos y configuración.
          </p>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Escribe ELIMINAR para confirmar
            </label>
            <input
              type="text"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              placeholder="ELIMINAR"
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
            />
          </div>
          <button
            onClick={() => mutation.mutate()}
            disabled={!canDelete || mutation.isPending}
            className="w-full py-2.5 bg-red-600 text-white text-sm font-medium rounded-xl disabled:opacity-40 hover:bg-red-700 transition-colors"
          >
            {mutation.isPending ? "Eliminando..." : "Eliminar cuenta permanentemente"}
          </button>
          {mutation.isError && (
            <p className="text-xs text-red-500">Error al eliminar. Intenta de nuevo.</p>
          )}
        </div>
      </BottomSheet>
    </>
  );
}
