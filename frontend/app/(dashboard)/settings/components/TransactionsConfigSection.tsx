"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

const CURRENCIES = [
  { value: "CLP", label: "CLP — Peso chileno" },
  { value: "USD", label: "USD — Dólar estadounidense" },
];

export function TransactionsConfigSection({
  preferredCurrency,
}: {
  preferredCurrency: string;
}) {
  const [currency, setCurrency] = useState(preferredCurrency);
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (value: string) =>
      api.updateProfile({ preferred_currency: value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleChange = (value: string) => {
    setCurrency(value);
    mutation.mutate(value);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Transacciones
      </h3>
      <div className="space-y-1">
        <label className="block text-xs font-medium text-slate-500">
          Moneda preferida
        </label>
        <select
          value={currency}
          onChange={(e) => handleChange(e.target.value)}
          disabled={mutation.isPending}
          className="w-full sm:w-64 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-50"
        >
          {CURRENCIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-slate-400 pt-1">
          {saved
            ? "Guardado"
            : mutation.isPending
              ? "Guardando..."
              : "Se usará como moneda por defecto en la vista de transacciones"}
        </p>
        {mutation.isError && (
          <p className="text-xs text-red-500">Error al guardar. Intenta de nuevo.</p>
        )}
      </div>
    </div>
  );
}
