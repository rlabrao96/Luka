"use client";
import { useState, useMemo, useEffect } from "react";
import { ChevronDown, Tag, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, CreditCard, Landmark, RefreshCw, SlidersHorizontal } from "lucide-react";
import { FilterPanel } from "../components/FilterPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecentTransactions } from "../components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLukaStore } from "@/app/lib/store";
import { api, type Transaction, type BankAccountRow } from "@/app/lib/api";

function formatCLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function getMonthKey(iso: string) {
  // Parse date string directly to avoid timezone shift
  return iso.split("T")[0].slice(0, 7);
}

function getMonthLabel(key: string) {
  const [year, month] = key.split("-");
  const d = new Date(Number(year), Number(month) - 1, 1);
  return d.toLocaleDateString("es-CL", { month: "long", year: "numeric" });
}

const CHECKING_KINDS = new Set(["checking_account", "savings_account", "sight_account"]);
const CREDIT_KINDS = new Set(["credit_card", "line_of_credit"]);

function isChecking(kind: string | null) {
  return kind ? CHECKING_KINDS.has(kind) : false;
}
function isCredit(kind: string | null) {
  return kind ? CREDIT_KINDS.has(kind) : false;
}

interface SummaryBarProps {
  accounts: BankAccountRow[];
  sharedTxns: Transaction[];
  periodLabel: string;
  userId: string | null;
  householdId: string | null;
}

function SummaryBar({ accounts, sharedTxns, periodLabel, userId, householdId }: SummaryBarProps) {
  const [syncing, setSyncing] = useState(false);
  const queryClient = useQueryClient();

  async function handleSync() {
    if (!householdId || syncing) return;
    setSyncing(true);
    try {
      await api.syncBalances(householdId);
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
    } finally {
      setSyncing(false);
    }
  }
  const myAccounts = accounts.filter((a) => a.is_active && a.user_id === userId);

  // Sum available balances by kind
  const checkingBalance = myAccounts
    .filter((a) => a.account_type !== "joint" && isChecking(a.account_kind))
    .reduce((s, a) => s + (a.balance_available ?? 0), 0);

  const creditBalance = myAccounts
    .filter((a) => a.account_type !== "joint" && isCredit(a.account_kind))
    .reduce((s, a) => s + (a.balance_available ?? 0), 0);

  const sharedBalance = accounts
    .filter((a) => a.is_active && (a.account_type === "joint" || a.account_type === "partner"))
    .reduce((s, a) => s + (a.balance_available ?? 0), 0);

  const hasBalances = myAccounts.some((a) => a.balance_available !== null);

  // Fall back to summing expense transactions if no Fintoc balance yet
  const sharedFallback = sharedTxns
    .filter((t) => t.transaction_type === "expense")
    .reduce((s, t) => s + Number(t.amount), 0);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Saldos disponibles</span>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-1 text-[10px] font-medium text-slate-400 hover:text-luka-primary transition-colors disabled:opacity-50"
        >
          <RefreshCw size={10} className={syncing ? "animate-spin" : ""} />
          {syncing ? "Actualizando..." : "Actualizar saldos"}
        </button>
      </div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
      {[
        {
          label: `Cuenta corriente`,
          sublabel: periodLabel,
          value: hasBalances ? formatCLP(checkingBalance) : "—",
          icon: Landmark,
          iconClass: "text-luka-primary",
          iconBg: "bg-blue-50",
        },
        {
          label: `Tarjeta de crédito`,
          sublabel: periodLabel,
          value: hasBalances ? formatCLP(creditBalance) : "—",
          icon: CreditCard,
          iconClass: "text-purple-500",
          iconBg: "bg-purple-50",
        },
        {
          label: `Cuenta compartida`,
          sublabel: periodLabel,
          value: hasBalances ? formatCLP(sharedBalance) : formatCLP(sharedFallback),
          icon: SlidersHorizontal,
          iconClass: "text-emerald-500",
          iconBg: "bg-emerald-50",
        },
      ].map(({ label, sublabel, value, icon: Icon, iconClass, iconBg }) => (
        <div
          key={label}
          className="bg-white rounded-xl border border-slate-100 p-4 flex items-center gap-3"
        >
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${iconBg}`}>
            <Icon size={15} className={iconClass} strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 leading-tight">
              {label}
            </p>
            <p className="text-base font-bold text-luka-dark tabular-nums truncate">{value}</p>
          </div>
        </div>
      ))}
    </div>
    </div>
  );
}

interface TransactionTableProps {
  transactions: Transaction[];
  loading: boolean;
  page: number;
  pageSize: 10 | 30 | 100;
  onPage: (p: number) => void;
  onPageSize: (s: 10 | 30 | 100) => void;
}

function TransactionTable({ transactions, loading, page, pageSize, onPage, onPageSize }: TransactionTableProps) {
  const totalPages = Math.max(1, Math.ceil(transactions.length / pageSize));
  const start = (page - 1) * pageSize;
  const paginated = transactions.slice(start, start + pageSize);
  const from = transactions.length === 0 ? 0 : start + 1;
  const to = Math.min(start + pageSize, transactions.length);

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
      <div className="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Movimientos
        </p>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400">Ver</span>
            {([10, 30, 100] as const).map((s) => (
              <button
                key={s}
                onClick={() => onPageSize(s)}
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded transition-colors ${
                  pageSize === s
                    ? "bg-luka-primary text-white"
                    : "text-slate-500 hover:text-luka-primary"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <p className="text-[10px] text-slate-400">
            {transactions.length === 0 ? "0 resultados" : `Mostrando ${from}–${to} de ${transactions.length}`}
          </p>
        </div>
      </div>

      <div className="px-5 py-1">
        {loading ? (
          <div className="py-12 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-luka-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <RecentTransactions transactions={paginated} />
        )}
      </div>

      {totalPages > 1 && (
        <div className="px-5 py-3.5 border-t border-slate-100 flex items-center justify-between gap-4">
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPage(1)}
              disabled={page === 1}
              title="Primera página"
              className="hidden lg:flex items-center justify-center w-7 h-7 rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronsLeft size={13} />
            </button>
            <button
              onClick={() => onPage(page - 1)}
              disabled={page === 1}
              className="flex items-center gap-1 h-7 px-2.5 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-600 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={12} /> Anterior
            </button>
          </div>
          <span className="text-[11px] font-medium text-slate-500">
            Página <span className="text-luka-dark font-semibold">{page}</span> de {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPage(page + 1)}
              disabled={page === totalPages}
              className="flex items-center gap-1 h-7 px-2.5 rounded-lg border border-slate-200 bg-white text-[11px] font-medium text-slate-600 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Siguiente <ChevronRight size={12} />
            </button>
            <button
              onClick={() => onPage(totalPages)}
              disabled={page === totalPages}
              title="Última página"
              className="hidden lg:flex items-center justify-center w-7 h-7 rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronsRight size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [selectedMonth, setSelectedMonth] = useState<string>("all");
  const [selectedBank, setSelectedBank] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [onlyUncategorized, setOnlyUncategorized] = useState(false);
  const [pageSize, setPageSize] = useState<10 | 30 | 100>(30);
  const [page, setPage] = useState(1);

  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);

  const { data: myTxns = [], isLoading: loadingMine } = useMyTransactions();
  const { data: sharedTxns = [], isLoading: loadingShared } = useSharedTransactions();
  const { data: accounts = [] } = useQuery<BankAccountRow[]>({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

  const monthOptions = useMemo(() => {
    const keys = new Set<string>();
    [...myTxns, ...sharedTxns].forEach((t) => keys.add(getMonthKey(t.transaction_date)));
    return Array.from(keys).sort().reverse();
  }, [myTxns, sharedTxns]);

  const bankOptions = useMemo(() => {
    const banks = new Set<string>();
    [...myTxns, ...sharedTxns].forEach((t) => { if (t.bank_name) banks.add(t.bank_name); });
    return Array.from(banks).sort();
  }, [myTxns, sharedTxns]);

  const categoryOptions = useMemo(() => {
    const cats = new Set<string>();
    [...myTxns, ...sharedTxns].forEach((t) => { if (t.category) cats.add(t.category); });
    return Array.from(cats).sort();
  }, [myTxns, sharedTxns]);

  const applyFilters = (txns: Transaction[]) => {
    let result = txns;
    if (selectedMonth !== "all") result = result.filter((t) => getMonthKey(t.transaction_date) === selectedMonth);
    if (selectedBank !== "all") result = result.filter((t) => t.bank_name === selectedBank);
    if (onlyUncategorized) {
      result = result.filter((t) => !t.category);
    } else if (selectedCategory !== "all") {
      result = result.filter((t) => t.category === selectedCategory);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (t) =>
          t.raw_merchant_name.toLowerCase().includes(q) ||
          (t.category ?? "").toLowerCase().includes(q) ||
          (t.bank_name ?? "").toLowerCase().includes(q)
      );
    }
    return result;
  };

  // Map bank_account_id → account_type for client-side filtering
  const accountTypeMap = useMemo(() => {
    const map = new Map<string, string>();
    accounts.forEach((a) => map.set(a.id, a.account_type));
    return map;
  }, [accounts]);

  // Personal = only transactions from personal/partner accounts (not joint)
  const personalTxns = useMemo(() => {
    if (accountTypeMap.size === 0) return myTxns; // accounts not loaded yet, show all
    return myTxns.filter((t) => {
      const type = t.bank_account_id ? accountTypeMap.get(t.bank_account_id) : undefined;
      return type !== "joint";
    });
  }, [myTxns, accountTypeMap]);

  useEffect(() => { setPage(1); }, [selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search]);

  const filteredMine = useMemo(() => applyFilters(personalTxns), [personalTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search]);
  const filteredShared = useMemo(() => applyFilters(sharedTxns), [sharedTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search]);
  const filteredAll = useMemo(() => {
    const combined = [...myTxns, ...sharedTxns];
    // dedupe by id
    const seen = new Set<string>();
    const unique = combined.filter((t) => { if (seen.has(t.id)) return false; seen.add(t.id); return true; });
    return applyFilters(unique).sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  }, [myTxns, sharedTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search]);

  const now = new Date();
  const currentMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const periodLabel = selectedMonth === "all"
    ? "este mes"
    : getMonthLabel(selectedMonth);
  const summaryShared = selectedMonth === "all"
    ? sharedTxns.filter((t) => getMonthKey(t.transaction_date) === currentMonthKey)
    : filteredShared;

  const selectClass =
    "h-8 rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-luka-primary appearance-none pr-7 cursor-pointer";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Transacciones</h2>
        <p className="text-sm text-luka-muted mt-0.5">Historial de movimientos</p>
      </div>

      {/* Filters */}
      <FilterPanel
        activeCount={[
          selectedMonth !== "all" ? 1 : 0,
          selectedBank !== "all" ? 1 : 0,
          selectedCategory !== "all" ? 1 : 0,
          onlyUncategorized ? 1 : 0,
        ].reduce((a, b) => a + b, 0)}
        onClear={() => {
          setSelectedMonth("all");
          setSelectedBank("all");
          setSelectedCategory("all");
          setOnlyUncategorized(false);
          setSearch("");
        }}
        searchValue={search}
        onSearchChange={setSearch}
      >
        {/* Month dropdown */}
        <div className="relative">
          <select value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)} className={selectClass}>
            <option value="all">Todos los meses</option>
            {monthOptions.map((m) => (
              <option key={m} value={m}>{getMonthLabel(m)}</option>
            ))}
          </select>
          <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        </div>

        {/* Bank dropdown */}
        {bankOptions.length > 0 && (
          <div className="relative">
            <select value={selectedBank} onChange={(e) => setSelectedBank(e.target.value)} className={selectClass}>
              <option value="all">Todos los bancos</option>
              {bankOptions.map((b) => (
                <option key={b} value={b}>
                  {b.split(" ").map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ")}
                </option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>
        )}

        {/* Category dropdown */}
        {categoryOptions.length > 0 && !onlyUncategorized && (
          <div className="relative">
            <select value={selectedCategory} onChange={(e) => setSelectedCategory(e.target.value)} className={selectClass}>
              <option value="all">Todas las categorías</option>
              {categoryOptions.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>
        )}

        {/* Uncategorized toggle */}
        <button
          onClick={() => { setOnlyUncategorized((v) => !v); setSelectedCategory("all"); }}
          className={`h-8 flex items-center gap-1.5 px-3 rounded-lg border text-[11px] font-medium transition-colors ${
            onlyUncategorized
              ? "bg-amber-50 border-amber-300 text-amber-700"
              : "bg-white border-slate-200 text-slate-600 hover:border-slate-300"
          }`}
        >
          <Tag size={11} strokeWidth={2} />
          Sin categoría
        </button>
      </FilterPanel>

      {/* Summary cards — Fintoc balances */}
      <SummaryBar
        accounts={accounts}
        sharedTxns={summaryShared}
        periodLabel={periodLabel}
        userId={userId}
        householdId={householdId}
      />

      {/* Tabs */}
      <Tabs defaultValue="all" onValueChange={() => setPage(1)}>
        <TabsList variant="line" className="border-b border-slate-200">
          {[
            { value: "all", label: "Todos", count: filteredAll.length },
            { value: "mine", label: "Personales", count: filteredMine.length },
            { value: "shared", label: "Compartidas", count: filteredShared.length },
          ].map(({ value, label, count }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="text-xs font-medium px-4 py-1.5"
            >
              {label}
              <span className="ml-1.5 text-[10px] opacity-70">({count})</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="all" className="mt-4 space-y-4">
          <TransactionTable
            transactions={filteredAll}
            loading={loadingMine || loadingShared}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={(s) => { setPageSize(s); setPage(1); }}
          />
        </TabsContent>

        <TabsContent value="mine" className="mt-4 space-y-4">
          <TransactionTable
            transactions={filteredMine}
            loading={loadingMine}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={(s) => { setPageSize(s); setPage(1); }}
          />
        </TabsContent>

        <TabsContent value="shared" className="mt-4 space-y-4">
          <TransactionTable
            transactions={filteredShared}
            loading={loadingShared}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={(s) => { setPageSize(s); setPage(1); }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
