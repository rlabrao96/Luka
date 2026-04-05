"use client";
import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

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

export function MonthSelector({ value, onChange, currentMonth }: MonthSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const options = getMonthOptions();

  const selectedLabel = options.find((o) => o.key === value)?.label ?? value;
  const isViewingPast = value !== currentMonth;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold border transition-colors ${
          isViewingPast
            ? "bg-blue-50 border-blue-200 text-blue-600"
            : "bg-white border-slate-200 text-slate-800 shadow-sm"
        }`}
      >
        {selectedLabel}
        <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[160px] bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => { onChange(opt.key); setOpen(false); }}
              className={`w-full text-left px-4 py-2.5 text-sm flex items-center justify-between transition-colors ${
                opt.key === value
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              {opt.label}
              {opt.key === value && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
