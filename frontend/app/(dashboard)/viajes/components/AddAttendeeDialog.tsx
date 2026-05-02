"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAddAttendee } from "@/app/lib/hooks/useTrips";
import { ApiError, type CreateAttendeeInput } from "@/app/lib/api";

interface AddAttendeeDialogProps {
  tripId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Heuristic: email > phone > display_name. Mirrors NewTripDialog. */
function classify(raw: string): CreateAttendeeInput | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (trimmed.includes("@")) return { email: trimmed };
  const phoneLike = /^\+?[\d\s\-().]{7,}$/.test(trimmed);
  if (phoneLike) return { phone: trimmed };
  return { display_name: trimmed };
}

export default function AddAttendeeDialog({
  tripId,
  open,
  onOpenChange,
}: AddAttendeeDialogProps) {
  const addMutation = useAddAttendee(tripId);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setValue("");
    setError(null);
    addMutation.reset();
  }

  function handleClose(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  async function handleSubmit() {
    setError(null);
    const payload = classify(value);
    if (!payload) {
      setError("Ingresa un email, teléfono o nombre.");
      return;
    }
    try {
      await addMutation.mutateAsync(payload);
      handleClose(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No pudimos agregar al asistente. Intenta de nuevo.");
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  const isPending = addMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Agregar asistente</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 pt-1">
          <Input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Email, teléfono o nombre"
            disabled={isPending}
            autoFocus
            className="h-11 sm:h-10 text-base sm:text-[13px] rounded-lg"
          />
          <p className="text-[11px] text-slate-400">
            Si es un usuario de Luka, lo agregamos por email o teléfono. Si no, ingresa solo el nombre.
          </p>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

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
              disabled={isPending || !value.trim()}
              className="flex-1 px-4 h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {isPending ? "Agregando..." : "Agregar"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
