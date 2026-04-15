"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

function currentMonthParam(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function CategoryBudgetsSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();
  const month = useMemo(() => currentMonthParam(), []);

  const prefs = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: 5 * 60 * 1000,
  });
  const budgets = useQuery({
    queryKey: ["category-budgets", householdId, month],
    queryFn: () => api.getCategoryBudgets(householdId as string, month),
    enabled: !!householdId,
  });

  // Category name -> input value (string so empty state works)
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (budgets.data) {
      const seed: Record<string, string> = {};
      for (const b of budgets.data.budgets) {
        seed[b.category] = String(b.amount);
      }
      setDraft(seed);
    }
  }, [budgets.data]);

  const expenseCategories = useMemo(() => {
    const cats = prefs.data?.categories ?? [];
    return cats
      .filter((c) => c.category_type === "expense")
      .sort((a, b) => a.sort_order - b.sort_order);
  }, [prefs.data]);

  const mutation = useMutation({
    mutationFn: () => {
      const items = Object.entries(draft)
        .map(([category, raw]) => ({
          category,
          amount: raw ? Number(raw) : 0,
        }))
        .filter((b) => b.amount > 0);
      return api.setCategoryBudgets(householdId as string, { month, budgets: items });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-budgets", householdId, month] });
      queryClient.invalidateQueries({ queryKey: ["budget-v2", householdId] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  if (!householdId) return null;

  const isLoading = prefs.isPending || budgets.isPending;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">
        Presupuestos por categoría
      </h3>
      <p className="text-xs text-slate-400 mb-4">
        Define un tope mensual por categoría. El motor de riesgo usa estos topes
        para detectar sobregiros antes de que ocurran.
      </p>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-10 rounded-lg bg-slate-100 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {expenseCategories.map((c) => (
            <div key={c.category} className="flex items-center gap-3">
              <label className="flex-1 text-sm text-slate-700">{c.category}</label>
              <input
                type="number"
                inputMode="numeric"
                min="0"
                placeholder="Sin tope"
                value={draft[c.category] ?? ""}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, [c.category]: e.target.value }))
                }
                className="w-40 rounded-xl border border-slate-200 px-3 py-2 text-sm text-right tabular-nums bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          ))}
          {expenseCategories.length === 0 && (
            <p className="text-xs text-slate-400">
              No hay categorías de gasto configuradas. Agrégalas en la sección de
              categorías más abajo.
            </p>
          )}
        </div>
      )}

      <div className="flex items-center gap-3 pt-4">
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || isLoading}
          className="rounded-xl bg-luka-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          {mutation.isPending ? "Guardando..." : "Guardar topes"}
        </button>
        {saved && <span className="text-xs text-emerald-600">Guardado</span>}
        {mutation.isError && (
          <span className="text-xs text-red-500">
            Error al guardar. Intenta de nuevo.
          </span>
        )}
      </div>
    </div>
  );
}
