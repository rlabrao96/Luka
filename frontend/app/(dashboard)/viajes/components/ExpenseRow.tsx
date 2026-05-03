"use client";

import { useState } from "react";
import { MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import type { TripAttendee, TripExpense } from "@/app/lib/api";
import { formatMajorAmount } from "@/app/lib/currency";
import { useDeleteExpense } from "@/app/lib/hooks/useTrips";

interface ExpenseRowProps {
  expense: TripExpense;
  attendees: TripAttendee[];
  tripBaseCurrency: string;
  tripId: string;
}

const SPANISH_MONTHS_SHORT = [
  "ene", "feb", "mar", "abr", "may", "jun",
  "jul", "ago", "sep", "oct", "nov", "dic",
];

function formatExpenseDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getDate()} ${SPANISH_MONTHS_SHORT[d.getMonth()]}`;
}

/**
 * Single expense row — payer initial avatar, description + meta, amount, kebab.
 *
 * Click anywhere on the row except the kebab to open an edit sheet (v2;
 * placeholder for now). Delete via kebab triggers a confirm dialog.
 */
export default function ExpenseRow({
  expense,
  attendees,
  tripBaseCurrency,
  tripId,
}: ExpenseRowProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const deleteMutation = useDeleteExpense(tripId);

  const payer = attendees.find((a) => a.id === expense.payer_attendee_id);
  const payerName = payer?.display_name ?? "—";
  const initial = payerName.trim().charAt(0).toUpperCase() || "?";

  const showAltCurrency = expense.currency !== tripBaseCurrency;

  function handleRowClick() {
    // Edit sheet is Phase 7.4 v2 / Phase 7.5 — soft placeholder for now.
    alert("Editar gasto — próximamente");
  }

  function handleDelete() {
    deleteMutation.mutate(expense.id, {
      onError: (err) => {
        console.error("delete trip expense failed", err);
        if (typeof window !== "undefined") {
          window.alert("No pudimos eliminar el gasto. Intenta de nuevo.");
        }
      },
    });
    setConfirmOpen(false);
  }

  return (
    <>
      <button
        type="button"
        onClick={handleRowClick}
        className="w-full text-left flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-[var(--shadow-card)] transition-all hover:border-luka-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary"
      >
        {/* Avatar */}
        <span className="shrink-0 w-9 h-9 rounded-full bg-blue-50 text-luka-primary text-xs font-semibold flex items-center justify-center">
          {initial}
        </span>
        {/* Middle */}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-luka-dark truncate">
            {expense.description}
          </p>
          <p className="text-[11px] text-slate-500 truncate">
            {formatExpenseDate(expense.expense_date)} · {payerName} pagó
          </p>
        </div>
        {/* Right */}
        <div className="shrink-0 flex items-center gap-1.5">
          <div className="text-right">
            <p className="text-sm font-semibold text-luka-dark tabular-nums">
              {formatMajorAmount(Number(expense.amount), expense.currency)}
            </p>
            {showAltCurrency && (
              <p className="text-[10px] text-slate-400">{expense.currency}</p>
            )}
          </div>
          <span
            role="button"
            aria-label="Acciones del gasto"
            onClick={(e) => e.stopPropagation()}
            className="contents"
          >
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Acciones del gasto"
                className="flex items-center justify-center h-7 w-7 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal size={14} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[160px]">
                <DropdownMenuItem
                  variant="destructive"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmOpen(true);
                  }}
                >
                  <Trash2 />
                  Eliminar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </span>
        </div>
      </button>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar gasto?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. El saldo del viaje se recalculará.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleteMutation.isPending ? "Eliminando..." : "Eliminar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
