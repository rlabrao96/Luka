"use client";

import { useCurrencies } from "@/app/lib/hooks/useCurrencies";
import type { UserCurrency } from "@/app/lib/api";

interface CurrencyToggleProps {
  value: string;
  onChange: (currency: string) => void;
  /** Optional override — otherwise reads from user preferences via useCurrencies(). */
  currencies?: UserCurrency[];
  /** Render nothing if the user only has one currency enabled. Default true. */
  hideWhenSingle?: boolean;
}

export function CurrencyToggle({
  value,
  onChange,
  currencies: override,
  hideWhenSingle = true,
}: CurrencyToggleProps) {
  const { data: fetched } = useCurrencies();
  const currencies = override ?? fetched ?? [];
  if (currencies.length === 0) return null;
  if (hideWhenSingle && currencies.length === 1) return null;

  const sorted = [...currencies].sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div role="group" aria-label="Moneda" className="flex gap-1">
      {sorted.map((c) => {
        const active = c.currency_code === value;
        return (
          <button
            key={c.currency_code}
            type="button"
            onClick={() => onChange(c.currency_code)}
            aria-pressed={active}
            className={`min-h-9 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary ${
              active
                ? "bg-luka-primary text-white"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200"
            }`}
          >
            {c.currency_code}
            {c.is_primary && (
              <span aria-label="Moneda principal" title="Moneda principal" className="ml-1">
                ★
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
