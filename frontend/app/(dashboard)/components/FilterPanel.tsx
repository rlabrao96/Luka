"use client";
import { useState } from "react";
import { SlidersHorizontal, Search, X } from "lucide-react";

/** Hook lifting the FilterPanel's open state so pages can render the
 *  triggers and the collapsible body in separate DOM slots (e.g. triggers
 *  inside the PageHeader controls row; body below the header). */
export function useFilterPanel() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  return {
    searchOpen,
    filtersOpen,
    toggleSearch: () => setSearchOpen((v) => !v),
    toggleFilters: () => setFiltersOpen((v) => !v),
    openSearch: () => setSearchOpen(true),
    closeSearch: () => setSearchOpen(false),
    closeFilters: () => setFiltersOpen(false),
  };
}

export interface FilterPanelTriggersProps {
  searchOpen: boolean;
  filtersOpen: boolean;
  onToggleSearch: () => void;
  onToggleFilters: () => void;
  activeCount: number;
}

/** Two 36px-tall icon chips (search + filters) — sized to match the
 *  currency / month chips so they can all flex-wrap in the same controls
 *  row. Hidden on lg+ (desktop inlines the filters directly). */
export function FilterPanelTriggers({
  searchOpen,
  filtersOpen,
  onToggleSearch,
  onToggleFilters,
  activeCount,
}: FilterPanelTriggersProps) {
  return (
    <div className="flex items-center gap-2 lg:hidden">
      <button
        type="button"
        onClick={onToggleSearch}
        aria-label="Abrir búsqueda"
        aria-expanded={searchOpen}
        className="w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-lg shadow-[var(--shadow-card)] hover:border-luka-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
      >
        <Search size={16} className="text-slate-500" />
      </button>
      <button
        type="button"
        onClick={onToggleFilters}
        aria-label={`Abrir filtros${activeCount > 0 ? ` (${activeCount} activos)` : ""}`}
        aria-expanded={filtersOpen}
        className="relative w-9 h-9 flex items-center justify-center bg-white border border-slate-200 rounded-lg shadow-[var(--shadow-card)] hover:border-luka-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
      >
        <SlidersHorizontal size={16} className="text-slate-500" />
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
  );
}

export interface FilterPanelBodyProps {
  searchOpen: boolean;
  filtersOpen: boolean;
  onCloseSearch: () => void;
  onCloseFilters: () => void;
  searchValue: string;
  onSearchChange: (v: string) => void;
  activeCount: number;
  onClear: () => void;
  children: React.ReactNode;
}

/** Mobile: conditional search bar + conditional filter panel.
 *  Desktop: always-visible inline row (search input + children). */
export function FilterPanelBody({
  searchOpen,
  filtersOpen,
  onCloseSearch,
  onCloseFilters,
  searchValue,
  onSearchChange,
  activeCount,
  onClear,
  children,
}: FilterPanelBodyProps) {
  return (
    <>
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
              onClick={() => { onCloseSearch(); onSearchChange(""); }}
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
              onClick={() => { onClear(); onCloseFilters(); }}
              className="text-xs text-luka-primary font-medium hover:underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {/* Desktop filters — always visible inline row below the header */}
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
