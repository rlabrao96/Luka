"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { AllocationResponse, SetAllocationPayload } from "@/app/lib/api";

interface Props {
  allocation: AllocationResponse;
  income: number;
  month: string; // YYYY-MM-DD
  onSave: (payload: SetAllocationPayload) => void;
  isSaving: boolean;
}

function CLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

export default function AllocationCard({ allocation, income, month, onSave, isSaving }: Props) {
  const [hogar, setHogar] = useState(allocation.allocation.hogar_pct);
  const [ahorro, setAhorro] = useState(allocation.allocation.ahorro_pct);
  const personal = Math.max(0, 100 - hogar - ahorro);
  const [isEditing, setIsEditing] = useState(allocation.allocation.is_default);

  function applySuggestion(s: { hogar_pct: number; ahorro_pct: number }) {
    setHogar(s.hogar_pct);
    setAhorro(s.ahorro_pct);
  }

  function handleSave() {
    onSave({ month, hogar_pct: hogar, ahorro_pct: ahorro, personal_pct: personal });
    setIsEditing(false);
  }

  if (!isEditing) {
    return (
      <Card className="bg-white shadow-[var(--shadow-card)]">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-semibold text-gray-800">Tu presupuesto</CardTitle>
          <button
            onClick={() => setIsEditing(true)}
            className="text-xs text-blue-600 hover:underline"
          >
            Editar
          </button>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between text-sm text-gray-500">
            <span>
              Hogar <span className="text-gray-800 font-medium">{hogar}%</span>
            </span>
            <span>
              Ahorro <span className="text-gray-800 font-medium">{ahorro}%</span>
            </span>
            <span>
              Personal <span className="text-gray-800 font-medium">{personal}%</span>
            </span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white shadow-[var(--shadow-card)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-gray-800">Tu presupuesto</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Suggestion pills */}
        <div className="flex gap-2 flex-wrap">
          {allocation.suggestions.historical && (
            <button
              onClick={() => applySuggestion(allocation.suggestions.historical!)}
              className="text-xs px-3 py-1 rounded-full bg-blue-50 text-blue-600 border border-blue-200"
            >
              Según tu historial
            </button>
          )}
          <button
            onClick={() => applySuggestion(allocation.suggestions.recommended)}
            className="text-xs px-3 py-1 rounded-full bg-gray-50 text-gray-500 border border-gray-200"
          >
            {allocation.suggestions.recommended.label ?? "Regla 50/20/30"}
          </button>
        </div>

        {/* Hogar slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Hogar</span>
            <span className="text-gray-800 font-medium">
              {hogar}% — {income > 0 ? CLP((income * hogar) / 100) : "—"}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100 - ahorro}
            step={5}
            value={hogar}
            onChange={(e) => setHogar(Number(e.target.value))}
            className="luka-slider w-full"
          />
        </div>

        {/* Ahorro slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Ahorro</span>
            <span className="text-gray-800 font-medium">
              {ahorro}% — {income > 0 ? CLP((income * ahorro) / 100) : "—"}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100 - hogar}
            step={5}
            value={ahorro}
            onChange={(e) => setAhorro(Number(e.target.value))}
            className="luka-slider w-full"
          />
        </div>

        {/* Personal (read-only) */}
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Personal (resto)</span>
          <span className="text-gray-800 font-medium">
            {personal}% — {income > 0 ? CLP((income * personal) / 100) : "—"}
          </span>
        </div>

        {personal < 0 && (
          <p className="text-xs text-red-500">
            Hogar + Ahorro supera el 100%. Ajusta los valores.
          </p>
        )}
        <Button
          onClick={handleSave}
          disabled={isSaving || personal < 0}
          className="w-full bg-blue-600 text-white hover:bg-blue-700"
        >
          {isSaving ? "Guardando..." : "Guardar"}
        </Button>
      </CardContent>
    </Card>
  );
}
