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
          type="button"
          onClick={() => setSearchOpen((v) => !v)}
          aria-label="Abrir búsqueda"
          aria-expanded={searchOpen}
          className="w-11 h-11 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
        >
          <Search size={18} className="text-slate-500" />
        </button>
        <button
          type="button"
          onClick={() => setFiltersOpen((v) => !v)}
          aria-label={`Abrir filtros${activeCount > 0 ? ` (${activeCount} activos)` : ""}`}
          aria-expanded={filtersOpen}
          className="relative w-11 h-11 flex items-center justify-center bg-white border border-slate-200 rounded-[10px] shadow-[var(--shadow-card)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
        >
          <SlidersHorizontal size={18} className="text-slate-500" />
          {activeCount > 0 && (
            <span
              aria-hidden
              className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-luka-primary text-white text-[9px] font-bold flex items-center justify-center"
            >
              {activeCount}
            </span>
          )}
        </button>
      </div>

      {/* Mobile search bar — text-base (16px) avoids iOS zoom-on-focus */}
      {searchOpen && (
        <div className="lg:hidden">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              autoFocus
              placeholder="Buscar comercio, banco o categoría..."
              aria-label="Buscar"
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full h-11 pl-9 pr-11 rounded-lg border border-slate-200 bg-white text-base text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
            />
            <button
              type="button"
              onClick={() => { setSearchOpen(false); onSearchChange(""); }}
              aria-label="Cerrar búsqueda"
              className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-md text-slate-400 hover:bg-slate-100"
            >
              <X size={16} />
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
