"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { SUPPORTED_CURRENCIES } from "@/app/lib/currency";
import {
  useCurrencies,
  useAddCurrency,
  useDeleteCurrency,
} from "@/app/lib/hooks/useCurrencies";

export function TransactionsConfigSection({
  preferredCurrency: _preferredCurrency,
}: {
  preferredCurrency: string;
}) {
  const [removingCode, setRemovingCode] = useState<string | null>(null);
  const [savedBanner, setSavedBanner] = useState(false);
  const queryClient = useQueryClient();

  const { data: userCurrencies = [] } = useCurrencies();
  const addCurrency = useAddCurrency();
  const deleteCurrency = useDeleteCurrency();

  const setPrimary = useMutation({
    mutationFn: (code: string) =>
      api.updateProfile({ preferred_currency: code }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["currencies"] });
      setSavedBanner(true);
      setTimeout(() => setSavedBanner(false), 2000);
    },
  });

  const handleDelete = (code: string) => {
    setRemovingCode(code);
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

  // Primary first; others by sort_order.
  const sorted = [...userCurrencies].sort((a, b) => {
    if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
    return a.sort_order - b.sort_order;
  });

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Monedas
        </h3>
        {(savedBanner || setPrimary.isPending) && (
          <span className="text-[11px] font-medium text-blue-600">
            {setPrimary.isPending ? "Guardando…" : "Guardado"}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-400 -mt-1">
        Monedas disponibles en Transacciones, Presupuesto, Dashboard, Suscripciones y Compartido. La marcada como <span className="font-semibold text-blue-700">Principal</span> se usa como moneda por defecto en toda la app.
      </p>

      <ul className="rounded-xl border border-slate-100 overflow-hidden divide-y divide-slate-100 bg-white">
        {sorted.map((c) => {
          const name = nameByCode.get(c.currency_code) ?? "";
          const isRemoving = removingCode === c.currency_code;
          const isSettingThis =
            setPrimary.isPending && setPrimary.variables === c.currency_code;

          return (
            <li
              key={c.currency_code}
              className={`flex items-center justify-between gap-2 pl-4 pr-1.5 py-2 transition-all duration-200 ${
                isRemoving ? "opacity-0 -translate-x-2" : "opacity-100"
              } ${c.is_primary ? "bg-blue-50/40" : ""}`}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 tabular-nums leading-tight">
                  {c.currency_code}
                </p>
                <p className="text-xs text-slate-400 truncate leading-tight mt-0.5">
                  {name}
                </p>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                {c.is_primary ? (
                  <span className="inline-flex items-center gap-1 mr-2 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-blue-600 text-white">
                    <Check size={11} strokeWidth={3} />
                    Principal
                  </span>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => setPrimary.mutate(c.currency_code)}
                      disabled={setPrimary.isPending}
                      className="h-11 px-3 rounded-lg text-xs font-semibold text-blue-600 hover:bg-blue-50 active:bg-blue-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {isSettingThis ? "Guardando…" : "Hacer principal"}
                    </button>
                    {canRemove && (
                      <button
                        type="button"
                        onClick={() => handleDelete(c.currency_code)}
                        disabled={isRemoving || deleteCurrency.isPending}
                        aria-label={`Eliminar ${c.currency_code}`}
                        className="shrink-0 w-11 h-11 flex items-center justify-center rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 active:bg-red-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <Trash2 size={18} strokeWidth={1.75} />
                      </button>
                    )}
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {available.length > 0 && (
        <div className="pt-1 space-y-1">
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

      {setPrimary.isError && (
        <p className="text-xs text-red-500">Error al guardar. Intenta de nuevo.</p>
      )}
    </div>
  );
}
