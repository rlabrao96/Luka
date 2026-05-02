"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import type { TripDetail } from "@/app/lib/api";
import { api } from "@/app/lib/api";
import ExpenseRow from "./ExpenseRow";
import TripSuggestionsBanner from "./TripSuggestionsBanner";

interface GastosTabProps {
  trip: TripDetail;
  onAddExpense: () => void;
}

type Filter = "all" | "mine";

/**
 * Gastos tab — vertical list of ExpenseRow, newest first. The optional
 * "Solo míos" filter resolves the current Luka user to their attendee
 * via attendees[].user_id and keeps only expenses they paid for.
 */
export default function GastosTab({ trip, onAddExpense }: GastosTabProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const myAttendeeId = useMemo(() => {
    if (!me) return null;
    return trip.attendees.find((a) => a.user_id === me.id)?.id ?? null;
  }, [me, trip.attendees]);

  const expenses = useMemo(() => {
    const sorted = [...trip.expenses].sort((a, b) => {
      if (a.expense_date !== b.expense_date) {
        return a.expense_date < b.expense_date ? 1 : -1;
      }
      return a.created_at < b.created_at ? 1 : -1;
    });
    if (filter === "mine" && myAttendeeId) {
      return sorted.filter((e) => e.payer_attendee_id === myAttendeeId);
    }
    return sorted;
  }, [trip.expenses, filter, myAttendeeId]);

  if (trip.expenses.length === 0) {
    return (
      <div className="space-y-3">
        <TripSuggestionsBanner trip={trip} />
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center space-y-4">
        <p className="text-sm text-luka-dark font-semibold">
          Aún no hay gastos en este viaje.
        </p>
        <p className="text-xs text-slate-500 max-w-xs mx-auto">
          Agrega el primero para empezar a dividir.
        </p>
        <button
          type="button"
          onClick={onAddExpense}
          className="inline-flex items-center gap-1.5 h-10 px-4 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
        >
          <Plus size={16} />
          Agregar gasto
        </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <TripSuggestionsBanner trip={trip} />
      <div className="flex items-center gap-2">
        <FilterChip
          label="Todos"
          active={filter === "all"}
          onClick={() => setFilter("all")}
        />
        <FilterChip
          label="Solo míos"
          active={filter === "mine"}
          onClick={() => setFilter("mine")}
          disabled={!myAttendeeId}
        />
      </div>
      {expenses.length === 0 ? (
        <p className="text-xs text-slate-400 text-center py-6">
          Sin gastos para este filtro.
        </p>
      ) : (
        <div className="space-y-2">
          {expenses.map((e) => (
            <ExpenseRow
              key={e.id}
              expense={e}
              attendees={trip.attendees}
              tripBaseCurrency={trip.base_currency}
              tripId={trip.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
  disabled,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={
        "h-7 px-3 rounded-full text-xs font-medium border transition-colors disabled:opacity-50 " +
        (active
          ? "bg-luka-primary text-white border-luka-primary"
          : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50")
      }
    >
      {label}
    </button>
  );
}
