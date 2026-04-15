"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

const CURRENCIES = [
  { value: "CLP", label: "CLP" },
  { value: "USD", label: "USD" },
];

export function BudgetSettingsSection() {
  const queryClient = useQueryClient();
  const { data: current, isLoading } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("CLP");
  const [payday, setPayday] = useState("");
  const [personalAllocation, setPersonalAllocation] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (current) {
      setAmount(
        current.savings_target_amount != null
          ? String(current.savings_target_amount)
          : ""
      );
      setCurrency(current.savings_target_currency ?? "CLP");
      setPayday(
        current.payday_day_of_month != null
          ? String(current.payday_day_of_month)
          : ""
      );
      setPersonalAllocation(
        current.personal_allocation_amount != null
          ? String(current.personal_allocation_amount)
          : ""
      );
    }
  }, [current]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: amount ? Number(amount) : null,
        savings_target_currency: amount ? currency : null,
        payday_day_of_month: payday ? Number(payday) : null,
        personal_allocation_amount: personalAllocation ? Number(personalAllocation) : null,
        personal_allocation_currency: personalAllocation ? currency : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgetSettings"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Presupuesto y día de sueldo
      </h3>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">
            Meta mensual de ahorro
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="numeric"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Ej. 300000"
              className="flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-24 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              {CURRENCIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-xs text-slate-400 pt-1">
            Transacciones en categorías de ahorro/inversión cuentan hacia esta meta.
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">
            Gasto personal mensual (opcional)
          </label>
          <div className="flex gap-2">
            <input
              type="number"
              inputMode="numeric"
              min="0"
              value={personalAllocation}
              onChange={(e) => setPersonalAllocation(e.target.value)}
              placeholder="Ej. 200000"
              className="flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <div className="w-24 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-slate-50 text-slate-500 flex items-center">
              {currency}
            </div>
          </div>
          <p className="text-xs text-slate-400 pt-1">
            Monto que reservas para gasto personal cada mes. Aparece como un nodo &quot;Gasto personal&quot; en el Sankey del hogar.
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">
            Día de pago (1–31)
          </label>
          <select
            value={payday}
            onChange={(e) => setPayday(e.target.value)}
            className="w-full sm:w-32 rounded-xl border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            <option value="">—</option>
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-400 pt-1">
            Se usa para calcular los días restantes hasta el próximo sueldo.
          </p>
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || isLoading}
            className="rounded-xl bg-luka-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {mutation.isPending ? "Guardando..." : "Guardar"}
          </button>
          {saved && (
            <span className="text-xs text-emerald-600">Guardado</span>
          )}
          {mutation.isError && (
            <span className="text-xs text-red-500">
              Error al guardar. Intenta de nuevo.
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
