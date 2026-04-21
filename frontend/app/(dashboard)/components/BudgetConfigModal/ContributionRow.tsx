"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Home, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import { formatMoney, type Currency } from "@/app/lib/format";
import { AccordionRow } from "./AccordionRow";
import { CURRENCY_OPTIONS, isSupportedCurrency } from "./currencies";

type Mode = "full" | "fixed" | "reimbursement";

interface Props {
  expanded: boolean;
  onToggle: (id: "contribution") => void;
}

const MODE_LABELS: Record<Mode, string> = {
  full: "Completa",
  fixed: "Fija",
  reimbursement: "Reembolso",
};

const MODE_HELPERS: Record<Mode, string> = {
  full: "Mi ingreso real se suma al pot del hogar. Si prefieres mantener tu sueldo privado, elige Fija.",
  fixed: "Aporto un monto mensual fijo. Mi ingreso real queda privado — nadie más en el hogar lo verá.",
  reimbursement: "No aporto al pot. Mis gastos se llevan aparte y se reembolsan al final del mes.",
};

export function ContributionRow({ expanded, onToggle }: Props) {
  const queryClient = useQueryClient();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  const defaultCurrency = isSupportedCurrency(me?.preferred_currency)
    ? me.preferred_currency
    : "CLP";

  const [mode, setMode] = useState<Mode>("full");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState<string>(defaultCurrency);
  const [savedTick, setSavedTick] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!me) return;
    setMode((me.contribution_mode as Mode | null) ?? "full");
    // fixed_contribution_amount is a quantized string from the backend
    // (e.g. "800000.00"). Strip any trailing ".00" so the input field shows
    // a clean integer for CLP, but leave non-zero decimals alone for USD.
    setAmount(
      me.fixed_contribution_amount != null
        ? me.fixed_contribution_amount.replace(/\.00$/, "")
        : ""
    );
    setCurrency(me.fixed_contribution_currency ?? defaultCurrency);
  }, [me, defaultCurrency]);

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
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  const currentMode: Mode | null = (me?.contribution_mode as Mode | null) ?? null;
  const currentFixedAmountNum =
    me?.fixed_contribution_amount != null ? Number(me.fixed_contribution_amount) : null;
  const valuePrimary =
    currentMode === "fixed"
      ? `Fija (${
          currentFixedAmountNum != null
            ? formatMoney(
                currentFixedAmountNum,
                (me?.fixed_contribution_currency ?? defaultCurrency) as Currency
              )
            : ""
        })`
      : currentMode === "reimbursement"
        ? "Sólo reembolso"
        : "Completa";
  const valueUnit =
    currentMode === "fixed"
      ? "ingreso real queda privado"
      : currentMode === "reimbursement"
        ? "no aporta al pot"
        : "ingreso real se suma";

  const fixedInvalid =
    mode === "fixed" && (!amount || Number(amount) <= 0 || Number.isNaN(Number(amount)));

  return (
    <AccordionRow
      id="contribution"
      expanded={expanded}
      onToggle={(id) => onToggle(id as "contribution")}
      icon={<Home size={20} />}
      label="Aporte al hogar"
      valuePrimary={valuePrimary}
      valueUnit={valueUnit}
      empty={currentMode == null}
      savedTick={savedTick}
    >
      <div className="grid grid-cols-3 gap-1.5 bg-slate-100 p-1 rounded-[12px]">
        {(["full", "fixed", "reimbursement"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`
              rounded-[9px] py-2.5 px-2 text-[12px] font-semibold transition-all
              ${mode === m
                ? "bg-white text-luka-dark shadow-[0_1px_2px_rgba(0,0,0,0.04),0_0_0_1px_rgba(37,99,235,0.22)]"
                : "text-slate-500 hover:text-slate-700"}
            `}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>
      <div className="text-[11.5px] text-slate-600 mt-2.5 py-2.5 px-3 bg-slate-50 rounded-[10px] border-l-2 border-luka-primary leading-[1.45]">
        {MODE_HELPERS[mode]}
      </div>
      {mode === "fixed" && (
        <div className="flex gap-2 mt-3">
          <input
            type="number"
            inputMode="numeric"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Ej. 800000"
            className="flex-1 rounded-[11px] border border-slate-200 px-3 py-2.5 text-sm bg-white font-[var(--font-geist-mono)] focus:outline-none focus:ring-4 focus:ring-luka-primary/10 focus:border-luka-primary"
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
      )}
      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || fixedInvalid}
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
