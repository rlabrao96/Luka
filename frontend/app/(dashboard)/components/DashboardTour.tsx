"use client";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";

const TOUR_KEY = "luka_dashboard_tour_v1";

interface Step {
  anchor: string; // data-tour value
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    anchor: "cashflow",
    title: "Tu flujo del mes",
    body: "Ingresos, gastos y saldo neto — se actualizan solos con cada transacción que Luka captura.",
  },
  {
    anchor: "trend",
    title: "Cómo evolucionas",
    body: "Compara tu gasto personal y compartido mes a mes para ver hacia dónde va tu dinero.",
  },
  {
    anchor: "categories",
    title: "En qué se va",
    body: "Tus categorías principales y qué tan cerca estás de tus topes. Toca cualquiera para ver el detalle.",
  },
];

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

/** Lightweight coach-mark tour: highlights key dashboard sections once, then
 *  never again (localStorage). Shown only to users past first-run (the parent
 *  gates on `enabled`). Recomputes on scroll/resize so the spotlight stays
 *  glued to its target across responsive layouts. */
export function DashboardTour({ enabled }: { enabled: boolean }) {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);

  // Decide whether to run — after mount so localStorage is available.
  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;
    if (localStorage.getItem(TOUR_KEY)) return;
    // Small delay so the dashboard cards have painted and measured.
    const t = setTimeout(() => setActive(true), 600);
    return () => clearTimeout(t);
  }, [enabled]);

  const measure = useCallback(() => {
    if (!active) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${STEPS[step].anchor}"]`);
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }, [active, step]);

  useLayoutEffect(() => {
    if (!active) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${STEPS[step].anchor}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    // Measure after the scroll settles.
    const t = setTimeout(measure, 350);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [active, step, measure]);

  const finish = () => {
    localStorage.setItem(TOUR_KEY, "1");
    setActive(false);
  };

  if (!active || !rect) return null;

  const isLast = step === STEPS.length - 1;
  const pad = 8;
  // Place the tooltip below the target if there's room, otherwise above.
  const belowRoom = window.innerHeight - (rect.top + rect.height);
  const placeBelow = belowRoom > 200;
  const tipTop = placeBelow ? rect.top + rect.height + pad + 6 : rect.top - pad - 6;

  return (
    <div className="fixed inset-0 z-[95]" role="dialog" aria-modal="true" aria-label="Recorrido">
      {/* Dimmed overlay with a spotlight hole via a huge box-shadow. */}
      <div
        className="pointer-events-none absolute rounded-2xl transition-all duration-300"
        style={{
          top: rect.top - pad,
          left: rect.left - pad,
          width: rect.width + pad * 2,
          height: rect.height + pad * 2,
          boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.55)",
        }}
      />
      {/* Highlight ring. */}
      <div
        className="pointer-events-none absolute rounded-2xl ring-2 ring-luka-primary transition-all duration-300"
        style={{
          top: rect.top - pad,
          left: rect.left - pad,
          width: rect.width + pad * 2,
          height: rect.height + pad * 2,
        }}
      />
      {/* Tooltip card. */}
      <div
        className="absolute w-[min(320px,calc(100vw-2rem))] rounded-2xl bg-white p-4 shadow-2xl"
        style={{
          top: placeBelow ? tipTop : undefined,
          bottom: placeBelow ? undefined : window.innerHeight - tipTop,
          left: Math.max(16, Math.min(rect.left, window.innerWidth - 336)),
        }}
      >
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-luka-primary">
            {step + 1} de {STEPS.length}
          </span>
          <button
            type="button"
            onClick={finish}
            className="text-[11px] font-medium text-slate-400 hover:text-slate-600"
          >
            Saltar
          </button>
        </div>
        <h3 className="text-sm font-semibold text-luka-dark">{STEPS[step].title}</h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-600">{STEPS[step].body}</p>
        <div className="mt-3 flex items-center justify-between">
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${
                  i === step ? "bg-luka-primary" : "bg-slate-200"
                }`}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={() => (isLast ? finish() : setStep((s) => s + 1))}
            className="rounded-lg bg-luka-primary px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
          >
            {isLast ? "Entendido" : "Siguiente"}
          </button>
        </div>
      </div>
    </div>
  );
}
