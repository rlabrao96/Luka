"use client";
import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { BottomSheet } from "@/components/ui/bottom-sheet";

interface MonthSelectorProps {
  value: string;
  onChange: (month: string) => void;
  currentMonth: string;
}

function getMonthOptions(): { key: string; label: string }[] {
  const now = new Date();
  const options: { key: string; label: string }[] = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const label = d.toLocaleDateString("es-CL", { month: "short", year: "numeric" });
    options.push({ key, label: label.charAt(0).toUpperCase() + label.slice(1) });
  }
  return options;
}

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    setMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return mobile;
}

export function MonthSelector({ value, onChange, currentMonth }: MonthSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();
  const options = getMonthOptions();

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

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-semibold transition-colors whitespace-nowrap ${
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
