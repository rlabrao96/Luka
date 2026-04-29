// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { useState, useEffect, useMemo } from "react";
import {
  usePendingTransactions,
  useDismissTransaction,
  useDeleteTransaction,
  useBulkAction,
  useUpdateMerchantName,
  useMerchantNameMatchingCount,
} from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction, type PendingTransactions } from "@/app/lib/api";
import {
  Trash2,
  ChevronDown,
  TrendingDown,
  TrendingUp,
  ArrowLeftRight,
  MoreHorizontal,
  Link2,
  Check,
  AlertCircle,
  Pencil,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { CategoryPicker } from "./CategoryPicker";
import { CategoryBulkApplyToast } from "./CategoryBulkApplyToast";
import { SplitTypeEditor } from "./SplitTypeEditor";
import { formatStoredAmount, isNegativeStored } from "@/app/lib/currency";
import { toTitleCase } from "@/app/lib/strings";
import { LinkMatchDialog } from "./LinkMatchDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const BULK_SELECTION_CAP = 100;

function useIsMobile() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    setMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return mobile;
}


/**
 * Age badge measures how long a pending row has been sitting in the backlog,
 * which is "time since ingestion" — NOT "time since the charge posted".
 * A txn dated 14-abr ingested today should read "hace 0d", not "hace 6d".
 *
 * Prefers `created_at` (ingestion time). Falls back to `transaction_date`
 * only when the backend omits it, for defense in depth.
 */
function ageBadge(txn: Transaction): { label: string; className: string } | null {
  const anchor = txn.created_at ?? txn.transaction_date;
  if (!anchor) return null;
  const ms = Date.now() - new Date(anchor).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days < 0) return null;
  if (days < 3) return { label: "Nuevo", className: "bg-emerald-100 text-emerald-800" };
  if (days < 8) return { label: `hace ${days}d`, className: "bg-amber-100 text-amber-800" };
  return { label: `hace ${days}d`, className: "bg-red-100 text-red-700" };
}

/**
 * Inline (no-pill) variant of ageBadge: returns just the label and the
 * color class, for the mobile 3-row layout where the age tag is rendered
 * as colored text alongside `bank · date`.
 */
function ageInline(txn: Transaction): { label: string; colorClass: string } | null {
  const anchor = txn.created_at ?? txn.transaction_date;
  if (!anchor) return null;
  const ms = Date.now() - new Date(anchor).getTime();
  const days = Math.floor(ms / 86_400_000);
  if (days < 0) return null;
  if (days < 3) return { label: "Nuevo", colorClass: "text-emerald-600 font-semibold" };
  if (days < 8) return { label: `hace ${days}d`, colorClass: "text-amber-700 font-semibold" };
  return { label: `hace ${days}d`, colorClass: "text-red-600 font-semibold" };
}

const CATEGORY_COLLATOR = new Intl.Collator("es", { sensitivity: "base", numeric: true });

/* ─── Inline category dropdown ─── */

interface PendingCategoryCellProps {
  txn: Transaction;
}

function PendingCategoryCell({ txn }: PendingCategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const [bulkPrompt, setBulkPrompt] = useState<{
    category: string | null;
    count: number;
    merchantName: string;
  } | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const { expense: expenseCats, income: incomeCats } = useCategories();
  const sortedExpense = useMemo(
    () => [...expenseCats].sort((a, b) => CATEGORY_COLLATOR.compare(a, b)),
    [expenseCats]
  );
  const sortedIncome = useMemo(
    () => [...incomeCats].sort((a, b) => CATEGORY_COLLATOR.compare(a, b)),
    [incomeCats]
  );
  const incomeFirst = Number(txn.amount) > 0 && txn.transaction_type !== "transfer";

  async function handleSelect(cat: string | null) {
    setOpen(false);
    setLocalCategory(cat);
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    queryClient.setQueryData(queryKey, (old: PendingTransactions | undefined) => {
      if (!old) return old;
      const patch = (list: Transaction[]) =>
        list.map((t) => (t.id === txn.id ? { ...t, category: cat } : t));
      return {
        ...old,
        awaiting_reconciliation: patch(old.awaiting_reconciliation),
        needs_classification: patch(old.needs_classification),
        unmatched_email: patch(old.unmatched_email),
      };
    });
    try {
      await api.updateTransactionCategory(txn.id, cat);
      try {
        const res = await api.getCategoryMatchingCount(txn.id, cat);
        if (res.count > 0) {
          setBulkPrompt({
            category: cat,
            count: res.count,
            merchantName: res.raw_merchant_name,
          });
        }
      } catch {
        // Anchor update succeeded — non-fatal.
      }
    } catch {
      queryClient.setQueryData(queryKey, previous);
    }
  }

  return (
    <div className="relative flex flex-col items-start gap-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center justify-between gap-1 text-[11px] font-medium px-2 py-1 rounded-md border transition-colors w-[140px]",
          localCategory
            ? "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
            : "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100"
        )}
      >
        <span className="truncate">{localCategory ?? "Sin categoría"}</span>
        <ChevronDown size={10} className="shrink-0" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[160px] max-h-[320px] overflow-y-auto">
            <button
              onClick={() => handleSelect(null)}
              className="w-full text-left px-3 py-1.5 text-[11px] text-slate-400 hover:bg-slate-50"
            >
              Sin categoría
            </button>
            {(incomeFirst
              ? [
                  { label: "Ingresos", items: sortedIncome },
                  { label: "Gastos", items: sortedExpense },
                ]
              : [
                  { label: "Gastos", items: sortedExpense },
                  { label: "Ingresos", items: sortedIncome },
                ]
            ).map(({ label, items }) =>
              items.length === 0 ? null : (
                <div key={label}>
                  <div className="border-t border-slate-100 my-1" />
                  <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-900">
                    {label}
                  </div>
                  {items.map((cat) => (
                    <button
                      key={cat}
                      onClick={() => handleSelect(cat)}
                      className={cn(
                        "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                        localCategory === cat ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
                      )}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )
            )}
          </div>
        </>
      )}
      {bulkPrompt && (
        <CategoryBulkApplyToast
          transactionId={txn.id}
          category={bulkPrompt.category}
          merchantName={bulkPrompt.merchantName}
          matchingCount={bulkPrompt.count}
          onClose={() => setBulkPrompt(null)}
        />
      )}
    </div>
  );
}

/* ─── Inline split-type dropdown ─── */

const SPLIT_OPTIONS = [
  { value: "personal", label: "Personal", className: "bg-blue-50 text-blue-600 border-blue-200 hover:bg-blue-100" },
  { value: "shared", label: "Compartido", className: "bg-emerald-50 text-emerald-600 border-emerald-200 hover:bg-emerald-100" },
];

function PendingSplitCell({ txn }: { txn: Transaction }) {
  const [open, setOpen] = useState(false);
  const [localSplit, setLocalSplit] = useState(txn.split_type);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalSplit(txn.split_type); }, [txn.split_type]);

  const current = SPLIT_OPTIONS.find((o) => o.value === localSplit);

  async function handleSelect(value: string) {
    setOpen(false);
    setLocalSplit(value);
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    queryClient.setQueryData(queryKey, (old: PendingTransactions | undefined) => {
      if (!old) return old;
      const patch = (list: Transaction[]) =>
        list.map((t) => (t.id === txn.id ? { ...t, split_type: value } : t));
      return {
        ...old,
        awaiting_reconciliation: patch(old.awaiting_reconciliation),
        needs_classification: patch(old.needs_classification),
        unmatched_email: patch(old.unmatched_email),
      };
    });
    try {
      await api.updateTransactionSplitType(txn.id, value);
    } catch {
      queryClient.setQueryData(queryKey, previous);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center justify-between gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md border transition-colors w-[90px]",
          current
            ? current.className
            : "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100"
        )}
      >
        <span className="truncate">{current?.label ?? "Asignar"}</span>
        <ChevronDown size={9} className="shrink-0" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[110px]">
            {SPLIT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleSelect(opt.value)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                  localSplit === opt.value ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Mobile category pill ─── */

function PendingCategoryPill({ txn, expand = false }: { txn: Transaction; expand?: boolean }) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const dominantSign: "positive" | "negative" =
    Number(txn.amount) > 0 && txn.transaction_type !== "transfer" ? "positive" : "negative";

  async function handleSelect(cat: string | null) {
    setLocalCategory(cat);
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    queryClient.setQueryData(queryKey, (old: PendingTransactions | undefined) => {
      if (!old) return old;
      const patch = (list: Transaction[]) =>
        list.map((t) => (t.id === txn.id ? { ...t, category: cat } : t));
      return {
        ...old,
        awaiting_reconciliation: patch(old.awaiting_reconciliation),
        needs_classification: patch(old.needs_classification),
        unmatched_email: patch(old.unmatched_email),
      };
    });
    try {
      await api.updateTransactionCategory(txn.id, cat);
    } catch {
      queryClient.setQueryData(queryKey, previous);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "font-medium rounded cursor-pointer hover:opacity-80",
          expand
            ? "text-[11px] px-2 py-1 max-w-full text-left truncate"
            : "text-[9px] px-1.5 py-0.5 max-w-[80px] text-center truncate",
          localCategory ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600"
        )}
      >
        {localCategory ?? "Sin categoría"}
      </button>
      <CategoryPicker
        open={open}
        onClose={() => setOpen(false)}
        currentCategory={localCategory}
        dominantSign={dominantSign}
        onSelect={handleSelect}
      />
    </>
  );
}

/* ─── Per-row action menu ─── */

type BucketKind = "awaiting_reconciliation" | "needs_classification" | "unmatched_email";

interface RowActionMenuProps {
  txn: Transaction;
  bucket: BucketKind;
  onLink: (txn: Transaction) => void;
  onRequestDelete: (id: string) => void;
  onRename: (txn: Transaction) => void;
}

function RowActionMenu({ txn, bucket, onLink, onRequestDelete, onRename }: RowActionMenuProps) {
  const dismiss = useDismissTransaction();
  const canLink = bucket === "awaiting_reconciliation" || bucket === "unmatched_email";
  // Dismiss + delete are email-only: the backend rejects non-email rows because
  // Plaid owns the lifecycle of bank transactions. For bank-pending rows we
  // only show Vincular (manual match), which is valid for both sources.
  const isEmail = txn.source_type === "email";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Acciones de transacción"
        className="flex items-center justify-center h-7 w-7 rounded-md text-slate-500 hover:bg-slate-100 border border-slate-200 transition-colors"
      >
        <MoreHorizontal size={14} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[180px]">
        <DropdownMenuItem onClick={() => onRename(txn)}>
          <Pencil className="text-slate-500" />
          Editar nombre
        </DropdownMenuItem>
        {canLink && (
          <DropdownMenuItem onClick={() => onLink(txn)}>
            <Link2 className="text-slate-500" />
            Vincular…
          </DropdownMenuItem>
        )}
        {isEmail && (
          <>
            <DropdownMenuItem
              onClick={() => dismiss.mutate(txn.id)}
              disabled={dismiss.isPending}
            >
              <Check className="text-slate-500" />
              Marcar como resuelta
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onClick={() => onRequestDelete(txn.id)}
            >
              <Trash2 />
              Eliminar
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/* ─── Rename dialog ─── */

interface RenameDialogProps {
  txn: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function RenameMerchantDialog({ txn, open, onOpenChange }: RenameDialogProps) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [applyToAll, setApplyToAll] = useState(true);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const update = useUpdateMerchantName();

  const trimmed = value.trim();
  const original = txn?.raw_merchant_name ?? "";
  // Only fetch the count when the user has typed a different non-trivial
  // name — avoids hammering the endpoint on every keystroke.
  const countEnabled =
    !!txn && open && trimmed.length >= 2 && trimmed !== original;
  const matchingCountQ = useMerchantNameMatchingCount(
    txn?.id ?? null,
    countEnabled,
  );
  const matchingCount = matchingCountQ.data?.count ?? 0;

  useEffect(() => {
    if (open && txn) {
      setValue(txn.raw_merchant_name ?? "");
      setError(null);
      setApplyToAll(true);
      setSuccessMsg(null);
    }
  }, [open, txn]);

  async function handleSave() {
    if (!txn) return;
    if (!trimmed) {
      setError("El nombre no puede estar vacío.");
      return;
    }
    if (trimmed === txn.raw_merchant_name) {
      onOpenChange(false);
      return;
    }
    const useBulk = applyToAll && matchingCount > 0;
    update.mutate(
      {
        transactionId: txn.id,
        rawMerchantName: trimmed,
        applyToAllMatching: useBulk,
      },
      {
        onSuccess: (res) => {
          if (useBulk && res.updated_count > 1) {
            setSuccessMsg(`Renombramos ${res.updated_count} transacciones.`);
          } else {
            setSuccessMsg("Nombre actualizado.");
          }
          // Brief confirmation before closing.
          setTimeout(() => onOpenChange(false), 900);
        },
        onError: (err) =>
          setError(
            err instanceof Error && err.message
              ? `No pudimos guardar: ${err.message}`
              : "No pudimos guardar el nuevo nombre.",
          ),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar nombre</DialogTitle>
          <DialogDescription>
            Cambia cómo se ve este comercio en tu lista. Lo recordaremos para esta transacción.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Input
            autoFocus
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSave();
              }
            }}
            placeholder="Nombre del comercio"
            maxLength={255}
          />
          {countEnabled && matchingCount > 0 && !successMsg && (
            <div className="space-y-1 rounded-md bg-slate-50 p-2.5">
              <label className="flex cursor-pointer items-start gap-2 text-[13px] text-slate-800">
                <Checkbox
                  checked={applyToAll}
                  onCheckedChange={(v) => setApplyToAll(v === true)}
                  className="mt-0.5"
                />
                <span>
                  Aplicar a las otras {matchingCount} transacciones de{" "}
                  <span className="font-medium">
                    &ldquo;{original}&rdquo;
                  </span>
                </span>
              </label>
              <p className="pl-6 text-[11px] text-slate-500">
                Solo se aplicará a transacciones que no hayas editado manualmente.
              </p>
            </div>
          )}
          {successMsg && (
            <p className="rounded-md bg-emerald-50 px-2.5 py-2 text-[13px] text-emerald-700">
              {successMsg}
            </p>
          )}
          {error && (
            <p role="alert" className="text-[12px] text-red-600">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={update.isPending}
          >
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={update.isPending || !!successMsg}>
            {update.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ─── PendingSection ─── */

interface PendingSectionProps {
  title: string;
  transactions: Transaction[];
  isMobile: boolean;
  bucket: BucketKind;
  borderLeft?: boolean;
  selectMode: boolean;
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onLink: (txn: Transaction) => void;
  onRequestDelete: (id: string) => void;
  onRename: (txn: Transaction) => void;
}

function PendingSection({
  title,
  transactions,
  isMobile,
  bucket,
  borderLeft,
  selectMode,
  selected,
  onToggleSelect,
  onLink,
  onRequestDelete,
  onRename,
}: PendingSectionProps) {
  if (transactions.length === 0) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[10px] uppercase tracking-wide font-semibold text-orange-800 mb-1.5 pl-1 flex items-center gap-1.5">
        <span>{title}</span>
        <span className="bg-orange-200 text-orange-800 rounded-full px-1.5 py-0 text-[10px] font-semibold">
          {transactions.length}
        </span>
      </p>
      <div className="space-y-2">
        {transactions.map((txn) => {
          const amount = Number(txn.amount);
          const isTransfer = txn.transaction_type === "transfer";
          const isOutflow = isNegativeStored(amount);
          const currency = txn.currency ?? "CLP";
          const formattedAmount = isTransfer || isOutflow
            ? `(${formatStoredAmount(amount, currency)})`
            : `+${formatStoredAmount(amount, currency)}`;
          const bankName = txn.bank_name;
          const age = ageBadge(txn);
          const ageInlineTag = ageInline(txn);
          const isChecked = selected.has(txn.id);
          const isNegativeAmount = isTransfer || isOutflow;
          const dateText = new Date(txn.transaction_date).toLocaleDateString("es-CL", { day: "2-digit", month: "short" });

          const sourceChip = (
            <span className={cn(
              "text-[8px] sm:text-[9px] px-1 py-0.5 rounded font-medium shrink-0",
              txn.source_type === "plaid" ? "bg-emerald-50 text-emerald-500" : "bg-blue-50 text-blue-500"
            )}>
              {txn.source_type === "plaid" ? "bank" : "email"}
            </span>
          );

          const merchantText = (
            <p className="text-[13px] sm:text-sm font-semibold text-luka-dark truncate">
              {toTitleCase(txn.raw_merchant_name)}
            </p>
          );

          const amountSpan = (
            <span
              className={cn(
                "text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0",
                isTransfer ? "text-sky-500" : isOutflow ? "text-red-500" : "text-luka-success"
              )}
              aria-label={isNegativeAmount ? `menos ${formatStoredAmount(amount, currency)}` : undefined}
            >
              {formattedAmount}
            </span>
          );

          const splitPill = txn.transaction_type !== "transfer"
            ? (isMobile ? <SplitTypeEditor txn={txn} isMobile={true} /> : <PendingSplitCell txn={txn} />)
            : null;

          const rowActionMenu = !selectMode ? (
            <RowActionMenu
              txn={txn}
              bucket={bucket}
              onLink={onLink}
              onRequestDelete={onRequestDelete}
              onRename={onRename}
            />
          ) : null;

          return (
            <div
              key={txn.id}
              className={cn(
                "bg-white rounded-xl p-3 sm:p-3.5 border border-slate-100 shadow-[var(--shadow-card)]",
                borderLeft ? "border-l-[3px] border-l-amber-400" : "",
                selectMode && isChecked ? "ring-2 ring-luka-primary/30" : ""
              )}
            >
              {isMobile ? (
                <div className="grid grid-cols-[1fr_auto] gap-x-2.5 gap-y-1.5 items-center">
                  {/* Row 1 */}
                  <div className="flex items-center gap-1.5 min-w-0">
                    {selectMode && (
                      <Checkbox
                        checked={isChecked}
                        onCheckedChange={() => onToggleSelect(txn.id)}
                        aria-label={`Seleccionar ${toTitleCase(txn.raw_merchant_name)}`}
                        className="shrink-0"
                      />
                    )}
                    {sourceChip}
                    {merchantText}
                  </div>
                  <div className="whitespace-nowrap">{amountSpan}</div>

                  {/* Row 2 */}
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-400 min-w-0 flex-wrap">
                    <span className="truncate">{bankName ? toTitleCase(bankName) : "—"}</span>
                    <span>·</span>
                    <span>{dateText}</span>
                    {ageInlineTag && (
                      <>
                        <span>·</span>
                        <span className={ageInlineTag.colorClass}>{ageInlineTag.label}</span>
                      </>
                    )}
                  </div>
                  <div className="flex items-center justify-end">
                    {splitPill}
                  </div>

                  {/* Row 3 */}
                  <div className="flex items-center min-w-0">
                    {txn.transaction_type === "transfer" ? (
                      <span className="text-[11px] font-medium px-2 py-1 rounded bg-slate-100 text-slate-500">
                        Ajuste entre cuentas
                      </span>
                    ) : (
                      <PendingCategoryPill txn={txn} expand />
                    )}
                  </div>
                  <div className="flex items-center justify-end">{rowActionMenu}</div>
                </div>
              ) : (
                <div className="flex items-center gap-2 sm:gap-3">
                  {selectMode && (
                    <Checkbox
                      checked={isChecked}
                      onCheckedChange={() => onToggleSelect(txn.id)}
                      aria-label={`Seleccionar ${toTitleCase(txn.raw_merchant_name)}`}
                      className="shrink-0"
                    />
                  )}
                  {/* Direction icon — desktop only */}
                  <div
                    className="hidden sm:flex w-[38px] h-[38px] rounded-[10px] items-center justify-center shrink-0"
                    style={{
                      background: isTransfer
                        ? "linear-gradient(135deg, #f0f9ff, #bae6fd)"
                        : isOutflow
                          ? "linear-gradient(135deg, #fef2f2, #fecaca)"
                          : "linear-gradient(135deg, #ecfdf5, #d1fae5)",
                    }}
                  >
                    {isTransfer ? (
                      <ArrowLeftRight size={16} className="text-sky-500" strokeWidth={2.5} />
                    ) : isOutflow ? (
                      <TrendingDown size={16} className="text-red-400" strokeWidth={2.5} />
                    ) : (
                      <TrendingUp size={16} className="text-emerald-500" strokeWidth={2.5} />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-baseline gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        {sourceChip}
                        {merchantText}
                      </div>
                      {amountSpan}
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
                        <span className="text-[9px] sm:text-[10px] text-slate-400 shrink-0">
                          {bankName ? toTitleCase(bankName) : "—"}
                        </span>
                        <span className="text-[9px] sm:text-[10px] text-slate-300 shrink-0">
                          {dateText}
                        </span>
                        {age && (
                          <span
                            className={cn(
                              "text-[9px] sm:text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0",
                              age.className,
                            )}
                          >
                            {age.label}
                          </span>
                        )}
                        {txn.transaction_type === "transfer" ? (
                          <span className="text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                            Ajuste entre cuentas
                          </span>
                        ) : (
                          <PendingCategoryCell txn={txn} />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {splitPill}
                        {rowActionMenu}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── PendingBlock ─── */

export function PendingBlock() {
  const { data, isLoading, isError, refetch } = usePendingTransactions();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(true);
  const isMobile = useIsMobile();

  // Link dialog state
  const [linkTarget, setLinkTarget] = useState<Transaction | null>(null);
  const [linkOpen, setLinkOpen] = useState(false);

  // Rename dialog state
  const [renameTarget, setRenameTarget] = useState<Transaction | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);

  // Delete confirmation state (single row)
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Bulk select state
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [capWarning, setCapWarning] = useState(false);

  const bulkAction = useBulkAction();
  const deleteMutation = useDeleteTransaction();
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Sort awaiting_reconciliation newest-first using created_at (matches the
  // age badge — transaction_date can disagree when banks backdate rows or
  // when legacy data has off-year dates).
  const sortedAwaiting = useMemo(() => {
    if (!data) return [];
    const keyOf = (t: Transaction) =>
      new Date(t.created_at ?? t.transaction_date).getTime();
    return [...data.awaiting_reconciliation].sort((a, b) => keyOf(b) - keyOf(a));
  }, [data]);

  if (isLoading) {
    return (
      <div className="bg-orange-50 border border-orange-300 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-6 rounded-full" />
        </div>
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="bg-orange-50 border border-orange-300 rounded-xl p-4 flex items-center gap-3">
        <AlertCircle className="h-5 w-5 text-orange-600 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-orange-800">No pudimos cargar los pendientes</p>
          <p className="text-[11px] text-orange-700/80">Intenta nuevamente en un momento.</p>
        </div>
        <button
          onClick={() => refetch()}
          className="text-[12px] font-semibold text-orange-700 border border-orange-300 rounded-md px-3 py-1.5 hover:bg-orange-100 transition-colors"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const { needs_classification, unmatched_email } = data;
  const total = sortedAwaiting.length + needs_classification.length + unmatched_email.length;
  if (total === 0) return null;

  function handleToggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= BULK_SELECTION_CAP) {
          setCapWarning(true);
          return prev;
        }
        next.add(id);
      }
      return next;
    });
  }

  function handleOpenLink(txn: Transaction) {
    setLinkTarget(txn);
    setLinkOpen(true);
  }

  function handleOpenRename(txn: Transaction) {
    setRenameTarget(txn);
    setRenameOpen(true);
  }

  function handleConfirmDelete() {
    if (!deleteId) return;
    const id = deleteId;
    setDeleteId(null);
    setDeleteError(null);
    deleteMutation.mutate(id, {
      onError: (err) => {
        setDeleteError(
          err instanceof Error && err.message
            ? `No pudimos eliminar: ${err.message}`
            : "No pudimos eliminar la transacción. Intenta nuevamente.",
        );
      },
    });
  }

  function runBulk(action: "dismiss" | "delete") {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    bulkAction.mutate(
      { transactionIds: ids, action },
      {
        onSettled: () => {
          setSelected(new Set());
          setSelectMode(false);
          setBulkDeleteOpen(false);
        },
      },
    );
  }

  function exitSelectMode() {
    setSelectMode(false);
    setSelected(new Set());
    setCapWarning(false);
  }

  const selectedCount = selected.size;

  return (
    <div className="bg-orange-50 border border-orange-300 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1">
        <button
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
          aria-controls="pending-content"
          className="flex items-center gap-2 flex-1"
        >
          <span className="text-[15px] font-bold text-orange-700">Pendientes</span>
          <span className="bg-orange-400 text-white text-[11px] font-semibold rounded-full px-2 py-0.5">
            {total}
          </span>
          <ChevronDown
            size={16}
            className={`ml-auto text-orange-400 transition-transform duration-200 ${collapsed ? "-rotate-90" : ""}`}
          />
        </button>
        {!collapsed && (
          selectMode ? (
            <button
              onClick={exitSelectMode}
              className="text-[11px] font-semibold text-slate-600 border border-slate-300 bg-white rounded-md px-2 py-1 hover:bg-slate-50 transition-colors"
            >
              Cancelar
            </button>
          ) : (
            <button
              onClick={() => setSelectMode(true)}
              className="text-[11px] font-semibold text-orange-700 border border-orange-300 bg-white rounded-md px-2 py-1 hover:bg-orange-100 transition-colors"
            >
              Seleccionar
            </button>
          )
        )}
      </div>

      {!collapsed && (
        <div id="pending-content">
          <PendingSection
            title="Esperando confirmación bancaria"
            transactions={sortedAwaiting}
            isMobile={isMobile}
            bucket="awaiting_reconciliation"
            selectMode={selectMode}
            selected={selected}
            onToggleSelect={handleToggleSelect}
            onLink={handleOpenLink}
            onRequestDelete={setDeleteId}
            onRename={handleOpenRename}
          />
          <PendingSection
            title="Falta categoría o división"
            transactions={needs_classification}
            isMobile={isMobile}
            bucket="needs_classification"
            selectMode={selectMode}
            selected={selected}
            onToggleSelect={handleToggleSelect}
            onLink={handleOpenLink}
            onRequestDelete={setDeleteId}
            onRename={handleOpenRename}
          />
          <PendingSection
            title="Sin match bancario"
            transactions={unmatched_email}
            isMobile={isMobile}
            bucket="unmatched_email"
            borderLeft
            selectMode={selectMode}
            selected={selected}
            onToggleSelect={handleToggleSelect}
            onLink={handleOpenLink}
            onRequestDelete={setDeleteId}
            onRename={handleOpenRename}
          />
        </div>
      )}

      {capWarning && (
        <p className="mt-2 text-[11px] text-amber-700 text-right">
          Máximo {BULK_SELECTION_CAP} seleccionadas a la vez.
        </p>
      )}

      {deleteError && (
        <div
          role="alert"
          className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700"
        >
          <span>{deleteError}</span>
          <button
            onClick={() => setDeleteError(null)}
            className="font-semibold text-red-700 hover:underline"
            aria-label="Cerrar"
          >
            Cerrar
          </button>
        </div>
      )}

      {/* Floating bulk toolbar */}
      {selectMode && selectedCount > 0 && (
        <div className="fixed bottom-4 right-4 z-40 bg-white border border-slate-200 shadow-xl rounded-xl p-2 flex items-center gap-2">
          <span className="text-[12px] font-semibold text-slate-700 px-2">
            {selectedCount} seleccionada{selectedCount === 1 ? "" : "s"}
          </span>
          <button
            onClick={() => runBulk("dismiss")}
            disabled={bulkAction.isPending}
            className="text-[12px] font-semibold text-luka-primary border border-luka-primary/40 rounded-md px-3 py-1.5 hover:bg-blue-50 transition-colors disabled:opacity-50"
          >
            Marcar como resueltas ({selectedCount})
          </button>
          <button
            onClick={() => setBulkDeleteOpen(true)}
            disabled={bulkAction.isPending}
            className="text-[12px] font-semibold text-red-600 border border-red-300 rounded-md px-3 py-1.5 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            Eliminar ({selectedCount})
          </button>
        </div>
      )}

      {/* Link match dialog */}
      <LinkMatchDialog
        pendingTransaction={linkTarget}
        open={linkOpen}
        onOpenChange={(v) => {
          setLinkOpen(v);
          if (!v) setLinkTarget(null);
        }}
      />

      {/* Rename merchant dialog */}
      <RenameMerchantDialog
        txn={renameTarget}
        open={renameOpen}
        onOpenChange={(v) => {
          setRenameOpen(v);
          if (!v) setRenameTarget(null);
        }}
      />

      {/* Single-row delete confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={(v) => { if (!v) setDeleteId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar esta transacción?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-red-500 hover:bg-red-600 text-white"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk delete confirmation */}
      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar {selectedCount} transacciones?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => runBulk("delete")}
              className="bg-red-500 hover:bg-red-600 text-white"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
