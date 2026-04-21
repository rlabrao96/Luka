// frontend/app/(dashboard)/components/PendingBlock.tsx
"use client";
import { useState, useEffect } from "react";
import { usePendingTransactions } from "@/app/lib/hooks/useTransactions";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Transaction, type PendingTransactions } from "@/app/lib/api";
import { Trash2, ChevronDown, TrendingDown, TrendingUp, ArrowLeftRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { CategoryBottomSheet } from "./CategoryBottomSheet";
import { SplitTypeEditor } from "./SplitTypeEditor";
import { formatStoredAmount, isNegativeStored } from "@/app/lib/currency";

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


function toTitleCase(str: string) {
  return str.toLowerCase().split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

/* ─── Inline category dropdown (matches CategoryCell in RecentTransactions) ─── */

interface PendingCategoryCellProps {
  txn: Transaction;
}

function PendingCategoryCell({ txn }: PendingCategoryCellProps) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const { expense: expenseCats, income: incomeCats } = useCategories();
  const isIncome = Number(txn.amount) > 0 && txn.transaction_type !== "transfer";
  const categories = isIncome ? incomeCats : expenseCats;

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
          <div className="absolute left-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[160px]">
            <button
              onClick={() => handleSelect(null)}
              className="w-full text-left px-3 py-1.5 text-[11px] text-slate-400 hover:bg-slate-50"
            >
              Sin categoría
            </button>
            <div className="border-t border-slate-100 my-1" />
            {categories.map((cat) => (
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
        </>
      )}
    </div>
  );
}

/* ─── Inline split-type dropdown (same UX as category dropdown) ─── */

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

/* ─── Mobile category pill (opens bottom sheet) ─── */

function PendingCategoryPill({ txn }: { txn: Transaction }) {
  const [open, setOpen] = useState(false);
  const [localCategory, setLocalCategory] = useState(txn.category);
  const queryClient = useQueryClient();

  useEffect(() => { setLocalCategory(txn.category); }, [txn.category]);

  const isIncome = Number(txn.amount) > 0 && txn.transaction_type !== "transfer";

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
          "text-[9px] font-medium px-1.5 py-0.5 rounded max-w-[80px] text-center truncate cursor-pointer hover:opacity-80",
          localCategory ? "bg-slate-100 text-slate-600" : "bg-amber-50 text-amber-600"
        )}
      >
        {localCategory ?? "Sin categoría"}
      </button>
      <CategoryBottomSheet
        open={open}
        onClose={() => setOpen(false)}
        currentCategory={localCategory}
        isIncome={isIncome}
        onSelect={handleSelect}
      />
    </>
  );
}

/* ─── PendingSection ─── */

interface PendingSectionProps {
  title: string;
  transactions: Transaction[];
  isMobile: boolean;
  renderAction?: (txn: Transaction) => React.ReactNode;
  borderLeft?: boolean;
}

function PendingSection({ title, transactions, isMobile, renderAction, borderLeft }: PendingSectionProps) {
  if (transactions.length === 0) return null;
  return (
    <div className="mt-3 first:mt-0">
      <p className="text-[10px] uppercase tracking-wide font-semibold text-orange-800 mb-1.5 pl-1">
        {title}
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

          return (
            <div
              key={txn.id}
              className={cn(
                "bg-white rounded-xl p-3 sm:p-3.5 border border-slate-100 shadow-[var(--shadow-card)]",
                borderLeft ? "border-l-[3px] border-l-amber-400" : ""
              )}
            >
              <div className="flex items-center gap-2 sm:gap-3">
                {/* Direction icon — hidden on mobile to save space */}
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

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {/* Line 1: Email badge + Merchant + Amount */}
                  <div className="flex justify-between items-baseline gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={cn(
                        "text-[8px] sm:text-[9px] px-1 py-0.5 rounded font-medium shrink-0",
                        txn.source_type === "plaid" ? "bg-emerald-50 text-emerald-500" : "bg-blue-50 text-blue-500"
                      )}>
                        {txn.source_type === "plaid" ? "bank" : "email"}
                      </span>
                      <p className="text-[13px] sm:text-sm font-semibold text-luka-dark truncate">
                        {toTitleCase(txn.raw_merchant_name)}
                      </p>
                    </div>
                    <span
                      className={cn(
                        "text-[13px] sm:text-[15px] font-bold tabular-nums shrink-0",
                        isTransfer ? "text-sky-500" : isOutflow ? "text-red-500" : "text-luka-success"
                      )}
                    >
                      {formattedAmount}
                    </span>
                  </div>

                  {/* Line 2: Bank name + Date + Category + Split + Action */}
                  <div className="flex justify-between items-center mt-1">
                    <div className="flex items-center gap-1 sm:gap-1.5 min-w-0">
                      <span className="text-[9px] sm:text-[10px] text-slate-400 shrink-0">
                        {bankName ? toTitleCase(bankName) : "—"}
                      </span>
                      <span className="text-[9px] sm:text-[10px] text-slate-300 shrink-0">
                        {new Date(txn.transaction_date).toLocaleDateString("es-CL", { day: "2-digit", month: "short" })}
                      </span>
                      {txn.transaction_type === "transfer" ? (
                        <span className="text-[9px] sm:text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                          Ajuste entre cuentas
                        </span>
                      ) : isMobile ? (
                        <PendingCategoryPill txn={txn} />
                      ) : (
                        <PendingCategoryCell txn={txn} />
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {txn.transaction_type !== "transfer" && (
                        isMobile ? (
                          <SplitTypeEditor txn={txn} isMobile={true} />
                        ) : (
                          <PendingSplitCell txn={txn} />
                        )
                      )}
                      {renderAction?.(txn)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── PendingBlock ─── */

export function PendingBlock() {
  const { data, isLoading } = usePendingTransactions();
  const queryClient = useQueryClient();
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const isMobile = useIsMobile();

  if (isLoading || !data) return null;

  const { awaiting_reconciliation, unmatched_email } = data;
  const total = awaiting_reconciliation.length + unmatched_email.length;

  if (total === 0) return null;

  function handleDelete(id: string) {
    const queryKey = ["transactions", "pending"];
    const previous = queryClient.getQueryData(queryKey);
    setConfirmingId(null);
    queryClient.setQueryData(queryKey, (old: typeof data) => {
      if (!old) return old;
      return { ...old, unmatched_email: old.unmatched_email.filter((t) => t.id !== id) };
    });
    api.deleteTransaction(id)
      .catch(() => queryClient.setQueryData(queryKey, previous));
  }

  return (
    <div className="bg-orange-50 border border-orange-300 rounded-xl p-4">
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center gap-2 mb-1 w-full"
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

      {!collapsed && <>
      <PendingSection
        title="Esperando confirmación bancaria"
        transactions={awaiting_reconciliation}
        isMobile={isMobile}
      />

      <PendingSection
        title="Sin match bancario"
        transactions={unmatched_email}
        isMobile={isMobile}
        borderLeft
        renderAction={(txn) =>
          confirmingId === txn.id ? (
            <div className="flex items-center gap-1">
              <span className="text-[11px] text-slate-500">¿Eliminar?</span>
              <button
                onClick={() => handleDelete(txn.id)}
                className="text-[11px] font-semibold text-white bg-red-500 rounded-md px-2 py-1 hover:bg-red-600 transition-colors"
              >
                Sí
              </button>
              <button
                onClick={() => setConfirmingId(null)}
                className="text-[11px] font-medium text-slate-500 border border-slate-200 rounded-md px-2 py-1 hover:bg-slate-50 transition-colors"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmingId(txn.id)}
              className="flex items-center gap-1 text-[11px] font-medium text-red-600 border border-red-300 rounded-md px-2 py-1 hover:bg-red-50 transition-colors"
            >
              <Trash2 size={11} />
              Eliminar
            </button>
          )
        }
      />
      </>}
    </div>
  );
}
