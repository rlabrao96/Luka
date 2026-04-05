"use client";

interface CurrencyToggleProps {
  value: string;
  onChange: (currency: string) => void;
}

const CURRENCIES = ["CLP", "USD"] as const;

export function CurrencyToggle({ value, onChange }: CurrencyToggleProps) {
  return (
    <div className="flex rounded-lg border border-slate-200 overflow-hidden shadow-sm">
      {CURRENCIES.map((c) => (
        <button
          key={c}
          onClick={() => onChange(c)}
          className={`px-3 py-1.5 text-sm font-semibold transition-colors ${
            c === value
              ? "bg-blue-600 text-white"
              : "bg-white text-slate-500 hover:bg-slate-50"
          }`}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
