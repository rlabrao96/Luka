"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { User, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

interface Props {
  expanded: boolean;
  onToggle: (id: "personal") => void;
}

function formatAmount(n: number | null, currency: string | null): string {
  if (n == null) return "Sin monto";
  if (currency === "USD") return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export function PersonalAllocationRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [amount, setAmount] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setAmount(
      current.personal_allocation_amount != null
        ? String(current.personal_allocation_amount)
        : ""
    );
  }, [current]);

  const inferredCurrency = current?.savings_target_currency ?? "CLP";

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: current?.savings_target_amount ?? null,
        savings_target_currency: current?.savings_target_currency ?? null,
        payday_day_of_month: current?.payday_day_of_month ?? null,
        personal_allocation_amount: amount ? Number(amount) : null,
        personal_allocation_currency: amount ? inferredCurrency : null,
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
      id="personal"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "personal")}
      icon={<User size={20} />}
      label="Gasto personal"
      valuePrimary={formatAmount(
        current?.personal_allocation_amount ?? null,
        current?.personal_allocation_currency ?? null
      )}
      valueUnit={
        current?.personal_allocation_amount != null
          ? `${current.personal_allocation_currency ?? "CLP"} / mes`
          : undefined
      }
      empty={current?.personal_allocation_amount == null}
      savedTick={savedTick}
    >
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Ej. 200000"
          className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary font-[var(--font-geist-mono)]"
        />
        <div className="w-20 rounded-[11px] border border-slate-200 px-2 py-2.5 text-[12px] font-[var(--font-geist-mono)] font-medium text-slate-500 bg-slate-50 text-center flex items-center justify-center">
          {inferredCurrency}
        </div>
      </div>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Monto que reservas para gasto personal cada mes. Aparece como un nodo &quot;Gasto personal&quot; en el Sankey del hogar.
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
