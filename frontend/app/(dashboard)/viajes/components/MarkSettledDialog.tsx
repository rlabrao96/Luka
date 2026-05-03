"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateSettlement } from "@/app/lib/hooks/useTrips";
import { ApiError, type TripDetail } from "@/app/lib/api";

export interface MarkSettledPrefill {
  from_attendee_id: string;
  to_attendee_id: string;
  amount: string;
  currency: string;
}

interface MarkSettledDialogProps {
  tripId: string;
  trip: TripDetail;
  prefill?: MarkSettledPrefill;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Dialog to record a settlement (manual payment between attendees).
 * Single-currency in v1: locked to trip.base_currency.
 */
export default function MarkSettledDialog({
  tripId,
  trip,
  prefill,
  open,
  onOpenChange,
}: MarkSettledDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Registrar pago</DialogTitle>
        </DialogHeader>
        {open && (
          <SettlementForm
            tripId={tripId}
            trip={trip}
            prefill={prefill}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface SettlementFormProps {
  tripId: string;
  trip: TripDetail;
  prefill?: MarkSettledPrefill;
  onClose: () => void;
}

function SettlementForm({ tripId, trip, prefill, onClose }: SettlementFormProps) {
  const createMutation = useCreateSettlement(tripId);
  const attendees = trip.attendees;

  const [fromId, setFromId] = useState<string>(
    () => prefill?.from_attendee_id ?? attendees[0]?.id ?? "",
  );
  const [toId, setToId] = useState<string>(
    () =>
      prefill?.to_attendee_id ??
      attendees.find((a) => a.id !== (prefill?.from_attendee_id ?? attendees[0]?.id))?.id ??
      "",
  );
  const [amount, setAmount] = useState<string>(() => prefill?.amount ?? "");
  const [error, setError] = useState<string | null>(null);

  // If prefill changes (e.g., user clicks a different suggestion while open),
  // hydrate the form. Effect runs only when prefill identity changes.
  useEffect(() => {
    if (prefill) {
      setFromId(prefill.from_attendee_id);
      setToId(prefill.to_attendee_id);
      setAmount(prefill.amount);
    }
  }, [prefill]);

  const amountNum = Number(amount);
  const isAmountValid = !Number.isNaN(amountNum) && amountNum > 0;

  function validate(): string | null {
    if (!fromId || !toId) return "Selecciona ambos asistentes.";
    if (fromId === toId) return "Selecciona dos asistentes distintos.";
    if (!isAmountValid) return "El monto debe ser mayor a 0.";
    return null;
  }

  function handleSubmit() {
    setError(null);
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    createMutation.mutate(
      {
        from_attendee_id: fromId,
        to_attendee_id: toId,
        amount: amountNum.toFixed(2),
        currency: trip.base_currency,
      },
      {
        onError: (err) => {
          console.error("create trip settlement failed", err);
          const msg =
            err instanceof ApiError
              ? err.message
              : "No pudimos registrar el pago. Intenta de nuevo.";
          if (typeof window !== "undefined") window.alert(msg);
        },
      },
    );
    onClose();
  }

  const isPending = false;

  return (
    <div className="space-y-4 pt-1">
      <Field label="De">
        <select
          value={fromId}
          onChange={(e) => setFromId(e.target.value)}
          disabled={isPending}
          className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700 bg-white"
        >
          {attendees.map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name}
              {a.left_at ? " (salió)" : ""}
            </option>
          ))}
        </select>
      </Field>

      <Field label="A">
        <select
          value={toId}
          onChange={(e) => setToId(e.target.value)}
          disabled={isPending}
          className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700 bg-white"
        >
          {attendees.map((a) => (
            <option key={a.id} value={a.id}>
              {a.display_name}
              {a.left_at ? " (salió)" : ""}
            </option>
          ))}
        </select>
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
          {isPending ? "Guardando..." : "Confirmar pago"}
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
