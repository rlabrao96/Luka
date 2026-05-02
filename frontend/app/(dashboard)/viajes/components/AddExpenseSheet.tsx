"use client";

import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateExpense } from "@/app/lib/hooks/useTrips";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  api,
  type TripDetail,
  type TripAttendee,
  type SplitInput,
  type CreateExpenseInput,
} from "@/app/lib/api";

interface AddExpenseSheetProps {
  tripId: string;
  trip: TripDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ShareMode = "equal" | "custom_amount" | "custom_percent";

function todayISO(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

/**
 * Bottom-sheet (mobile) / centered dialog (desktop) for creating a trip
 * expense. The shared `Dialog` already adapts via Tailwind breakpoints, so
 * one component covers both modes. The actual form lives in a child that's
 * mounted only when `open` is true, so its initial-state factories own
 * "reset on open" — no effect needed.
 *
 * v1 scope: single currency (locked to trip.base_currency); no "Vincular
 * transacción" picker (deferred to Phase 7.7); no edit (Phase 7.5+).
 */
export default function AddExpenseSheet({
  tripId,
  trip,
  open,
  onOpenChange,
}: AddExpenseSheetProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nuevo gasto</DialogTitle>
        </DialogHeader>
        {open && (
          <ExpenseForm
            tripId={tripId}
            trip={trip}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface ExpenseFormProps {
  tripId: string;
  trip: TripDetail;
  onClose: () => void;
}

function ExpenseForm({ tripId, trip, onClose }: ExpenseFormProps) {
  const createMutation = useCreateExpense(tripId);
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const activeAttendees = useMemo<TripAttendee[]>(
    () => trip.attendees.filter((a) => a.left_at === null),
    [trip.attendees],
  );

  const myAttendeeId = me
    ? activeAttendees.find((a) => a.user_id === me.id)?.id ?? null
    : null;

  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [expenseDate, setExpenseDate] = useState<string>(() => todayISO());
  const [payerId, setPayerId] = useState<string>(
    () => myAttendeeId ?? activeAttendees[0]?.id ?? "",
  );
  const [shareMode, setShareMode] = useState<ShareMode>("equal");
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(activeAttendees.map((a) => a.id)),
  );
  const [customAmounts, setCustomAmounts] = useState<Record<string, string>>({});
  const [customPercents, setCustomPercents] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const amountNum = Number(amount);
  const isAmountValid = !Number.isNaN(amountNum) && amountNum > 0;

  const customAmountSum = useMemo(() => {
    let sum = 0;
    for (const id of selected) {
      const v = Number(customAmounts[id]);
      if (!Number.isNaN(v)) sum += v;
    }
    return sum;
  }, [customAmounts, selected]);

  const customPercentSum = useMemo(() => {
    let sum = 0;
    for (const id of selected) {
      const v = Number(customPercents[id]);
      if (!Number.isNaN(v)) sum += v;
    }
    return sum;
  }, [customPercents, selected]);

  const customAmountMatches =
    isAmountValid && Math.abs(customAmountSum - amountNum) < 0.01;
  const customPercentMatches = Math.abs(customPercentSum - 100) < 0.01;

  function toggleAttendee(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function validate(): string | null {
    if (!description.trim()) return "Ingresa una descripción.";
    if (description.length > 500) return "La descripción es demasiado larga.";
    if (!isAmountValid) return "Ingresa un monto válido mayor a 0.";
    if (!payerId) return "Selecciona quién pagó.";
    if (!expenseDate) return "Ingresa una fecha.";
    if (selected.size === 0) return "Selecciona al menos un asistente.";
    if (shareMode === "custom_amount" && !customAmountMatches) {
      return "Los montos por persona deben sumar al total.";
    }
    if (shareMode === "custom_percent" && !customPercentMatches) {
      return "Los porcentajes deben sumar 100%.";
    }
    return null;
  }

  function buildSplits(): SplitInput[] {
    const ids = Array.from(selected);
    if (shareMode === "equal") {
      return ids.map((id) => ({ attendee_id: id, share_type: "equal" }));
    }
    if (shareMode === "custom_amount") {
      return ids.map((id) => ({
        attendee_id: id,
        share_type: "custom_amount",
        share_amount: (Number(customAmounts[id]) || 0).toFixed(2),
      }));
    }
    return ids.map((id) => ({
      attendee_id: id,
      share_type: "custom_percent",
      share_percent: (Number(customPercents[id]) || 0).toFixed(2),
    }));
  }

  async function handleSubmit() {
    setError(null);
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    const body: CreateExpenseInput = {
      payer_attendee_id: payerId,
      description: description.trim(),
      amount: amountNum.toFixed(2),
      currency: trip.base_currency,
      expense_date: expenseDate,
      splits: buildSplits(),
    };
    try {
      await createMutation.mutateAsync(body);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("No pudimos guardar el gasto. Intenta de nuevo.");
    }
  }

  const isPending = createMutation.isPending;
  const dateOutOfRange =
    expenseDate &&
    (expenseDate < trip.start_date || expenseDate > trip.end_date);

  return (
    <div className="space-y-4 pt-1">
      <Field label="Descripción">
        <Input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
          placeholder="Cena en restaurante"
          disabled={isPending}
          className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
        />
      </Field>

      <div className="grid grid-cols-[1fr_auto] gap-2">
        <Field label="Monto">
          <Input
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            disabled={isPending}
            className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
          />
        </Field>
        <Field label="Moneda">
          <div className="h-11 sm:h-10 px-3 rounded-lg border border-slate-200 bg-slate-50 text-slate-600 text-sm flex items-center font-medium">
            {trip.base_currency}
          </div>
        </Field>
      </div>

      <Field label="Fecha">
        <Input
          type="date"
          value={expenseDate}
          onChange={(e) => setExpenseDate(e.target.value)}
          disabled={isPending}
          className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
        />
        {dateOutOfRange && (
          <p className="text-[11px] text-amber-600 mt-1">
            La fecha está fuera del rango del viaje.
          </p>
        )}
      </Field>

      <Field label="Pagado por">
        <select
          value={payerId}
          onChange={(e) => setPayerId(e.target.value)}
          disabled={isPending}
          className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700 bg-white"
        >
          {activeAttendees.map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name}
              {a.id === myAttendeeId ? " (yo)" : ""}
            </option>
          ))}
        </select>
      </Field>

      <Field label="División">
        <div className="grid grid-cols-3 gap-1.5">
          {(["equal", "custom_amount", "custom_percent"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setShareMode(mode)}
              disabled={isPending}
              className={
                "h-9 rounded-lg text-xs font-semibold border transition-colors " +
                (shareMode === mode
                  ? "bg-luka-primary text-white border-luka-primary"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50")
              }
            >
              {mode === "equal" && "Igual"}
              {mode === "custom_amount" && "Por monto"}
              {mode === "custom_percent" && "Por %"}
            </button>
          ))}
        </div>
      </Field>

      <Field label="Asistentes">
        <div className="flex flex-wrap gap-1.5">
          {activeAttendees.map((a) => {
            const isOn = selected.has(a.id);
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => toggleAttendee(a.id)}
                disabled={isPending}
                className={
                  "text-xs font-medium px-3 py-1.5 rounded-full border transition-colors " +
                  (isOn
                    ? "bg-blue-50 text-blue-700 border-blue-200"
                    : "bg-white text-slate-500 border-slate-200 hover:bg-slate-50")
                }
              >
                {a.display_name}
              </button>
            );
          })}
        </div>
      </Field>

      {shareMode === "custom_amount" && selected.size > 0 && (
        <div className="space-y-2">
          {Array.from(selected).map((id) => {
            const a = activeAttendees.find((x) => x.id === id);
            if (!a) return null;
            return (
              <div key={id} className="flex items-center gap-2">
                <span className="flex-1 text-xs text-slate-600 truncate">
                  {a.display_name}
                </span>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  value={customAmounts[id] ?? ""}
                  onChange={(e) =>
                    setCustomAmounts((prev) => ({ ...prev, [id]: e.target.value }))
                  }
                  placeholder="0.00"
                  disabled={isPending}
                  className="h-9 w-28 text-sm rounded-lg"
                />
              </div>
            );
          })}
          <p
            className={
              "text-[11px] " +
              (isAmountValid && customAmountMatches
                ? "text-emerald-600"
                : "text-red-600")
            }
          >
            Suma: {customAmountSum.toFixed(2)} /{" "}
            {isAmountValid ? amountNum.toFixed(2) : "—"}
          </p>
        </div>
      )}
      {shareMode === "custom_percent" && selected.size > 0 && (
        <div className="space-y-2">
          {Array.from(selected).map((id) => {
            const a = activeAttendees.find((x) => x.id === id);
            if (!a) return null;
            return (
              <div key={id} className="flex items-center gap-2">
                <span className="flex-1 text-xs text-slate-600 truncate">
                  {a.display_name}
                </span>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  max="100"
                  value={customPercents[id] ?? ""}
                  onChange={(e) =>
                    setCustomPercents((prev) => ({ ...prev, [id]: e.target.value }))
                  }
                  placeholder="0"
                  disabled={isPending}
                  className="h-9 w-24 text-sm rounded-lg"
                />
                <span className="text-xs text-slate-400 w-3">%</span>
              </div>
            );
          })}
          <p
            className={
              "text-[11px] " +
              (customPercentMatches ? "text-emerald-600" : "text-red-600")
            }
          >
            Suma: {customPercentSum.toFixed(2)}% / 100%
          </p>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          onClick={onClose}
          disabled={isPending}
          className="flex-1 sm:flex-initial h-11 sm:h-10"
        >
          Cancelar
        </Button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isPending}
          className="flex-1 px-4 h-11 sm:h-10 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {isPending ? "Guardando..." : "Guardar gasto"}
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
