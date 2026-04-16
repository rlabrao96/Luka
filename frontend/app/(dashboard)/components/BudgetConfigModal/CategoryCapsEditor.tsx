"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X, Check } from "lucide-react";
import { api, type BudgetV2Response } from "@/app/lib/api";
import { getCategoryPill } from "@/app/lib/category-icons";
import { CategoryCapPicker } from "./CategoryCapPicker";

interface Props {
  householdId: string;
  month: string;
  householdBudget: BudgetV2Response | undefined;
  onSaved: () => void;
}

function formatSpend(n: number, currency: string): string {
  if (currency === "USD") {
    return `US$${(n / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

/** Derive per-category spend from the Sankey `spent_<cat>` nodes. */
function spendByCategoryFrom(budget: BudgetV2Response | undefined): Record<string, number> {
  if (!budget) return {};
  const map: Record<string, number> = {};
  for (const node of budget.sankey.nodes) {
    if (node.id.startsWith("spent_")) {
      const cat = node.label ?? node.id.slice("spent_".length);
      map[cat] = Math.abs(Number(node.value) || 0);
    }
  }
  return map;
}

export function CategoryCapsEditor({
  householdId,
  month,
  householdBudget,
  onSaved,
}: Props) {
  const queryClient = useQueryClient();

  const prefs = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: 5 * 60 * 1000,
  });
  const budgets = useQuery({
    queryKey: ["category-budgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId, month),
  });

  // Local draft: category → amount as a string. Only includes
  // categories the user intends to cap (uncapped categories are absent).
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [pickerOpen, setPickerOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedTick, setSavedTick] = useState(0);

  useEffect(() => {
    if (!budgets.data) return;
    const seed: Record<string, string> = {};
    for (const b of budgets.data.budgets) {
      if (b.amount > 0) seed[b.category] = String(b.amount);
    }
    setDraft(seed);
  }, [budgets.data]);

  const allExpenseCategories = useMemo(
    () =>
      (prefs.data?.categories ?? [])
        .filter((c) => c.category_type === "expense")
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((c) => c.category),
    [prefs.data]
  );

  const spendByCategory = useMemo(
    () => spendByCategoryFrom(householdBudget),
    [householdBudget]
  );

  const currency = householdBudget?.currency ?? "CLP";

  const mutation = useMutation({
    mutationFn: () => {
      const items = Object.entries(draft)
        .map(([category, raw]) => ({ category, amount: raw ? Number(raw) : 0 }))
        .filter((b) => b.amount > 0);
      return api.setCategoryBudgets(householdId, { month, budgets: items });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-budgets", householdId, month] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2", householdId] });
      setErrorMsg(null);
      setSavedTick((n) => n + 1);
      onSaved();
    },
    onError: (e: Error) => {
      setErrorMsg(e.message ?? "Error al guardar. Intenta de nuevo.");
    },
  });

  const activeCaps = Object.keys(draft);
  const excluded = new Set(activeCaps);

  function handlePick(category: string) {
    setDraft((d) => ({ ...d, [category]: "" }));
    setPickerOpen(false);
    // Scroll focus to the new row on the next tick.
    setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>(
        `input[data-cap-input="${category}"]`
      );
      el?.focus();
    }, 60);
  }

  function handleRemove(category: string) {
    setDraft((d) => {
      const next = { ...d };
      delete next[category];
      return next;
    });
  }

  function handleChange(category: string, raw: string) {
    setDraft((d) => ({ ...d, [category]: raw }));
  }

  const isLoading = prefs.isPending || budgets.isPending;

  return (
    <div>
      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-12 rounded-[11px] bg-slate-100 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          {activeCaps.map((category) => {
            const icon = getCategoryPill(category);
            const spend = spendByCategory[category] ?? 0;
            return (
              <div
                key={category}
                className="grid grid-cols-[32px_1fr_130px_26px] items-center gap-2.5 px-2.5 py-2 rounded-[11px] bg-slate-50 border border-slate-100 hover:border-slate-200 hover:bg-white transition-all animate-in fade-in-0 zoom-in-[.98] duration-200"
              >
                <span
                  className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                  style={{ background: icon.gradient }}
                >
                  {icon.emoji}
                </span>
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium text-luka-dark truncate">
                    {category}
                  </div>
                  {spend > 0 && (
                    <div className="text-[10.5px] text-slate-500">
                      Gastado: {formatSpend(spend, currency)}
                    </div>
                  )}
                </div>
                <input
                  type="number"
                  inputMode="numeric"
                  min="0"
                  data-cap-input={category}
                  value={draft[category]}
                  onChange={(e) => handleChange(category, e.target.value)}
                  placeholder="Tu tope"
                  className="w-full rounded-[9px] bg-white border border-slate-200 px-2.5 py-1.5 text-[12.5px] text-right font-[var(--font-geist-mono)] text-luka-dark focus:outline-none focus:ring-2 focus:ring-luka-primary/20 focus:border-luka-primary placeholder:italic placeholder:text-slate-400"
                />
                <button
                  type="button"
                  onClick={() => handleRemove(category)}
                  aria-label={`Quitar tope de ${category}`}
                  className="w-6 h-6 rounded-[8px] flex items-center justify-center text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}

          <button
            type="button"
            onClick={() => setPickerOpen((v) => !v)}
            className="w-full mt-2 py-2.5 px-3.5 rounded-[12px] border border-dashed border-slate-300 text-[13px] font-semibold text-luka-primary hover:border-luka-primary hover:border-solid hover:bg-luka-primary/[0.04] transition-all flex items-center justify-center gap-1.5"
          >
            <Plus size={16} strokeWidth={2.4} />
            Agregar tope
          </button>

          {pickerOpen && (
            <CategoryCapPicker
              allCategories={allExpenseCategories}
              spendByCategory={spendByCategory}
              excluded={excluded}
              onPick={handlePick}
              formatSpend={(n) => formatSpend(n, currency)}
            />
          )}

          <p className="text-[11.5px] text-slate-500 mt-2 leading-[1.45]">
            Sólo se muestran las categorías con tope activo. Toca <strong>+ Agregar tope</strong> para incluir otra.
          </p>
        </div>
      )}

      <div className="flex items-center gap-2.5 mt-3.5">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || isLoading}
          className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4 py-2.5 shadow-[0_2px_8px_rgba(37,99,235,0.25)] hover:bg-luka-primary-dark transition-all disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando…" : "Guardar topes"}
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
    </div>
  );
}
