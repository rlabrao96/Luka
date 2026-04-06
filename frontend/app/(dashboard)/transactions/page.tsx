"use client";
import { useState, useMemo, useEffect } from "react";
import { ChevronDown, Tag, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { FilterPanel } from "../components/FilterPanel";
import { PendingBlock } from "../components/PendingBlock";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecentTransactions } from "../components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { ProcessingBanner } from "../components/ProcessingBanner";
import { useQuery } from "@tanstack/react-query";
import { useLukaStore } from "@/app/lib/store";
import { api, type Transaction, type BankAccountRow } from "@/app/lib/api";

function formatAmount(n: number, currency: string) {
  // Balances are stored in cents; CLP has no decimals
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? n / 100 : n;
  if (currency === "USD")
    return `US$${Math.abs(displayVal).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `$${Math.round(Math.abs(displayVal)).toLocaleString("es-CL")}`;
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
const CC_KIND = "credit_card";
const LOC_KIND = "line_of_credit";

interface SummaryBarProps {
  accounts: BankAccountRow[];
  transactions: Transaction[];
  selectedCurrency: string;
  selectedBank: string;
  onCurrencyChange: (c: string) => void;
}

function SummaryBar({ accounts, transactions, selectedCurrency, selectedBank, onCurrencyChange }: SummaryBarProps) {
  const currencies = useMemo(() => {
    const set = new Set<string>();
    accounts.forEach((a) => { if (a.currency) set.add(a.currency); });
    transactions.forEach((t) => { if (t.currency) set.add(t.currency); });
    return Array.from(set).sort();
  }, [accounts, transactions]);

  const hasUSD = currencies.includes("USD");

  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === selectedCurrency
      && (selectedBank === "all" || a.bank_name === selectedBank)
  );

  const checkingBalance = filtered
    .filter((a) => a.account_kind && CHECKING_KINDS.has(a.account_kind))
    .reduce((s, a) => s + (a.balance_current ?? 0), 0);

  const ccUsed = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + (a.balance_current ?? 0), 0); // Already negative

  const ccLimit = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + (a.balance_limit ?? 0), 0);

  const locBalance = filtered
    .filter((a) => a.account_kind === LOC_KIND)
    .reduce((s, a) => s + (a.balance_current ?? 0), 0);

  const hasLOC = filtered.some((a) => a.account_kind === LOC_KIND);
  const hasCC = filtered.some((a) => a.account_kind === CC_KIND);

  const netPosition = checkingBalance + locBalance + ccUsed;

  const hasAnyBalance = filtered.some((a) => a.balance_current !== null);

  const gridClass = { 1: "lg:grid-cols-1", 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4" } as Record<number, string>;

  const cards: Array<{
    label: string;
    value: string;
    sublabel: string;
    bg: string;
    textColor: string;
    show: boolean;
  }> = [
    {
      label: "Cuenta Corriente",
      value: hasAnyBalance ? formatAmount(checkingBalance, selectedCurrency) : "—",
      sublabel: "",
      bg: "bg-blue-50 border-blue-100",
      textColor: "text-luka-dark",
      show: true,
    },
    {
      label: "Tarjeta de Crédito",
      value: hasAnyBalance ? formatAmount(ccUsed, selectedCurrency) : "—",
      sublabel: hasAnyBalance && ccLimit > 0
        ? `gastado de ${formatAmount(ccLimit, selectedCurrency)}`
        : "",
      bg: "bg-red-50 border-red-100",
      textColor: ccUsed < 0 ? "text-red-600" : "text-luka-dark",
      show: hasCC,
    },
    {
      label: "Línea de Crédito",
      value: hasAnyBalance ? formatAmount(locBalance, selectedCurrency) : "—",
      sublabel: "disponible",
      bg: "bg-emerald-50 border-emerald-100",
      textColor: "text-luka-dark",
      show: hasLOC,
    },
    {
      label: "Posición Neta",
      value: hasAnyBalance ? formatAmount(netPosition, selectedCurrency) : "—",
      sublabel: "líquido - deuda TC",
      bg: netPosition >= 0
        ? "bg-emerald-50 border-emerald-200"
        : "bg-red-50 border-red-200",
      textColor: netPosition >= 0 ? "text-emerald-700" : "text-red-600",
      show: hasCC,
    },
  ];

  const visibleCards = cards.filter((c) => c.show);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Saldos disponibles
        </span>
        <div className="flex gap-1">
          {["CLP", ...(hasUSD ? ["USD"] : [])].map((c) => (
            <button
              key={c}
              onClick={() => onCurrencyChange(c)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                selectedCurrency === c
                  ? "bg-luka-primary text-white"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
      <div className={`grid grid-cols-1 ${gridClass[visibleCards.length] ?? "lg:grid-cols-4"} gap-3`}>
        {visibleCards.map(({ label, value, sublabel, bg, textColor }) => (
          <div
            key={label}
            className={`rounded-xl border p-4 ${bg}`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 leading-tight">
              {label}
            </p>
            <p className={`text-lg font-bold tabular-nums truncate ${textColor}`}>
              {value}
            </p>
            {sublabel && (
              <p className="text-[10px] text-slate-400 mt-0.5">{sublabel}</p>
            )}
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

      <div className="px-5 pt-1 pb-5">
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

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const [selectedCurrency, setSelectedCurrency] = useState<string>("CLP");

  useEffect(() => {
    if (me?.preferred_currency) setSelectedCurrency(me.preferred_currency);
  }, [me?.preferred_currency]);

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
    // Currency filter
    result = result.filter((t) => (t.currency ?? "CLP") === selectedCurrency);
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

  useEffect(() => { setPage(1); }, [selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search, selectedCurrency]);

  const filteredMine = useMemo(() => applyFilters(personalTxns), [personalTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search, selectedCurrency]);
  const filteredShared = useMemo(() => applyFilters(sharedTxns), [sharedTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search, selectedCurrency]);
  const filteredAll = useMemo(() => {
    const combined = [...myTxns, ...sharedTxns];
    // dedupe by id
    const seen = new Set<string>();
    const unique = combined.filter((t) => { if (seen.has(t.id)) return false; seen.add(t.id); return true; });
    return applyFilters(unique).sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  }, [myTxns, sharedTxns, selectedMonth, selectedBank, selectedCategory, onlyUncategorized, search, selectedCurrency]);

  const selectClass =
    "h-8 rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-luka-primary appearance-none pr-7 cursor-pointer";

  return (
    <div className="space-y-6">
      <ProcessingBanner />
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

      {/* Summary cards — account balances */}
      <SummaryBar
        accounts={accounts}
        transactions={[...myTxns, ...sharedTxns]}
        selectedCurrency={selectedCurrency}
        selectedBank={selectedBank}
        onCurrencyChange={setSelectedCurrency}
      />

      {/* Pending transactions */}
      <PendingBlock />

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
