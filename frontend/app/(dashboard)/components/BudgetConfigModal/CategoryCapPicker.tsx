"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { getCategoryPill } from "@/app/lib/category-icons";

export interface PickerCategory {
  category: string;
  spend: number; // absolute value, same currency as the caller
}

export interface CategoryCapPickerProps {
  /** Every expense category in the user's category preferences. */
  allCategories: string[];
  /** Per-category spend this month, derived from the budget-v2 query. */
  spendByCategory: Record<string, number>;
  /** Categories already present in the caps list — excluded from the picker. */
  excluded: Set<string>;
  /** Called with the picked category name. */
  onPick: (category: string) => void;
  /** Currency symbol prefix, e.g. "$" or "US$". */
  formatSpend: (n: number) => string;
}

export function CategoryCapPicker({
  allCategories,
  spendByCategory,
  excluded,
  onPick,
  formatSpend,
}: CategoryCapPickerProps) {
  const [search, setSearch] = useState("");

  const candidates: PickerCategory[] = useMemo(() => {
    return allCategories
      .filter((c) => !excluded.has(c))
      .map((c) => ({ category: c, spend: spendByCategory[c] ?? 0 }))
      .sort((a, b) => b.spend - a.spend);
  }, [allCategories, spendByCategory, excluded]);

  const { suggested, other } = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const matches = needle
      ? candidates.filter((c) => c.category.toLowerCase().includes(needle))
      : candidates;
    return {
      suggested: matches.slice(0, 5).filter((c) => c.spend > 0),
      other: matches.slice(5),
    };
  }, [candidates, search]);

  return (
    <div
      className="mt-2 bg-white border border-slate-200 rounded-[14px] shadow-[0_12px_32px_-12px_rgba(15,23,42,0.18)] overflow-hidden animate-in fade-in-0 slide-in-from-top-1 duration-200"
      role="listbox"
      aria-label="Elegir categoría"
    >
      {/* Search */}
      <div className="px-3.5 py-3 border-b border-slate-100 flex items-center gap-2">
        <Search size={16} className="text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar categoría…"
          autoFocus
          className="flex-1 text-[13.5px] bg-transparent outline-none placeholder:text-slate-400"
        />
      </div>

      <div className="max-h-72 overflow-y-auto">
        {suggested.length > 0 && (
          <>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500 px-3.5 pt-2.5 pb-1">
              Sugeridas · top {suggested.length} gasto del mes
            </div>
            {suggested.map((c, i) => {
              const icon = getCategoryPill(c.category);
              return (
                <button
                  key={c.category}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => onPick(c.category)}
                  className="w-full grid grid-cols-[32px_1fr_auto] items-center gap-2.5 px-3.5 py-2.5 text-left hover:bg-slate-50 transition-colors"
                  style={{
                    backgroundImage:
                      "linear-gradient(90deg, rgba(37,99,235,0.04), transparent)",
                  }}
                >
                  <span
                    className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                    style={{ background: icon.gradient }}
                  >
                    {icon.emoji}
                  </span>
                  <span className="text-[13.5px] font-medium text-luka-dark">
                    {c.category}
                    <span className="ml-1.5 align-middle text-[9px] font-bold uppercase tracking-[0.06em] bg-luka-primary text-white px-1.5 py-0.5 rounded">
                      top {i + 1}
                    </span>
                  </span>
                  <span className="text-[11px] text-slate-500 font-[var(--font-geist-mono)]">
                    {formatSpend(c.spend)}
                  </span>
                </button>
              );
            })}
          </>
        )}
        {other.length > 0 && (
          <>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-500 px-3.5 pt-2.5 pb-1">
              Otras
            </div>
            {other.map((c) => {
              const icon = getCategoryPill(c.category);
              return (
                <button
                  key={c.category}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => onPick(c.category)}
                  className="w-full grid grid-cols-[32px_1fr_auto] items-center gap-2.5 px-3.5 py-2.5 text-left hover:bg-slate-50 transition-colors"
                >
                  <span
                    className="w-8 h-8 rounded-[9px] flex items-center justify-center text-[14px]"
                    style={{ background: icon.gradient }}
                  >
                    {icon.emoji}
                  </span>
                  <span className="text-[13.5px] font-medium text-luka-dark">{c.category}</span>
                  <span className="text-[11px] text-slate-500 font-[var(--font-geist-mono)]">
                    {c.spend > 0 ? formatSpend(c.spend) : "—"}
                  </span>
                </button>
              );
            })}
          </>
        )}
        {suggested.length === 0 && other.length === 0 && (
          <div className="px-3.5 py-4 text-center text-[12px] text-slate-500">
            No hay categorías disponibles.
          </div>
        )}
      </div>
      <div className="px-3.5 py-2.5 border-t border-slate-100 bg-[#FAFBFF] text-[11px] text-slate-500">
        {candidates.length} categoría{candidates.length === 1 ? "" : "s"} restante{candidates.length === 1 ? "" : "s"}
      </div>
    </div>
  );
}
