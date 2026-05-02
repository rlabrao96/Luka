"use client";

import { use, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTrip } from "@/app/lib/hooks/useTrips";
import { ApiError } from "@/app/lib/api";
import TripHeader from "../components/TripHeader";
import ResumenTab from "../components/ResumenTab";
import GastosTab from "../components/GastosTab";
import SaldosTab from "../components/SaldosTab";
import AsistentesTab from "../components/AsistentesTab";
import AddExpenseSheet from "../components/AddExpenseSheet";

interface TripDetailPageProps {
  // Next 16 App Router: params is async — use React.use() to unwrap.
  params: Promise<{ id: string }>;
}

export default function TripDetailPage({ params }: TripDetailPageProps) {
  const { id } = use(params);
  const [sheetOpen, setSheetOpen] = useState(false);
  const { data: trip, isLoading, isError, error, refetch } = useTrip(id);

  const isNotMember =
    isError && error instanceof ApiError && (error.status === 404 || error.status === 403);

  const addExpenseButton = (
    <button
      type="button"
      onClick={() => setSheetOpen(true)}
      className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors shadow-[var(--shadow-card)]"
    >
      <Plus size={16} />
      Agregar gasto
    </button>
  );

  if (isLoading || !trip) {
    if (isNotMember) {
      return (
        <div className="space-y-5">
          <Link
            href="/viajes"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-luka-primary"
          >
            ← Viajes
          </Link>
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-12 text-center">
            <p className="text-sm text-slate-700 font-semibold">Viaje no encontrado</p>
            <p className="text-xs text-slate-500 mt-1">
              Es posible que ya no seas asistente o que el viaje haya sido eliminado.
            </p>
          </div>
        </div>
      );
    }
    if (isError) {
      return (
        <div className="space-y-5">
          <Link
            href="/viajes"
            className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-luka-primary"
          >
            ← Viajes
          </Link>
          <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-6 text-center space-y-3">
            <p className="text-sm text-red-700">No pudimos cargar este viaje.</p>
            <button
              type="button"
              onClick={() => refetch()}
              className="text-xs font-semibold text-red-700 underline underline-offset-2 hover:text-red-900"
            >
              Reintentar
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className="space-y-5">
        <div className="h-4 w-20 bg-slate-100 rounded animate-pulse" />
        <div className="space-y-2">
          <div className="h-7 w-48 bg-slate-100 rounded animate-pulse" />
          <div className="h-4 w-32 bg-slate-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 h-20"
            >
              <div className="h-3 w-16 bg-slate-100 rounded animate-pulse" />
              <div className="h-5 w-24 bg-slate-100 rounded animate-pulse mt-2" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 pb-24 lg:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <TripHeader trip={trip} />
        </div>
        <div className="hidden lg:block shrink-0 pt-7">{addExpenseButton}</div>
      </div>

      <Tabs defaultValue="resumen">
        <TabsList variant="line" className="border-b border-slate-200 w-full overflow-x-auto justify-start">
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="gastos">Gastos</TabsTrigger>
          <TabsTrigger value="saldos">Saldos</TabsTrigger>
          <TabsTrigger value="asistentes">Asistentes</TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="mt-4">
          <ResumenTab trip={trip} />
        </TabsContent>
        <TabsContent value="gastos" className="mt-4">
          <GastosTab trip={trip} onAddExpense={() => setSheetOpen(true)} />
        </TabsContent>
        <TabsContent value="saldos" className="mt-4">
          <SaldosTab trip={trip} />
        </TabsContent>
        <TabsContent value="asistentes" className="mt-4">
          <AsistentesTab trip={trip} />
        </TabsContent>
      </Tabs>

      {/* Sticky bottom CTA on mobile */}
      <div className="fixed bottom-0 inset-x-0 lg:hidden bg-white border-t border-slate-200 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] z-30">
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className="w-full inline-flex items-center justify-center gap-1.5 h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
        >
          <Plus size={16} />
          Agregar gasto
        </button>
      </div>

      <AddExpenseSheet
        tripId={trip.id}
        trip={trip}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  );
}
