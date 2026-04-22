"use client";
import { useState, useRef, useEffect, useMemo } from "react";
import { ChevronDown, Check } from "lucide-react";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { localeForCurrency, resolveAppLocale } from "@/app/lib/locale";
import { useBreakpoint } from "@/app/lib/hooks/useBreakpoint";
import { getLastNMonths } from "@/app/lib/months";

interface MonthSelectorProps {
  value: string;
  onChange: (month: string) => void;
  currentMonth: string;
  /** Number of months to expose in the list. Defaults to 12 so users can pick
   *  any month in the last year without hitting a wall. */
  count?: number;
  /** Localize labels via a currency (e.g. "BRL" → pt-BR). When omitted we fall
   *  back to the browser-resolved locale. */
  currency?: string;
  /** Compact-trigger variant (smaller padding, chevron always visible). */
  size?: "sm" | "md";
}

export function MonthSelector({
  value,
  onChange,
  currentMonth,
  count = 12,
  currency,
  size = "sm",
}: MonthSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isMobile = useBreakpoint("sm");
  const locale = currency ? localeForCurrency(currency) : resolveAppLocale();
  const options = useMemo(() => getLastNMonths(locale, count), [locale, count]);

  const selectedLabel = options.find((o) => o.key === value)?.label ?? value;
  const isViewingPast = value !== currentMonth;

  useEffect(() => {
    if (isMobile) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isMobile]);

  function handleSelect(key: string) {
    onChange(key);
    setOpen(false);
  }

  const optionList = options.map((opt) => (
    <button
      key={opt.key}
      onClick={() => handleSelect(opt.key)}
      className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between transition-colors ${
        opt.key === value
          ? "bg-luka-primary text-white font-semibold"
          : "text-slate-700 hover:bg-slate-50"
      }`}
    >
      {opt.label}
      {opt.key === value && <Check size={14} />}
    </button>
  ));

  const triggerSize =
    size === "md"
      ? "h-9 px-3 text-sm"
      : "py-1 px-3 text-xs";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 rounded-lg font-semibold transition-colors whitespace-nowrap ${triggerSize} ${
          isViewingPast
            ? "bg-luka-primary text-white"
            : "bg-slate-100 text-slate-500 hover:bg-slate-200"
        }`}
      >
        {selectedLabel}
        <ChevronDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Desktop: dropdown */}
      {open && !isMobile && (
        <div className="absolute left-0 top-full mt-1 z-50 min-w-[160px] bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden">
          {optionList}
        </div>
      )}

      {/* Mobile: bottom sheet */}
      {isMobile && (
        <BottomSheet open={open} onClose={() => setOpen(false)} title="Seleccionar mes">
          {optionList}
        </BottomSheet>
      )}
    </div>
  );
}
