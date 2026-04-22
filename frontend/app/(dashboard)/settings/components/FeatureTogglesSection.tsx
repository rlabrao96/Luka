"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Switch } from "@/components/ui/switch";
import { useLukaStore } from "@/app/lib/store";
import { api } from "@/app/lib/api";

export function FeatureTogglesSection() {
  const showCuotaButton = useLukaStore((s) => s.showCuotaButton);
  const setShowCuotaButton = useLukaStore((s) => s.setShowCuotaButton);

  const queryClient = useQueryClient();
  const { data, isLoading: waLoading } = useQuery({
    queryKey: ["notification-preferences"],
    queryFn: () => api.getNotificationPreferences(),
  });

  const waMutation = useMutation({
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

  const whatsappEnabled = data?.whatsapp_enabled ?? true;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Funciones
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Activa o desactiva funciones de la app.
        </p>
      </div>

      <div className="space-y-2">
        <label
          htmlFor="toggle-whatsapp"
          className={`flex items-start justify-between gap-4 rounded-xl border border-slate-100 px-4 py-3 transition-colors ${
            waLoading ? "opacity-50" : "cursor-pointer hover:bg-slate-50"
          }`}
        >
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-luka-dark">
              Notificaciones por WhatsApp
            </p>
            <p className="text-xs text-luka-muted mt-0.5 leading-snug">
              Recibe alertas y clasifica transacciones respondiendo desde WhatsApp.
            </p>
          </div>
          <Switch
            id="toggle-whatsapp"
            checked={whatsappEnabled}
            onCheckedChange={(v) => waMutation.mutate(v)}
            disabled={waLoading}
            aria-label="Notificaciones por WhatsApp"
          />
        </label>

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
    </div>
  );
}
