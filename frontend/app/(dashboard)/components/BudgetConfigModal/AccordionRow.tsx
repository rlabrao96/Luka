"use client";

import { useEffect, useId, useRef } from "react";
import { ChevronRight } from "lucide-react";

export interface AccordionRowProps {
  /** Unique id so the parent can track which row is expanded. */
  id: string;
  /** Whether this row is the currently-expanded one. */
  expanded: boolean;
  /** Toggle callback from the parent state machine. */
  onToggle: (id: string) => void;
  /** Icon node rendered inside the 42x42 tile (e.g. <Target size={20} />). */
  icon: React.ReactNode;
  /** Small uppercase label, e.g. "Meta de ahorro". */
  label: string;
  /** Main value text, e.g. "$300.000" or "Sin meta". */
  valuePrimary: string;
  /** Muted unit text rendered in Geist Mono next to the primary value. */
  valueUnit?: string;
  /** Italic "empty" state — when true, the primary value renders muted + italic. */
  empty?: boolean;
  /**
   * Signal that a save just succeeded. Incrementing this number triggers
   * the auto-collapse timer inside the row. The parent increments it from
   * inside the save mutation's onSuccess.
   */
  savedTick?: number;
  /** Expanded body content (the editor form). */
  children: React.ReactNode;
}

export function AccordionRow({
  id,
  expanded,
  onToggle,
  icon,
  label,
  valuePrimary,
  valueUnit,
  empty = false,
  savedTick = 0,
  children,
}: AccordionRowProps) {
  const bodyId = useId();
  // Auto-collapse 900ms after a successful save.
  // Cancelled if the row is collapsed in the meantime (e.g. the user
  // expanded another row, or the modal closed and `expanded` flipped to false).
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (savedTick === 0) return;
    timerRef.current = setTimeout(() => {
      onToggle(id);
    }, 900);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedTick]);

  // Cancel the timer if the parent collapses this row from outside
  // (e.g. the user clicked a different row).
  useEffect(() => {
    if (!expanded && timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [expanded]);

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => onToggle(id)}
        className={`
          w-full text-left grid grid-cols-[42px_1fr_auto] items-center gap-3.5
          rounded-2xl px-4 py-3.5 transition-colors
          hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary/30
          ${expanded ? "bg-gradient-to-b from-[#F5F9FF] to-transparent" : ""}
        `}
      >
        {expanded && (
          <span
            aria-hidden
            className="absolute left-1 top-3.5 bottom-3.5 w-[3px] rounded-sm bg-gradient-to-b from-luka-primary to-luka-sky"
          />
        )}
        <span
          className="w-[42px] h-[42px] rounded-xl flex items-center justify-center text-luka-primary"
          style={{ background: "linear-gradient(135deg, #EFF6FF, #DBEAFE)" }}
        >
          {icon}
        </span>
        <span className="min-w-0">
          <span className="block text-[10.5px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            {label}
          </span>
          <span
            className={`block text-[15px] font-bold text-slate-900 truncate ${
              empty ? "italic font-medium text-slate-500" : ""
            }`}
          >
            {valuePrimary}
            {valueUnit && (
              <span className="ml-1.5 font-[var(--font-geist-mono)] font-medium text-[12px] text-slate-500">
                {valueUnit}
              </span>
            )}
          </span>
        </span>
        <ChevronRight
          size={18}
          className={`text-slate-400 transition-transform duration-[260ms] ease-[cubic-bezier(.2,.9,.25,1)] ${
            expanded ? "rotate-90 text-luka-primary" : ""
          }`}
        />
      </button>
      <div
        id={bodyId}
        role="region"
        aria-hidden={!expanded}
        className="grid transition-[grid-template-rows] duration-[280ms] ease-[cubic-bezier(.2,.9,.25,1)]"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden min-h-0">
          <div className="pt-1 pb-4 pl-[72px] pr-4">{children}</div>
        </div>
      </div>
    </div>
  );
}
