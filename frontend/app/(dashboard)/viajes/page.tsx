"use client";

import { useMemo, useState } from "react";
import { Plus, Plane } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useTrips } from "@/app/lib/hooks/useTrips";
import { ApiError, type Trip } from "@/app/lib/api";
import TripCard from "./components/TripCard";
import NewTripDialog from "./components/NewTripDialog";

/** Skeleton row used while the trips query is in flight. */
function TripCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-[var(--shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
          <div className="h-3 w-24 bg-slate-100 rounded animate-pulse" />
        </div>
        <div className="h-4 w-20 bg-slate-100 rounded animate-pulse shrink-0" />
      </div>
    </div>
  );
}

function Section({ title, trips }: { title: string; trips: Trip[] }) {
  if (trips.length === 0) return null;
  return (
    <section className="space-y-2">
      <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
        {title}
      </p>
      <div className="space-y-2 md:space-y-0 md:grid md:grid-cols-2 md:gap-4">
        {trips.map((trip) => (
          <TripCard key={trip.id} trip={trip} />
        ))}
      </div>
    </section>
  );
}

export default function ViajesPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const { data, isLoading, isError, error, refetch } = useTrips();

  const allEmpty = useMemo(() => {
    if (!data) return false;
    return (
      data.active.length === 0 &&
      data.upcoming.length === 0 &&
      data.past.length === 0
    );
  }, [data]);

  // Mid-session feature-flag flip would surface here as 403. Show a friendly
  // message instead of the generic error block.
  const isFeatureDisabled =
    isError && error instanceof ApiError && error.status === 403;

  const newTripButton = (
    <button
      type="button"
      onClick={() => setDialogOpen(true)}
      className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-[var(--shadow-card)]"
    >
      <Plus size={16} />
      Nuevo viaje
    </button>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Viajes"
        subtitle="Divide gastos con tus amigos en tus próximos viajes"
        actions={!isFeatureDisabled ? newTripButton : undefined}
      />

      {isFeatureDisabled ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center">
          <p className="text-sm text-slate-600">
            La sección de Viajes no está disponible para tu cuenta.
          </p>
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-6 text-center space-y-3">
          <p className="text-sm text-red-700">
            No pudimos cargar tus viajes. Intenta de nuevo.
          </p>
          <button
            type="button"
            onClick={() => refetch()}
            className="text-xs font-semibold text-red-700 underline underline-offset-2 hover:text-red-900"
          >
            Reintentar
          </button>
        </div>
      ) : isLoading || !data ? (
        <div className="space-y-2 md:grid md:grid-cols-2 md:gap-4 md:space-y-0">
          <TripCardSkeleton />
          <TripCardSkeleton />
          <TripCardSkeleton />
        </div>
      ) : allEmpty ? (
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mx-auto">
            <Plane size={20} className="text-luka-primary" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-luka-dark">
              No tienes viajes todavía
            </p>
            <p className="text-xs text-slate-500 max-w-xs mx-auto">
              Crea uno para dividir gastos con tus amigos.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            className="inline-flex items-center gap-1.5 h-10 px-4 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            <Plus size={16} />
            Nuevo viaje
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <Section title="Activos" trips={data.active} />
          <Section title="Próximos" trips={data.upcoming} />
          <Section title="Pasados" trips={data.past} />
        </div>
      )}

      <NewTripDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
