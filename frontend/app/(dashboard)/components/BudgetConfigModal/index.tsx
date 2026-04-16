"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/app/lib/api";
import type { BudgetV2Response } from "@/app/lib/api";
import { SavingsTargetRow } from "./SavingsTargetRow";
import { PersonalAllocationRow } from "./PersonalAllocationRow";
import { PaydayRow } from "./PaydayRow";
import { ContributionRow } from "./ContributionRow";

export interface BudgetConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  householdId: string | null;
  month: string; // YYYY-MM-01
  /** Live household-view budget-v2 response for per-category spend lookups. */
  householdBudget: BudgetV2Response | undefined;
}

// Row ids used by the accordion state machine.
export type BudgetConfigRowId =
  | "savings"
  | "personal"
  | "payday"
  | "contribution"
  | "caps";

export function BudgetConfigModal({
  open,
  onOpenChange,
  householdId,
  month,
  householdBudget,
}: BudgetConfigModalProps) {
  // One row expanded at a time. null = all collapsed.
  const [expandedRow, setExpandedRow] = useState<BudgetConfigRowId | null>(null);

  // Prefetch the mutable data the individual rows need. We load it here
  // so the rows can read it via the query cache without each one
  // re-requesting on mount.
  const budgetSettings = useQuery({
    queryKey: ["budgetSettings"],
    queryFn: () => api.getBudgetSettings(),
    enabled: open,
    staleTime: 30 * 1000,
  });

  // First-open auto-expand logic. `needsSetup` is the one-time nudge:
  // if the user has no savings target AND no payday set, expand
  // Meta de ahorro on first open. The nudge only fires once per modal open.
  useEffect(() => {
    if (!open) {
      setExpandedRow(null);
      return;
    }
    if (!budgetSettings.data) return;
    const needsSetup =
      budgetSettings.data.savings_target_amount == null ||
      budgetSettings.data.payday_day_of_month == null;
    if (needsSetup) setExpandedRow("savings");
    // Only run once per open — the dep list intentionally omits expandedRow.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, budgetSettings.data]);

  function toggleRow(id: BudgetConfigRowId) {
    setExpandedRow((prev) => (prev === id ? null : id));
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm
                     data-[state=open]:animate-in data-[state=closed]:animate-out
                     data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        />
        <Dialog.Content
          aria-describedby={undefined}
          className="
            fixed z-50
            left-1/2 top-1/2 w-[calc(100%-2rem)] max-w-md max-h-[90vh]
            -translate-x-1/2 -translate-y-1/2
            bg-white rounded-2xl overflow-hidden flex flex-col
            shadow-[0_24px_64px_-16px_rgba(15,23,42,0.22),0_8px_24px_-12px_rgba(15,23,42,0.10)]
            data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[.985]
            data-[state=closed]:animate-out data-[state=closed]:fade-out-0
            max-md:top-auto max-md:bottom-0 max-md:left-0 max-md:translate-x-0 max-md:translate-y-0
            max-md:w-full max-md:max-w-full max-md:rounded-2xl max-md:rounded-b-none
            max-md:data-[state=open]:animate-slide-up
          "
        >
          {/* Mobile drag handle */}
          <div className="flex md:hidden justify-center pt-3 pb-1" aria-hidden>
            <div className="h-1 w-10 rounded-full bg-slate-200" />
          </div>

          {/* Header */}
          <div
            className="relative px-6 pt-5 pb-4 border-b border-slate-100"
            style={{
              background:
                "radial-gradient(1200px 200px at 90% -20%, rgba(96,165,250,0.18), transparent 60%), linear-gradient(180deg, #FFFFFF 0%, #F6FAFF 100%)",
            }}
          >
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-luka-primary">
              Configurar presupuesto
            </div>
            <Dialog.Title className="text-[22px] font-bold text-luka-dark mt-1 tracking-[-0.02em]">
              Tu plan de este mes
            </Dialog.Title>
            <Dialog.Description className="text-[12.5px] text-slate-500 mt-0.5">
              Todos los números que alimentan el Sankey, en un solo lugar.
            </Dialog.Description>
            <Dialog.Close
              aria-label="Cerrar"
              className="absolute top-4 right-4 w-8 h-8 rounded-[9px] bg-slate-900/[0.04] hover:bg-slate-900/10 flex items-center justify-center transition-colors"
            >
              <X size={16} className="text-slate-700" />
            </Dialog.Close>
          </div>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto pb-2">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Mi plan
            </div>
            <div className="px-2 space-y-0.5">
              <SavingsTargetRow
                expanded={expandedRow === "savings"}
                onToggle={toggleRow}
              />
              <PersonalAllocationRow
                expanded={expandedRow === "personal"}
                onToggle={toggleRow}
              />
              <PaydayRow
                expanded={expandedRow === "payday"}
                onToggle={toggleRow}
              />
            </div>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Hogar
            </div>
            <div className="px-2 space-y-0.5">
              <ContributionRow
                expanded={expandedRow === "contribution"}
                onToggle={toggleRow}
              />
            </div>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500 px-[18px] pt-2.5 pb-1.5">
              Categorías
            </div>
            <div className="px-2 space-y-0.5 pb-2">
              {/* CategoryCapsRow lands here in Task 11 */}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-3.5 border-t border-slate-100 bg-[#FAFBFF] flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11.5px] text-slate-500">
              <kbd className="bg-white border border-slate-200 rounded-[5px] px-1.5 py-0.5 font-[var(--font-geist-mono)] text-[10.5px]">
                Esc
              </kbd>
              <span>para cerrar</span>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-[11px] bg-luka-primary text-white text-[13px] font-semibold px-4.5 py-2.5 shadow-[0_2px_10px_rgba(37,99,235,0.30)] hover:bg-luka-primary-dark transition-colors"
              >
                Listo
              </button>
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// Suppress the unused-prop TS warnings for props that land in Tasks 6-11.
// The modal consumers (budgets/page.tsx) will pass them from the get-go.
type _UsedLater = Pick<BudgetConfigModalProps, "householdId" | "month" | "householdBudget">;
type _Touch = keyof _UsedLater extends never ? never : _UsedLater;
