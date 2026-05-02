"use client";

import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTripPreview, useJoinTrip } from "@/app/lib/hooks/useTrips";
import { ApiError } from "@/app/lib/api";
import { formatTripDateRange } from "@/app/lib/months";

interface JoinTripPageProps {
  params: Promise<{ token: string }>;
}

export default function JoinTripPage({ params }: JoinTripPageProps) {
  const { token } = use(params);
  const router = useRouter();
  const { data: preview, error, isLoading } = useTripPreview(token);
  const joinMutation = useJoinTrip();

  if (isLoading) {
    return (
      <div className="px-4 py-6 max-w-md mx-auto space-y-3">
        <div className="h-7 w-48 bg-slate-100 rounded animate-pulse" />
        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
        <div className="h-11 w-full bg-slate-100 rounded animate-pulse mt-6" />
      </div>
    );
  }

  if (error) {
    const msg =
      error instanceof ApiError && error.status === 404
        ? "Este enlace de invitación no es válido o ha expirado."
        : error instanceof ApiError && error.status === 403
          ? "No tienes acceso a la función de viajes. Contacta a tu administrador."
          : "No pudimos cargar la invitación. Intenta de nuevo.";
    return (
      <div className="px-4 py-6 max-w-md mx-auto space-y-3">
        <Link
          href="/viajes"
          className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-luka-primary"
        >
          ← Viajes
        </Link>
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-center">
          <p className="text-sm text-red-700">{msg}</p>
        </div>
      </div>
    );
  }

  if (!preview) return null;

  async function handleJoin() {
    try {
      const trip = await joinMutation.mutateAsync(token);
      router.push(`/viajes/${trip.id}`);
    } catch {
      // Surfaced via mutation state below.
    }
  }

  const joinError = joinMutation.error;

  return (
    <div className="px-4 py-6 max-w-md mx-auto space-y-3">
      <Link
        href="/viajes"
        className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-luka-primary"
      >
        ← Viajes
      </Link>

      <div className="rounded-xl border border-slate-200 bg-white px-5 py-6 space-y-3">
        <div>
          <p className="text-[11px] font-semibold text-slate-500 uppercase">
            Te invitaron al viaje
          </p>
          <h1 className="text-2xl font-semibold text-luka-dark mt-1">
            {preview.name}
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            {formatTripDateRange(preview.start_date, preview.end_date)}
          </p>
        </div>
        <p className="text-xs text-slate-500">
          {preview.attendee_count}{" "}
          {preview.attendee_count === 1
            ? "asistente activo"
            : "asistentes activos"}{" "}
          · Moneda: {preview.base_currency}
        </p>

        <button
          type="button"
          onClick={handleJoin}
          disabled={joinMutation.isPending}
          className="w-full inline-flex items-center justify-center h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {joinMutation.isPending ? "Uniéndome..." : "Unirme al viaje"}
        </button>

        {joinError && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {joinError instanceof ApiError
              ? joinError.message
              : "Error al unirse al viaje. Intenta de nuevo."}
          </p>
        )}
      </div>
    </div>
  );
}
