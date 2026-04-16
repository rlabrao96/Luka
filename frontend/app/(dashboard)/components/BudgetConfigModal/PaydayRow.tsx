"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calendar, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { AccordionRow } from "./AccordionRow";

interface Props {
  expanded: boolean;
  onToggle: (id: "payday") => void;
}

export function PaydayRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: current } = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
  });

  const [day, setDay] = useState("");
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return;
    setDay(
      current.payday_day_of_month != null ? String(current.payday_day_of_month) : ""
    );
  }, [current]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBudgetSettings({
        savings_target_amount: current?.savings_target_amount ?? null,
        savings_target_currency: current?.savings_target_currency ?? null,
        payday_day_of_month: day ? Number(day) : null,
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
      id="payday"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "payday")}
      icon={<Calendar size={20} />}
      label="Día de pago"
      valuePrimary={
        current?.payday_day_of_month != null
          ? `Día ${current.payday_day_of_month}`
          : "Sin configurar"
      }
      valueUnit={current?.payday_day_of_month != null ? "de cada mes" : undefined}
      empty={current?.payday_day_of_month == null}
      savedTick={savedTick}
    >
      <select
        value={day}
        onChange={(e) => setDay(e.target.value)}
        className="w-full sm:w-32 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white font-[var(--font-geist-mono)] focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary"
      >
        <option value="">—</option>
        {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
        Se usa para calcular los días restantes hasta el próximo sueldo.
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
