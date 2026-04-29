"use client";

import { ArrowLeftRight, HandCoins } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type VincularType = "transfer" | "reimbursement";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (type: VincularType) => void;
};

/**
 * Two-option picker shown right after the user clicks "Vincular" on a
 * settled row. The user must declare WHICH kind of link this is even when
 * the cardinality could be 1-to-1 (a friend reimbursing one expense is a
 * reembolso, not a transferencia).
 */
export function VincularTypeDialog({ open, onOpenChange, onPick }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>¿Qué tipo de vínculo es este?</DialogTitle>
          <DialogDescription>
            Elige cómo agrupar este movimiento con otros.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-2.5 sm:gap-3">
          <button
            type="button"
            onClick={() => onPick("transfer")}
            className="text-left flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 hover:border-luka-primary/40 hover:bg-blue-50/40 transition-colors"
          >
            <div className="shrink-0 mt-0.5 flex w-9 h-9 rounded-lg bg-blue-50 text-blue-500 items-center justify-center">
              <ArrowLeftRight size={18} strokeWidth={2.5} />
            </div>
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-luka-dark">
                Transferencia entre mis cuentas
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Moví dinero entre dos de mis cuentas (p. ej. pago de tarjeta).
              </p>
            </div>
          </button>

          <button
            type="button"
            onClick={() => onPick("reimbursement")}
            className="text-left flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 hover:border-luka-primary/40 hover:bg-emerald-50/40 transition-colors"
          >
            <div className="shrink-0 mt-0.5 flex w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 items-center justify-center">
              <HandCoins size={18} strokeWidth={2.5} />
            </div>
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-luka-dark">
                Reembolso
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Alguien me devolvió este gasto (o un grupo de gastos).
              </p>
            </div>
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
