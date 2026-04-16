"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

const CURRENCIES = [
  { value: "CLP", label: "CLP — Peso chileno" },
  { value: "USD", label: "USD — Dólar estadounidense" },
  { value: "COP", label: "COP — Peso colombiano" },
  { value: "BRL", label: "BRL — Real brasileño" },
  { value: "MXN", label: "MXN — Peso mexicano" },
  { value: "ARS", label: "ARS — Peso argentino" },
  { value: "PEN", label: "PEN — Sol peruano" },
  { value: "UYU", label: "UYU — Peso uruguayo" },
  { value: "PYG", label: "PYG — Guaraní paraguayo" },
  { value: "BOB", label: "BOB — Boliviano" },
  { value: "VES", label: "VES — Bolívar venezolano" },
  { value: "DOP", label: "DOP — Peso dominicano" },
  { value: "GTQ", label: "GTQ — Quetzal guatemalteco" },
  { value: "HNL", label: "HNL — Lempira hondureño" },
  { value: "NIO", label: "NIO — Córdoba nicaragüense" },
  { value: "CRC", label: "CRC — Colón costarricense" },
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
          Moneda principal
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
