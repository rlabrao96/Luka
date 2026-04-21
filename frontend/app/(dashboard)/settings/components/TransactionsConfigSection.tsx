"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { SUPPORTED_CURRENCIES } from "@/app/lib/currency";
import {
  useCurrencies,
  useAddCurrency,
  useDeleteCurrency,
} from "@/app/lib/hooks/useCurrencies";

export function TransactionsConfigSection({
  preferredCurrency,
}: {
  preferredCurrency: string;
}) {
  const [currency, setCurrency] = useState(preferredCurrency);
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();

  const { data: userCurrencies = [] } = useCurrencies();
  const addCurrency = useAddCurrency();
  const deleteCurrency = useDeleteCurrency();

  const mutation = useMutation({
    mutationFn: (value: string) =>
      api.updateProfile({ preferred_currency: value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["currencies"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handlePreferredChange = (value: string) => {
    setCurrency(value);
    mutation.mutate(value);
  };

  const activeCodes = new Set(userCurrencies.map((c) => c.currency_code));
  const available = SUPPORTED_CURRENCIES.filter((c) => !activeCodes.has(c.code));
  const canRemove = userCurrencies.length > 1;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5 space-y-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
        Monedas
      </h3>

      <div className="space-y-1">
        <label className="block text-xs font-medium text-slate-500">
          Moneda principal
        </label>
        <select
          value={currency}
          onChange={(e) => handlePreferredChange(e.target.value)}
          disabled={mutation.isPending}
          className="w-full sm:w-64 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-50"
        >
          {SUPPORTED_CURRENCIES.map((c) => (
            <option key={c.code} value={c.code}>
              ★ {c.code} — {c.name}
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-400 pt-1">
          {saved
            ? "Guardado"
            : mutation.isPending
              ? "Guardando..."
              : "Se marca con ★ y se usa como moneda por defecto en toda la app"}
        </p>
        {mutation.isError && (
          <p className="text-xs text-red-500">Error al guardar. Intenta de nuevo.</p>
        )}
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-slate-500">
          Monedas activas
        </label>
        <p className="text-xs text-slate-400">
          Monedas disponibles en los filtros de Transacciones, Presupuesto, Dashboard, Suscripciones y Compartido.
        </p>

        <div className="flex flex-wrap gap-1.5 pt-1">
          {[...userCurrencies]
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((c) => (
              <span
                key={c.currency_code}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700"
              >
                {c.currency_code}
                {c.is_primary && (
                  <span
                    aria-label="Moneda principal"
                    title="Moneda principal"
                    className="text-[9px] opacity-60 font-bold"
                  >
                    ★
                  </span>
                )}
                {canRemove && !c.is_primary && (
                  <button
                    type="button"
                    onClick={() => deleteCurrency.mutate(c.currency_code)}
                    className="opacity-60 hover:opacity-100 leading-none"
                    aria-label={`Eliminar ${c.currency_code}`}
                  >
                    ×
                  </button>
                )}
              </span>
            ))}
        </div>

        {available.length > 0 && (
          <div className="pt-2">
            <label className="block text-xs font-medium text-slate-500 mb-1">
              Agregar moneda
            </label>
            <select
              value=""
              onChange={(e) => {
                if (e.target.value) addCurrency.mutate(e.target.value);
              }}
              disabled={addCurrency.isPending}
              className="w-full sm:w-64 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-50"
            >
              <option value="">— Selecciona una moneda —</option>
              {available.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
