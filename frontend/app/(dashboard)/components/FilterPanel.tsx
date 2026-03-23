"use client";
import { useState } from "react";
import { SlidersHorizontal, Search, X } from "lucide-react";

interface FilterPanelProps {
  activeCount: number;
  onClear: () => void;
  searchValue: string;
  onSearchChange: (v: string) => void;
  children: React.ReactNode;
}

export function FilterPanel({
  activeCount,
  onClear,
  searchValue,
  onSearchChange,
  children,
}: FilterPanelProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <>
      {/* Mobile header buttons — hidden on lg+ */}
      <div className="flex items-center gap-2 lg:hidden">
        <button
          onClick={() => setSearchOpen((v) => !v)}
          className="w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)]"
        >
          <Search size={16} className="text-slate-500" />
        </button>
        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="relative w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)]"
        >
          <SlidersHorizontal size={16} className="text-slate-500" />
          {activeCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-luka-primary text-white text-[9px] font-bold flex items-center justify-center">
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {/* Mobile search bar */}
      {searchOpen && (
        <div className="lg:hidden">
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              autoFocus
              placeholder="Buscar comercio, banco o categoría..."
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full h-9 pl-8 pr-9 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
            />
            <button
              onClick={() => { setSearchOpen(false); onSearchChange(""); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Mobile collapsible filter panel */}
      {filtersOpen && (
        <div className="lg:hidden bg-white rounded-xl border border-slate-100 p-4 shadow-[var(--shadow-card)] space-y-3">
          {children}
          {activeCount > 0 && (
            <button
              onClick={() => { onClear(); setFiltersOpen(false); }}
              className="text-xs text-luka-primary font-medium hover:underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {/* Desktop filters — always visible */}
      <div className="hidden lg:flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar comercio, banco o categoría..."
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full h-8 pl-8 pr-3 rounded-lg border border-slate-200 bg-white text-[11px] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
          />
        </div>
        {children}
      </div>
    </>
  );
}
