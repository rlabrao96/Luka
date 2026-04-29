"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Search } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useReimbursementCandidates,
  useLinkReimbursement,
} from "@/app/lib/hooks/useTransactions";
import type { Transaction } from "@/app/lib/api";
import { formatStoredAmount } from "@/app/lib/currency";
import { toTitleCase } from "@/app/lib/strings";
import { cn } from "@/lib/utils";

type WindowDays = 30 | 60 | 90 | 365;

const WINDOW_OPTIONS: { label: string; value: WindowDays }[] = [
  { label: "30d", value: 30 },
  { label: "60d", value: 60 },
  { label: "90d", value: 90 },
  { label: "Todo", value: 365 },
];

type Props = {
  anchor: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/**
 * Reimbursement-link dialog. The user picks N counterpart rows that, summed
 * with the anchor, net to zero. Confirm enables only when balanced (within
 * 1¢, mirroring backend tolerance).
 */
export function ReimbursementLinkDialog({ anchor, open, onOpenChange }: Props) {
  const [windowDays, setWindowDays] = useState<WindowDays>(90);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Reset state every time the dialog opens for a new anchor.
  useEffect(() => {
    if (open) {
      setWindowDays(90);
      setSearch("");
      setSelected(new Set());
    }
  }, [open, anchor?.id]);

  const anchorId = anchor?.id ?? null;
  const { data: candidates = [], isLoading, isError, refetch } =
    useReimbursementCandidates(open ? anchorId : null, windowDays);
  const linkMutation = useLinkReimbursement();

  const anchorAmount = anchor ? Number(anchor.amount) : 0;
  const anchorCurrency = anchor?.currency ?? "CLP";
  const anchorIsInflow = anchorAmount > 0;
  const anchorMagnitude = Math.abs(anchorAmount);

  // Client-side merchant search + smart sort: exact-amount matches bubble
  // to the top so the obvious counterpart is always visible immediately.
  // Within each group (exact / rest), sort by date desc.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const base = q
      ? candidates.filter((c) =>
          c.raw_merchant_name.toLowerCase().includes(q),
        )
      : candidates;
    return [...base].sort((a, b) => {
      const aExact = Math.abs(Math.abs(Number(a.amount)) - anchorMagnitude) < 0.005 ? 1 : 0;
      const bExact = Math.abs(Math.abs(Number(b.amount)) - anchorMagnitude) < 0.005 ? 1 : 0;
      if (aExact !== bExact) return bExact - aExact;
      return b.transaction_date.localeCompare(a.transaction_date);
    });
  }, [candidates, search, anchorMagnitude]);

  const selectedSum = useMemo(() => {
    let s = 0;
    for (const c of candidates) if (selected.has(c.id)) s += Number(c.amount);
    return s;
  }, [candidates, selected]);

  // Balanced iff anchor + Σ counterparts = 0 within 1¢.
  const balance = anchorAmount + selectedSum;
  const balanced = selected.size > 0 && Math.abs(balance) < 0.005;

  const targetMagnitude = Math.abs(anchorAmount);
  const collectedMagnitude = Math.abs(selectedSum);
  const formattedTarget = formatStoredAmount(-targetMagnitude, anchorCurrency).replace(
    /^\(|\)$/g,
    "",
  );
  const formattedCollected = formatStoredAmount(
    -collectedMagnitude,
    anchorCurrency,
  ).replace(/^\(|\)$/g, "");

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleConfirm() {
    if (!anchor || !balanced) return;
    linkMutation.mutate(
      {
        transactionId: anchor.id,
        counterpartIds: Array.from(selected),
      },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  }

  const anchorMerchant = anchor ? toTitleCase(anchor.raw_merchant_name) : "";
  const anchorAmountLabel = anchor
    ? formatStoredAmount(anchorAmount, anchorCurrency)
    : "";
  const headerWord = anchorIsInflow ? "reembolso" : "gasto";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg sm:max-w-lg max-h-[90vh] sm:max-h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-slate-100">
          <DialogTitle>
            {anchor
              ? `Vincular ${headerWord} de ${anchorAmountLabel} (${anchorMerchant})`
              : "Vincular reembolso"}
          </DialogTitle>
          <DialogDescription>
            Selecciona los movimientos que se compensan con este {headerWord}. La
            suma debe dar cero.
          </DialogDescription>
        </DialogHeader>

        {/* Sticky running-total bar */}
        <div
          className={cn(
            "px-5 py-2.5 border-b border-slate-100 transition-colors",
            balanced ? "bg-emerald-50" : "bg-amber-50/70",
          )}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span
              className={cn(
                "text-[11px] font-medium uppercase tracking-wide",
                balanced ? "text-emerald-700" : "text-amber-700",
              )}
            >
              {balanced ? "Balanceado" : "Seleccionado"}
            </span>
            <span
              className={cn(
                "text-[13px] font-bold tabular-nums",
                balanced ? "text-emerald-700" : "text-amber-700",
              )}
            >
              {formattedCollected} / {formattedTarget}
              <span className="ml-1.5 text-[10px] font-medium text-slate-500">
                ({selected.size} {selected.size === 1 ? "transacción" : "transacciones"})
              </span>
            </span>
          </div>
        </div>

        {/* Filters */}
        <div className="px-5 pt-3 flex flex-col gap-2">
          <div className="flex gap-1.5 flex-wrap">
            {WINDOW_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setWindowDays(opt.value)}
                className={cn(
                  "text-[11px] font-semibold rounded-full px-2.5 py-1 border transition-colors",
                  windowDays === opt.value
                    ? "border-luka-primary bg-luka-primary text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-luka-primary/40",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar comercio…"
              className="w-full text-[13px] pl-8 pr-3 py-1.5 rounded-md border border-slate-200 bg-white focus:outline-none focus:border-luka-primary/60 focus:ring-2 focus:ring-luka-primary/10"
            />
          </div>
        </div>

        {/* Candidates list */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {isLoading && (
            <div className="space-y-2">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-lg" />
              ))}
            </div>
          )}
          {isError && (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <AlertCircle className="h-6 w-6 text-red-400" />
              <p className="text-sm text-slate-600">
                No pudimos cargar los candidatos.
              </p>
              <button
                onClick={() => refetch()}
                className="text-[12px] font-semibold text-luka-primary border border-luka-primary/40 rounded-md px-3 py-1.5 hover:bg-blue-50 transition-colors"
              >
                Reintentar
              </button>
            </div>
          )}
          {!isLoading && !isError && filtered.length === 0 && (
            <p className="text-[12px] text-slate-500 text-center py-8">
              {candidates.length === 0
                ? "No encontramos candidatos en este rango."
                : "Ningún resultado coincide con la búsqueda."}
            </p>
          )}
          {!isLoading && !isError && filtered.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {filtered.map((c) => {
                const checked = selected.has(c.id);
                const isExactMatch =
                  Math.abs(Math.abs(Number(c.amount)) - anchorMagnitude) < 0.005;
                const date = new Date(c.transaction_date).toLocaleDateString(
                  "es-CL",
                  { day: "2-digit", month: "short", year: "numeric" },
                );
                const amount = formatStoredAmount(
                  Number(c.amount),
                  c.currency ?? "CLP",
                );
                const merchant = toTitleCase(c.raw_merchant_name);
                const sourceLabel =
                  c.source_type === "email"
                    ? "email"
                    : c.source_type === "plaid"
                      ? "plaid"
                      : c.source_type === "connect"
                        ? "banco"
                        : "—";
                const accountName = c.bank_account_name
                  ? toTitleCase(c.bank_account_name)
                  : "—";
                return (
                  <li key={c.id}>
                    <label
                      className={cn(
                        "flex items-center gap-3 rounded-lg border px-3 py-2 cursor-pointer transition-colors",
                        checked
                          ? "border-luka-primary bg-blue-50/50"
                          : isExactMatch
                            ? "border-emerald-300 bg-emerald-50/40 hover:bg-emerald-50"
                            : "border-slate-200 bg-white hover:bg-slate-50",
                      )}
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() => toggle(c.id)}
                        aria-label={`Seleccionar ${merchant} ${amount}`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-baseline gap-2">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <p className="text-[13px] font-semibold text-luka-dark truncate">
                              {merchant}
                            </p>
                            {isExactMatch && (
                              <span className="shrink-0 text-[9px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">
                                Match
                              </span>
                            )}
                          </div>
                          <span className="text-[13px] font-bold tabular-nums text-slate-700 shrink-0">
                            {amount}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5 text-[10px] text-slate-400">
                          <span className="uppercase tracking-wide font-medium">
                            {sourceLabel}
                          </span>
                          <span>·</span>
                          <span className="truncate">{accountName}</span>
                          <span>·</span>
                          <span className="shrink-0">{date}</span>
                        </div>
                      </div>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between gap-3">
          {linkMutation.isError && (
            <p className="text-[11px] text-red-500 truncate flex-1">
              {(linkMutation.error as Error)?.message ??
                "No pudimos vincular. Intenta de nuevo."}
            </p>
          )}
          <div className="flex items-center gap-2 ml-auto">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="text-[12px] font-semibold text-slate-600 px-3 py-1.5 rounded-md hover:bg-slate-100 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={!balanced || linkMutation.isPending}
              className={cn(
                "text-[12px] font-semibold rounded-md px-3.5 py-1.5 transition-colors",
                balanced
                  ? "bg-luka-primary text-white hover:bg-luka-primary/90"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed",
                linkMutation.isPending && "opacity-60",
              )}
            >
              {linkMutation.isPending ? "Vinculando…" : "Confirmar reembolso"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
