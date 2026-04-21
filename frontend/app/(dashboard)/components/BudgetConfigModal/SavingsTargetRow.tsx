"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Target, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { formatMoney, type Currency } from "@/app/lib/format";
import { AccordionRow } from "./AccordionRow";
import { CURRENCY_OPTIONS, isSupportedCurrency } from "./currencies";

interface Props {
  expanded: boolean;
  onToggle: (id: "savings") => void;
}

export function SavingsTargetRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  const defaultCurrency = isSupportedCurrency(me?.preferred_currency)
    ? me.preferred_currency
    : "CLP";

  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>(defaultCurrency);
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setAmount(
      current.savings_target_amount != null ? String(current.savings_target_amount) : ""
    );
    setCurrency(current.savings_target_currency ?? defaultCurrency);
  }, [current, defaultCurrency]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: amount ? Number(amount) : null,
        savings_target_currency: amount ? currency : null,
        payday_day_of_month: current?.payday_day_of_month ?? null,
        personal_allocation_amount: current?.personal_allocation_amount ?? null,
        personal_allocation_currency: current?.personal_allocation_currency ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budgetSettings"] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2"] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  return (
    <AccordionRow
      id="savings"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "savings")}
      icon={<Target size={20} />}
      label="Meta de ahorro"
      valuePrimary={
        current?.savings_target_amount != null
          ? formatMoney(
              current.savings_target_amount,
              (current?.savings_target_currency ?? defaultCurrency) as Currency
            )
          : "Sin meta"
      }
      valueUnit={
        current?.savings_target_amount != null
          ? `${current.savings_target_currency ?? defaultCurrency} / mes`
          : undefined
      }
      empty={current?.savings_target_amount == null}
      savedTick={savedTick}
    >
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Ej. 300000"
          className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary font-[var(--font-geist-mono)]"
        />
        <select
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          className="w-20 rounded-[11px] border border-slate-200 px-2 py-2.5 text-[12px] font-[var(--font-geist-mono)] font-medium text-slate-500 bg-white text-center"
        >
          {CURRENCY_OPTIONS.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Transacciones en categorías de ahorro/inversión cuentan hacia esta meta.
      </p>
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar"}
        </button>
        {savedTick > 0 && !errorMsg && (
          <span
            key={savedTick}
            className="text-[11.5px] text-emerald-600 font-semibold inline-flex items-center gap-1 animate-in fade-in-0 slide-in-from-left-1 duration-[240ms]"
          >
            <Check size={12} strokeWidth={3} />
            Guardado
          </span>
        )}
        {errorMsg && <span className="text-[11.5px] text-red-500">{errorMsg}</span>}
      </div>
    </AccordionRow>
  );
}
