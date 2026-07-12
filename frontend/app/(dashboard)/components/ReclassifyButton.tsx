"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Check } from "lucide-react";
import { api } from "@/app/lib/api";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";

type Range = 7 | 30 | 90 | 180;

const RANGE_LABELS: Record<Range, string> = {
  7: "Últimos 7 días",
  30: "Últimos 30 días",
  90: "Últimos 3 meses",
  180: "Últimos 6 meses",
};

function sinceISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

/** Manual "classify unclassified transactions" trigger. Appears only when the
 *  user has uncategorized transactions in the last 6 months. Opens a dialog to
 *  pick a time frame, runs the automatic classifier over that range, and tells
 *  the user a review notification will arrive for approval — reusing the
 *  merchant-review pipeline. */
export function ReclassifyButton() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [range, setRange] = useState<Range>(30);
  const [done, setDone] = useState<number | null>(null);

  // Cheap gate: how many uncategorized in the widest window (6 months).
  const count = useQuery({
    queryKey: ["unclassified-count", sinceISO(180)],
    queryFn: () => api.getUnclassifiedCount(sinceISO(180)),
    staleTime: 60 * 1000,
  });

  // Per-range count so the dialog shows what each option would classify.
  const rangeCount = useQuery({
    queryKey: ["unclassified-count", sinceISO(range)],
    queryFn: () => api.getUnclassifiedCount(sinceISO(range)),
    enabled: open,
    staleTime: 30 * 1000,
  });

  const run = useMutation({
    mutationFn: () => api.reclassify(sinceISO(range)),
    onSuccess: (res) => {
      setDone(res.transaction_count);
      qc.invalidateQueries({ queryKey: ["unclassified-count"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const total = count.data?.count ?? 0;
  if (total === 0) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setDone(null);
          setOpen(true);
        }}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-luka-primary/30 bg-luka-primary/5 px-3 text-xs font-semibold text-luka-primary hover:bg-luka-primary/10"
        title="Clasificar transacciones sin categoría"
      >
        <Sparkles size={14} />
        <span className="hidden sm:inline">Clasificar</span>
        <span className="rounded-full bg-luka-primary px-1.5 text-[10px] font-bold text-white">
          {total}
        </span>
      </button>

      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          {done === null ? (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>Clasificar automáticamente</AlertDialogTitle>
                <AlertDialogDescription>
                  Luka analizará tus transacciones sin categoría con IA y te
                  enviará una notificación para que apruebes las categorías
                  sugeridas.
                </AlertDialogDescription>
              </AlertDialogHeader>

              <div className="space-y-2 py-1">
                {(Object.keys(RANGE_LABELS) as unknown as Range[])
                  .map(Number)
                  .map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setRange(r as Range)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                        range === r
                          ? "border-luka-primary bg-luka-primary/5 font-semibold text-luka-primary"
                          : "border-slate-200 text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      <span>{RANGE_LABELS[r as Range]}</span>
                      {range === r && <Check size={15} />}
                    </button>
                  ))}
                <p className="pt-1 text-center text-xs text-slate-500">
                  {rangeCount.isFetching
                    ? "Contando…"
                    : `${rangeCount.data?.count ?? 0} transacción(es) sin categoría en este rango.`}
                </p>
              </div>

              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <button
                  type="button"
                  onClick={() => run.mutate()}
                  disabled={run.isPending || (rangeCount.data?.count ?? 0) === 0}
                  className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-luka-primary px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Sparkles size={15} />
                  {run.isPending ? "Iniciando…" : "Clasificar"}
                </button>
              </AlertDialogFooter>
            </>
          ) : (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>¡En marcha! 🎉</AlertDialogTitle>
                <AlertDialogDescription>
                  {done > 0
                    ? `Estamos clasificando ${done} transacción(es). Te enviaremos una notificación para aprobar las categorías en unos momentos.`
                    : "No encontramos transacciones sin categoría en ese rango."}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="inline-flex h-10 items-center justify-center rounded-lg bg-luka-primary px-4 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Entendido
                </button>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
