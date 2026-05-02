"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCreateTrip } from "@/app/lib/hooks/useTrips";
import { ApiError, type CreateAttendeeInput } from "@/app/lib/api";
import { SUPPORTED_CURRENCIES } from "@/app/lib/currency";

interface NewTripDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface AttendeeChip {
  raw: string;
  payload: CreateAttendeeInput;
}

/** Heuristic: email > phone > display_name. Backend accepts at least one. */
function classifyAttendee(raw: string): CreateAttendeeInput | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (trimmed.includes("@")) return { email: trimmed };
  // Phone: starts with + OR is digits + spaces/dashes ≥ 7 chars
  const phoneLike = /^\+?[\d\s\-().]{7,}$/.test(trimmed);
  if (phoneLike) return { phone: trimmed };
  return { display_name: trimmed };
}

export default function NewTripDialog({
  open,
  onOpenChange,
}: NewTripDialogProps) {
  const router = useRouter();
  const createMutation = useCreateTrip();

  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("USD");
  const [attendeeInput, setAttendeeInput] = useState("");
  const [attendees, setAttendees] = useState<AttendeeChip[]>([]);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setName("");
    setStartDate("");
    setEndDate("");
    setBaseCurrency("USD");
    setAttendeeInput("");
    setAttendees([]);
    setError(null);
  }

  function handleClose(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function addAttendeeFromInput() {
    const payload = classifyAttendee(attendeeInput);
    if (!payload) return;
    setAttendees((prev) => [
      ...prev,
      { raw: attendeeInput.trim(), payload },
    ]);
    setAttendeeInput("");
  }

  function removeAttendee(idx: number) {
    setAttendees((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleAttendeeKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addAttendeeFromInput();
    }
  }

  function validate(): string | null {
    if (!name.trim()) return "Ingresa un nombre para el viaje.";
    if (name.length > 120) return "El nombre no puede superar 120 caracteres.";
    if (!startDate || !endDate) return "Ingresa las fechas del viaje.";
    if (endDate < startDate) {
      return "La fecha de fin debe ser igual o posterior a la de inicio.";
    }
    if (!baseCurrency) return "Selecciona una moneda base.";
    return null;
  }

  async function handleSubmit() {
    setError(null);
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    try {
      const trip = await createMutation.mutateAsync({
        name: name.trim(),
        start_date: startDate,
        end_date: endDate,
        base_currency: baseCurrency,
        attendees: attendees.map((a) => a.payload),
      });
      handleClose(false);
      router.push(`/viajes/${trip.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No pudimos crear el viaje. Intenta de nuevo.");
      }
    }
  }

  const isPending = createMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nuevo viaje</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-1">
          {/* Name */}
          <div>
            <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
              Nombre del viaje
            </label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              placeholder="Cartagena 2026"
              disabled={isPending}
              className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
            />
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                Inicio
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={isPending}
                className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                Fin
              </label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                min={startDate || undefined}
                disabled={isPending}
                className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
              />
            </div>
          </div>

          {/* Base currency */}
          <div>
            <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
              Moneda base
            </label>
            <select
              value={baseCurrency}
              onChange={(e) => setBaseCurrency(e.target.value)}
              disabled={isPending}
              className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700 bg-white"
            >
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.code} — {c.name}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-400 mt-1">
              Todos los saldos se mostrarán en esta moneda.
            </p>
          </div>

          {/* Attendees */}
          <div>
            <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
              Asistentes (opcional)
            </label>
            <div className="flex gap-2">
              <Input
                type="text"
                value={attendeeInput}
                onChange={(e) => setAttendeeInput(e.target.value)}
                onKeyDown={handleAttendeeKeyDown}
                placeholder="email, teléfono o nombre"
                disabled={isPending}
                className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg flex-1"
              />
              <Button
                type="button"
                variant="outline"
                onClick={addAttendeeFromInput}
                disabled={isPending || !attendeeInput.trim()}
                className="h-11 sm:h-10"
              >
                <Plus size={14} />
                Añadir
              </Button>
            </div>
            {attendees.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {attendees.map((a, idx) => (
                  <span
                    key={`${a.raw}-${idx}`}
                    className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs font-medium px-2 py-1 rounded-full"
                  >
                    {a.raw}
                    <button
                      type="button"
                      onClick={() => removeAttendee(idx)}
                      disabled={isPending}
                      aria-label={`Eliminar ${a.raw}`}
                      className="text-blue-700/70 hover:text-blue-900"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <p className="text-[11px] text-slate-400 mt-1.5">
              Te agregaremos automáticamente. Puedes invitar más después.
            </p>
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => handleClose(false)}
              disabled={isPending}
              className="flex-1 sm:flex-initial px-4 h-11 rounded-lg bg-slate-50 text-slate-500 border border-slate-200 text-sm font-medium hover:bg-slate-100 transition-colors disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={isPending}
              className="flex-1 px-4 h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {isPending ? "Creando..." : "Crear viaje"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
