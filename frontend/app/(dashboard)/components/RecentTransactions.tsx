"use client";
import { useState, useEffect, useMemo } from "react";
import { TrendingDown, ChevronDown, MoreHorizontal, Pencil, Calendar, Link2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Transaction, api } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { useLukaStore } from "@/app/lib/store";
import { TransactionCard } from "./TransactionCard";
import { CategoryPicker } from "./CategoryPicker";
import { SplitTypeEditor } from "./SplitTypeEditor";
import { resolveAppLocale } from "@/app/lib/locale";
import { useBreakpoint } from "@/app/lib/hooks/useBreakpoint";
import { EmptyState } from "./EmptyState";
import { PairedTransactionCard, groupPairs } from "./PairedTransactionCard";
import { LinkMatchDialog } from "./LinkMatchDialog";
import { VincularTypeDialog, type VincularType } from "./VincularTypeDialog";
import { ReimbursementLinkDialog } from "./ReimbursementLinkDialog";
import {
  useUpdateMerchantName,
  useUpdateTransactionDate,
} from "@/app/lib/hooks/useTransactions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

// Match the user's OS locale for date labels. SSR-safe via resolveAppLocale.
const RESOLVED_LOCALE = resolveAppLocale();

/* ─── Date grouping utilities ─── */

function getDateKey(iso: string): string {
  return iso.split("T")[0];
}

function formatDateHeader(dateKey: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.getTime() === today.getTime()) {
    return `Hoy, ${date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" })}`;
  }
  if (date.getTime() === yesterday.getTime()) {
    return `Ayer, ${date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" })}`;
  }
  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short" });
  }
  return date.toLocaleDateString(RESOLVED_LOCALE, { day: "2-digit", month: "short", year: "numeric" });
}

/* ─── CategoryCell (desktop inline dropdown) ─── */

interface CategoryCellProps {
  txn: Transaction;
}

const CATEGORY_COLLATOR = new Intl.Collator("es", { sensitivity: "base", numeric: true });

function CategoryCell({ txn }: CategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  // Sync if parent passes updated txn (e.g. after refetch)
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
    setLocalCategory(cat); // instant UI update

    // Optimistically patch array-shaped caches only — ["transactions","mine"]
    // and ["transactions","shared"] are Transaction[]; ["transactions","pending"]
    // is the 3-bucket PendingTransactions object which would crash .map().
    const patchCache = (old: Transaction[] | undefined) =>
      Array.isArray(old)
        ? old.map((t) => (t.id === txn.id ? { ...t, category: cat } : t))
        : old;
    queryClient.setQueriesData<Transaction[]>(
      {
        predicate: (q) => {
          const [root, bucket] = q.queryKey as unknown as [string, string];
          return root === "transactions" && (bucket === "mine" || bucket === "shared");
        },
      },
      patchCache,
    );

    try {
      await api.updateTransactionCategory(txn.id, cat);
    } catch {
      setLocalCategory(txn.category); // revert on error
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    }
  }

  return (
    <div className="relative">
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
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[160px] max-h-[320px] overflow-y-auto">
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
    </div>
  );
}

/* ─── Settled-row kebab + dialogs ─── */

function SettledRowKebab({
  txn,
  onRename,
  onEditDate,
  onLink,
}: {
  txn: Transaction;
  onRename: (txn: Transaction) => void;
  onEditDate: (txn: Transaction) => void;
  onLink: (txn: Transaction) => void;
}) {
  // Manual transfer linking only makes sense for settled, unpaired bank rows.
  // Paired rows render through PairedTransactionCard so they never reach here,
  // but we still gate on transfer/refund pair ids defensively.
  const canLink =
    (txn.source_type === "plaid" || txn.source_type === "connect") &&
    !txn.transfer_pair_id &&
    !txn.refund_pair_id &&
    !txn.reimbursement_group_id;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Acciones de transacción"
        className="flex items-center justify-center h-6 w-6 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
        onClick={(e) => e.stopPropagation()}
      >
        <MoreHorizontal size={14} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[180px]">
        <DropdownMenuItem onClick={() => onRename(txn)}>
          <Pencil className="text-slate-500" />
          Editar nombre
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onEditDate(txn)}>
          <Calendar className="text-slate-500" />
          Editar fecha
        </DropdownMenuItem>
        {canLink && (
          <DropdownMenuItem onClick={() => onLink(txn)}>
            <Link2 className="text-slate-500" />
            Vincular
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function RenameMerchantDialog({
  txn,
  open,
  onOpenChange,
}: {
  txn: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateMerchantName();

  useEffect(() => {
    if (open && txn) {
      setValue(txn.raw_merchant_name ?? "");
      setError(null);
    }
  }, [open, txn]);

  function handleSave() {
    if (!txn) return;
    const trimmed = value.trim();
    if (!trimmed) {
      setError("El nombre no puede estar vacío.");
      return;
    }
    if (trimmed === txn.raw_merchant_name) {
      onOpenChange(false);
      return;
    }
    update.mutate(
      { transactionId: txn.id, rawMerchantName: trimmed },
      {
        onSuccess: () => onOpenChange(false),
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
        <div className="space-y-2">
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
          {error && (
            <p role="alert" className="text-[12px] text-red-600">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={update.isPending}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={update.isPending}>
            {update.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditDateDialog({
  txn,
  open,
  onOpenChange,
}: {
  txn: Transaction | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const update = useUpdateTransactionDate();

  useEffect(() => {
    if (open && txn) {
      // ISO date prefix (YYYY-MM-DD) — `<input type="date">` expects this.
      setValue((txn.transaction_date ?? "").slice(0, 10));
      setError(null);
    }
  }, [open, txn]);

  function handleSave() {
    if (!txn) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      setError("Fecha inválida.");
      return;
    }
    const picked = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(picked.getTime())) {
      setError("Fecha inválida.");
      return;
    }
    // Reject future dates more than 30 days out — bank backdates are common
    // but a real-future entry is almost certainly a typo.
    const maxFuture = new Date();
    maxFuture.setUTCDate(maxFuture.getUTCDate() + 30);
    if (picked.getTime() > maxFuture.getTime()) {
      setError("La fecha está demasiado lejos en el futuro.");
      return;
    }
    if (value === (txn.transaction_date ?? "").slice(0, 10)) {
      onOpenChange(false);
      return;
    }
    update.mutate(
      { transactionId: txn.id, transactionDate: value },
      {
        onSuccess: () => onOpenChange(false),
        onError: (err) =>
          setError(
            err instanceof Error && err.message
              ? `No pudimos guardar: ${err.message}`
              : "No pudimos guardar la fecha.",
          ),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar fecha</DialogTitle>
          <DialogDescription>
            Corrige la fecha de esta transacción. La usaremos en tus reportes y resúmenes.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Input
            autoFocus
            type="date"
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
          />
          {error && (
            <p role="alert" className="text-[12px] text-red-600">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={update.isPending}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={update.isPending}>
            {update.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ─── RecentTransactions ─── */

interface RecentTransactionsProps {
  transactions: Transaction[];
  compact?: boolean;
}

export function RecentTransactions({
  transactions,
  compact = false,
}: RecentTransactionsProps) {
  const isMobile = useBreakpoint("lg");
  const showCuotaButton = useLukaStore((s) => s.showCuotaButton);
  const [categorySheet, setCategorySheet] = useState<Transaction | null>(null);
  const [renameTarget, setRenameTarget] = useState<Transaction | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [editDateTarget, setEditDateTarget] = useState<Transaction | null>(null);
  const [editDateOpen, setEditDateOpen] = useState(false);
  const [linkTarget, setLinkTarget] = useState<Transaction | null>(null);
  // Type picker stage (Transferencia vs. Reembolso). Once the user picks
  // we hand off to the proper dialog (LinkMatchDialog or ReimbursementLinkDialog).
  const [vincularPickerOpen, setVincularPickerOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [reimbursementOpen, setReimbursementOpen] = useState(false);
  const queryClient = useQueryClient();

  if (!transactions.length) {
    return <EmptyState icon={TrendingDown} message="No hay transacciones." height={140} />;
  }

  async function handleCategorySelect(txn: Transaction, category: string | null) {
    const patchCache = (old: Transaction[] | undefined) =>
      Array.isArray(old)
        ? old.map((t) => (t.id === txn.id ? { ...t, category } : t))
        : old;
    queryClient.setQueriesData<Transaction[]>(
      {
        predicate: (q) => {
          const [root, bucket] = q.queryKey as unknown as [string, string];
          return root === "transactions" && (bucket === "mine" || bucket === "shared");
        },
      },
      patchCache,
    );

    try {
      await api.updateTransactionCategory(txn.id, category);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    }
  }

  const allItems = groupPairs(transactions);

  function getItemDateKey(item: import("./PairedTransactionCard").TransactionOrPair): string {
    if (item.kind === "single") return getDateKey(item.txn.transaction_date);
    let maxDate = item.legs[0].transaction_date;
    for (let i = 1; i < item.legs.length; i++) {
      if (item.legs[i].transaction_date > maxDate) maxDate = item.legs[i].transaction_date;
    }
    return getDateKey(maxDate);
  }

  const dateGroups = new Map<string, import("./PairedTransactionCard").TransactionOrPair[]>();
  for (const item of allItems) {
    const key = getItemDateKey(item);
    if (!dateGroups.has(key)) dateGroups.set(key, []);
    dateGroups.get(key)!.push(item);
  }

  const sortedDates = Array.from(dateGroups.keys()).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-1">
      {sortedDates.map((dateKey) => {
        const items = dateGroups.get(dateKey)!;
        return (
          <div key={dateKey}>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest pt-3 pb-1.5">
              {formatDateHeader(dateKey)}
            </p>
            <div className="space-y-1.5">
              {items.map((item) => {
                if (item.kind === "pair") {
                  return (
                    <PairedTransactionCard
                      key={item.pairId}
                      pairId={item.pairId}
                      pairType={item.pairType}
                      legs={item.legs}
                    />
                  );
                }
                const txn = item.txn;
                /* Compact mode: simple card, no editing */
                if (compact) {
                  return <TransactionCard key={txn.id} txn={txn} compact />;
                }

                /* Non-compact: delegate to TransactionCard with slotted editors.
                 * Mobile → category opens a bottom sheet via onCategoryTap.
                 * Desktop → inline CategoryCell dropdown via categorySlot. */
                return (
                  <TransactionCard
                    key={txn.id}
                    txn={txn}
                    displayName={txn.display_name}
                    onCategoryTap={isMobile ? (t) => setCategorySheet(t) : undefined}
                    categorySlot={!isMobile ? <CategoryCell txn={txn} /> : undefined}
                    splitSlot={<SplitTypeEditor txn={txn} isMobile={isMobile} />}
                    enableMarkCuota={showCuotaButton}
                    actionsSlot={
                      <SettledRowKebab
                        txn={txn}
                        onRename={(t) => {
                          setRenameTarget(t);
                          setRenameOpen(true);
                        }}
                        onEditDate={(t) => {
                          setEditDateTarget(t);
                          setEditDateOpen(true);
                        }}
                        onLink={(t) => {
                          setLinkTarget(t);
                          setVincularPickerOpen(true);
                        }}
                      />
                    }
                  />
                );
              })}
            </div>
          </div>
        );
      })}

      <RenameMerchantDialog
        txn={renameTarget}
        open={renameOpen}
        onOpenChange={(v) => {
          setRenameOpen(v);
          if (!v) setRenameTarget(null);
        }}
      />
      <EditDateDialog
        txn={editDateTarget}
        open={editDateOpen}
        onOpenChange={(v) => {
          setEditDateOpen(v);
          if (!v) setEditDateTarget(null);
        }}
      />
      <VincularTypeDialog
        open={vincularPickerOpen}
        onOpenChange={(v) => {
          setVincularPickerOpen(v);
          if (!v && !linkOpen && !reimbursementOpen) setLinkTarget(null);
        }}
        onPick={(type: VincularType) => {
          setVincularPickerOpen(false);
          if (type === "transfer") setLinkOpen(true);
          else setReimbursementOpen(true);
        }}
      />
      <LinkMatchDialog
        pendingTransaction={linkTarget}
        open={linkOpen}
        onOpenChange={(v) => {
          setLinkOpen(v);
          if (!v) setLinkTarget(null);
        }}
        intent="transfer"
      />
      <ReimbursementLinkDialog
        anchor={linkTarget}
        open={reimbursementOpen}
        onOpenChange={(v) => {
          setReimbursementOpen(v);
          if (!v) setLinkTarget(null);
        }}
      />

      {/* Mobile category picker */}
      {categorySheet && (
        <CategoryPicker
          open={!!categorySheet}
          onClose={() => setCategorySheet(null)}
          currentCategory={categorySheet.category}
          dominantSign={Number(categorySheet.amount) > 0 ? "positive" : "negative"}
          onSelect={(cat) => {
            handleCategorySelect(categorySheet, cat);
            setCategorySheet(null);
          }}
        />
      )}
    </div>
  );
}
