"use client";

import { Switch } from "@/components/ui/switch";
import { useLukaStore } from "@/app/lib/store";

export function FeatureTogglesSection() {
  const showCuotaButton = useLukaStore((s) => s.showCuotaButton);
  const setShowCuotaButton = useLukaStore((s) => s.setShowCuotaButton);

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Funciones
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Activa funciones adicionales en el historial de transacciones.
        </p>
      </div>

      <label
        htmlFor="toggle-cuota-button"
        className="flex items-start justify-between gap-4 rounded-xl border border-slate-100 px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-luka-dark">
            Marcar como cuota
          </p>
          <p className="text-xs text-luka-muted mt-0.5 leading-snug">
            Muestra un botón para convertir un gasto en cuotas mensuales desde el historial.
          </p>
        </div>
        <Switch
          id="toggle-cuota-button"
          checked={showCuotaButton}
          onCheckedChange={setShowCuotaButton}
          aria-label="Mostrar botón Marcar como cuota"
        />
      </label>
    </div>
  );
}
