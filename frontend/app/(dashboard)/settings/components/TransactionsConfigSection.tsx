"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
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
  const [removingCode, setRemovingCode] = useState<string | null>(null);
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

  const handleDelete = (code: string) => {
    setRemovingCode(code);
    // Let the 180ms fade-out play before the row disappears from the list.
    setTimeout(() => {
      deleteCurrency.mutate(code, {
        onSettled: () => setRemovingCode(null),
      });
    }, 180);
  };

  const activeCodes = new Set(userCurrencies.map((c) => c.currency_code));
  const available = SUPPORTED_CURRENCIES.filter((c) => !activeCodes.has(c.code));
  const canRemove = userCurrencies.length > 1;

  const nameByCode = new Map(SUPPORTED_CURRENCIES.map((c) => [c.code, c.name]));

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5 space-y-6">
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
              {c.code} — {c.name}
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-400 pt-1">
          {saved
            ? "Guardado"
            : mutation.isPending
              ? "Guardando..."
              : "Se usa como moneda por defecto en toda la app"}
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

        <ul className="mt-3 rounded-xl border border-slate-100 overflow-hidden divide-y divide-slate-100 bg-white">
          {[...userCurrencies]
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((c) => {
              const name = nameByCode.get(c.currency_code) ?? "";
              const isRemoving = removingCode === c.currency_code;
              return (
                <li
                  key={c.currency_code}
                  className={`flex items-center justify-between gap-3 pl-4 pr-1.5 transition-all duration-200 ${
                    isRemoving ? "opacity-0 -translate-x-2" : "opacity-100"
                  }`}
                >
                  <div className="min-w-0 flex-1 py-3">
                    <p className="text-sm font-semibold text-slate-800 tabular-nums leading-tight">
                      {c.currency_code}
                    </p>
                    <p className="text-xs text-slate-400 truncate leading-tight mt-0.5">
                      {name}
                    </p>
                  </div>
                  {c.is_primary ? (
                    <span className="mr-2.5 shrink-0 inline-flex items-center px-2 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-blue-50 text-blue-700">
                      Principal
                    </span>
                  ) : canRemove ? (
                    <button
                      type="button"
                      onClick={() => handleDelete(c.currency_code)}
                      disabled={isRemoving || deleteCurrency.isPending}
                      aria-label={`Eliminar ${c.currency_code}`}
                      className="shrink-0 w-11 h-11 flex items-center justify-center rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 active:bg-red-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Trash2 size={18} strokeWidth={1.75} />
                    </button>
                  ) : null}
                </li>
              );
            })}
        </ul>

        {available.length > 0 && (
          <div className="pt-4 space-y-1">
            <label className="block text-xs font-medium text-slate-500">
              Agregar moneda
            </label>
            <div className="relative w-full sm:w-64">
              <Plus
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
              />
              <select
                value=""
                onChange={(e) => {
                  if (e.target.value) addCurrency.mutate(e.target.value);
                }}
                disabled={addCurrency.isPending}
                className="w-full rounded-xl border border-slate-200 pl-9 pr-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-50"
              >
                <option value="">Selecciona una moneda</option>
                {available.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
