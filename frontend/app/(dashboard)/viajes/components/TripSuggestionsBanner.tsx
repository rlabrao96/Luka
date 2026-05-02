"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, X } from "lucide-react";
import {
  useDismissSuggestion,
  useSuggestedTransactions,
} from "@/app/lib/hooks/useTrips";
import {
  api,
  type SuggestedTransaction,
  type TripDetail,
} from "@/app/lib/api";
import {
  formatStoredAmount,
  isZeroDecimalCurrency,
} from "@/app/lib/currency";
import AddExpenseSheet, { type AddExpensePrefill } from "./AddExpenseSheet";

interface TripSuggestionsBannerProps {
  trip: TripDetail;
}

function formatShortDate(iso: string): string {
  const [y, m, d] = iso.split("T")[0].split("-").map(Number);
  if (!y || !m || !d) return iso;
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("es-CL", { day: "numeric", month: "short" });
}

/**
 * Yellow inline banner that appears at the top of the Resumen / Gastos tabs
 * when the backend returns transactions whose date falls inside the trip
 * window but aren't yet linked to any trip expense. Each row offers three
 * actions: equal-split add, custom add, or per-row dismiss.
 *
 * Renders nothing while loading or when the list is empty, so it's cheap to
 * keep mounted in both tabs.
 */
export default function TripSuggestionsBanner({
  trip,
}: TripSuggestionsBannerProps) {
  const { data: suggestions, isLoading } = useSuggestedTransactions(trip.id);
  const dismiss = useDismissSuggestion(trip.id);
  const [collapsed, setCollapsed] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [prefill, setPrefill] = useState<AddExpensePrefill | undefined>();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const myAttendeeId = useMemo(() => {
    if (!me) return null;
    return (
      trip.attendees.find((a) => a.user_id === me.id && a.left_at === null)
        ?.id ?? null
    );
  }, [me, trip.attendees]);

  function buildPrefill(
    s: SuggestedTransaction,
    splitEqual: boolean,
  ): AddExpensePrefill {
    // Transactions store non-zero-decimal currencies in cents; trip expenses
    // use major units. Convert before seeding the form.
    const stored = Math.abs(Number(s.amount));
    const major = isZeroDecimalCurrency(s.currency) ? stored : stored / 100;
    const decimals = isZeroDecimalCurrency(s.currency) ? 0 : 2;
    return {
      description: s.merchant ?? "",
      amount: Number.isFinite(major) ? major.toFixed(decimals) : "",
      currency: s.currency,
      expense_date: s.transaction_date.split("T")[0],
      transaction_id: s.transaction_id,
      payer_attendee_id: myAttendeeId ?? undefined,
      all_split_equal: splitEqual,
      source_caption: `Vinculado a tu transacción del ${formatShortDate(
        s.transaction_date,
      )}${s.merchant ? ` · ${s.merchant}` : ""}`,
    };
  }

  function openWithPrefill(s: SuggestedTransaction, splitEqual: boolean) {
    setPrefill(buildPrefill(s, splitEqual));
    setSheetOpen(true);
  }

  if (isLoading) return null;
  const items = suggestions ?? [];
  if (items.length === 0) return null;
  if (collapsed) return null;

  return (
    <>
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 sm:p-4 mb-4">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
            <Sparkles size={16} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-semibold text-amber-900">
                {items.length}{" "}
                {items.length === 1
                  ? "transacción durante este viaje no agregada"
                  : "transacciones durante este viaje no agregadas"}
              </p>
              <button
                type="button"
                onClick={() => setCollapsed(true)}
                aria-label="Ocultar sugerencias"
                className="text-amber-700/70 hover:text-amber-900 shrink-0 p-0.5 -m-0.5"
              >
                <X size={14} />
              </button>
            </div>
            <p className="text-[11px] text-amber-800/80 mt-0.5">
              Agrégalas como gasto del viaje o descártalas.
            </p>

            <ul className="mt-3 space-y-2">
              {items.map((s) => (
                <li
                  key={s.transaction_id}
                  className="rounded-lg border border-amber-200 bg-white px-3 py-2.5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-luka-dark truncate">
                        {s.merchant ?? "Sin comercio"}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {formatShortDate(s.transaction_date)}
                        {s.category ? ` · ${s.category}` : ""}
                      </p>
                    </div>
                    <p className="text-sm font-semibold tabular-nums text-red-600 shrink-0">
                      {formatStoredAmount(
                        Math.abs(Number(s.amount)),
                        s.currency,
                      )}
                    </p>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => openWithPrefill(s, true)}
                      className="text-[11px] font-semibold px-2.5 py-1 rounded-md bg-luka-primary text-white hover:bg-blue-700 transition-colors"
                    >
                      Agregar (división igual)
                    </button>
                    <button
                      type="button"
                      onClick={() => openWithPrefill(s, false)}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      Personalizar
                    </button>
                    <button
                      type="button"
                      onClick={() => dismiss.mutate(s.transaction_id)}
                      disabled={dismiss.isPending}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      Descartar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <AddExpenseSheet
        tripId={trip.id}
        trip={trip}
        open={sheetOpen}
        onOpenChange={(o) => {
          setSheetOpen(o);
          if (!o) setPrefill(undefined);
        }}
        prefill={prefill}
      />
    </>
  );
}
