"use client";

interface CurrencyToggleProps {
  value: string;
  onChange: (currency: string) => void;
}

const CURRENCIES = ["CLP", "USD"] as const;

export function CurrencyToggle({ value, onChange }: CurrencyToggleProps) {
  return (
    <div className="flex gap-1">
      {CURRENCIES.map((c) => (
        <button
          key={c}
          onClick={() => onChange(c)}
          className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
            c === value
              ? "bg-luka-primary text-white"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200"
          }`}
        >
          {c}
        </button>
      ))}
    </div>
  );
}
