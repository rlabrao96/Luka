"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export type ContributionMode = "full" | "fixed" | "reimbursement";

const MODE_OPTIONS: { value: ContributionMode; label: string; helper: string }[] = [
  {
    value: "full",
    label: "Completa",
    helper: "Mi ingreso real se suma al pot del hogar.",
  },
  {
    value: "fixed",
    label: "Fija",
    helper: "Aporto un monto mensual definido; mi ingreso real queda privado.",
  },
  {
    value: "reimbursement",
    label: "Sólo reembolso",
    helper: "Llevo mis gastos aparte; no aporto al pot.",
  },
];

export function ContributionSection({
  currentMode = "full",
  currentAmount = null,
  currentCurrency = null,
}: {
  currentMode?: ContributionMode;
  currentAmount?: number | null;
  currentCurrency?: string | null;
}) {
  const [mode, setMode] = useState<ContributionMode>(currentMode);
  const [amount, setAmount] = useState<string>(
    currentAmount !== null ? String(currentAmount) : ""
  );
  const [currency, setCurrency] = useState<string>(currentCurrency ?? "CLP");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.updateContribution({
        mode,
        fixed_amount: mode === "fixed" ? Number(amount) : null,
        fixed_currency: mode === "fixed" ? currency : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      queryClient.invalidateQueries({ queryKey: ["household-summary"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setSaved(true);
      setError(null);
      setTimeout(() => setSaved(false), 2000);
    },
    onError: (e: Error) => {
      setError(e.message ?? "No se pudo guardar");
    },
  });

  const fixedInvalid =
    mode === "fixed" && (!amount || Number(amount) <= 0 || Number.isNaN(Number(amount)));

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">
        Aporte al hogar
      </h3>
      <p className="text-xs text-slate-400 mb-4">
        Define cómo cuenta tu ingreso para el presupuesto compartido.
      </p>

      <fieldset className="space-y-2">
        {MODE_OPTIONS.map((opt) => {
          const active = mode === opt.value;
          return (
            <label
              key={opt.value}
              className={`flex items-start gap-3 rounded-xl border px-3 py-3 cursor-pointer transition ${
                active
                  ? "border-blue-500 bg-blue-50/40"
                  : "border-slate-200 hover:border-slate-300"
              }`}
            >
              <input
                type="radio"
                name="contribution-mode"
                value={opt.value}
                checked={active}
                onChange={() => setMode(opt.value)}
                className="mt-1 accent-blue-600"
              />
              <div className="flex-1">
                <p className="text-sm font-medium text-slate-700">{opt.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{opt.helper}</p>
              </div>
            </label>
          );
        })}
      </fieldset>

      {mode === "fixed" && (
        <div className="mt-4 space-y-2">
          <label className="block text-xs font-medium text-slate-500">
            Monto mensual
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="numeric"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Ej. 800000"
              className="flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-28 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              <option value="CLP">CLP</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <p className="text-xs text-slate-400">
            Tu ingreso real queda privado — nadie más en el hogar lo verá.
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || fixedInvalid}
          className="rounded-xl bg-luka-primary text-white px-4 py-2 text-sm font-semibold disabled:opacity-60 hover:bg-luka-primary/90 transition"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {saved && (
          <span className="text-xs text-emerald-600 font-medium">Guardado</span>
        )}
        {error && <span className="text-xs text-red-500">{error}</span>}
      </div>

      {/* TODO(Chunk D follow-up): seed currentMode/currentAmount/currentCurrency
          from the household-summary endpoint once it returns those fields. */}
    </div>
  );
}
