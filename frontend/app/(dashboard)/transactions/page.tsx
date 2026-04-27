"use client";
import { useState, useMemo, useEffect } from "react";
import { ChevronDown, Tag, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { FilterPanelTriggers, FilterPanelBody, useFilterPanel } from "../components/FilterPanel";
import { PendingBlock } from "../components/PendingBlock";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecentTransactions } from "../components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { ProcessingBanner } from "../components/ProcessingBanner";
import { useQuery } from "@tanstack/react-query";
import { useLukaStore } from "@/app/lib/store";
import { api, type Transaction, type BankAccountRow } from "@/app/lib/api";
import { usePrimaryCurrency } from "@/app/lib/hooks/useCurrencies";
import { formatStoredAmount, normalizeBalance } from "@/app/lib/currency";
import { CurrencyToggle } from "../components/CurrencyToggle";
import { KpiCard } from "../components/KpiCard";
import { PageHeader } from "../components/PageHeader";
import { MonthSelector, ALL_MONTHS } from "../components/MonthSelector";
import { currentMonthKey } from "@/app/lib/months";

function getMonthKey(iso: string) {
  // Parse date string directly to avoid timezone shift
  return iso.split("T")[0].slice(0, 7);
}

const CHECKING_KINDS = new Set(["checking_account", "savings_account", "sight_account"]);
const CC_KIND = "credit_card";
const LOC_KIND = "line_of_credit";

interface SummaryBarProps {
  accounts: BankAccountRow[];
  selectedCurrency: string;
  selectedBank: string;
}

function SummaryBar({ accounts, selectedCurrency, selectedBank }: SummaryBarProps) {
  const filtered = accounts.filter(
    (a) => a.is_active && a.currency === selectedCurrency
      && (selectedBank === "all" || a.bank_name === selectedBank)
  );

  const checkingBalance = filtered
    .filter((a) => a.account_kind && CHECKING_KINDS.has(a.account_kind))
    .reduce((s, a) => s + normalizeBalance(a.balance_current ?? 0, selectedCurrency, a.provider), 0);

  const ccUsed = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + normalizeBalance(a.balance_current ?? 0, selectedCurrency, a.provider), 0); // Already negative

  const ccLimit = filtered
    .filter((a) => a.account_kind === CC_KIND)
    .reduce((s, a) => s + normalizeBalance(a.balance_limit ?? 0, selectedCurrency, a.provider), 0);

  const locBalance = filtered
    .filter((a) => a.account_kind === LOC_KIND)
    .reduce((s, a) => s + normalizeBalance(a.balance_current ?? 0, selectedCurrency, a.provider), 0);

  const hasLOC = filtered.some((a) => a.account_kind === LOC_KIND);
  const hasCC = filtered.some((a) => a.account_kind === CC_KIND);

  const netPosition = checkingBalance + locBalance + ccUsed;

  const hasAnyBalance = filtered.some((a) => a.balance_current !== null);

  const gridClass = { 1: "lg:grid-cols-1", 2: "lg:grid-cols-2", 3: "lg:grid-cols-3", 4: "lg:grid-cols-4" } as Record<number, string>;

  const cards: Array<{
    label: string;
    value: string;
    sublabel: string;
    className: string;
    valueClassName?: string;
    show: boolean;
  }> = [
    {
      label: "Cuenta Corriente",
      value: hasAnyBalance ? formatStoredAmount(checkingBalance, selectedCurrency) : "—",
      sublabel: "",
      className: "bg-blue-50 border-blue-100",
      show: true,
    },
    {
      label: "Tarjeta de Crédito",
      value: hasAnyBalance ? formatStoredAmount(ccUsed, selectedCurrency) : "—",
      sublabel: hasAnyBalance && ccLimit > 0
        ? `gastado de ${formatStoredAmount(ccLimit, selectedCurrency)}`
        : "",
      className: "bg-red-50 border-red-100",
      valueClassName: ccUsed < 0 ? "text-red-600" : undefined,
      show: hasCC,
    },
    {
      label: "Línea de Crédito",
      value: hasAnyBalance ? formatStoredAmount(locBalance, selectedCurrency) : "—",
      sublabel: "disponible",
      className: "bg-emerald-50 border-emerald-100",
      show: hasLOC,
    },
    {
      label: "Posición Neta",
      value: hasAnyBalance ? formatStoredAmount(netPosition, selectedCurrency) : "—",
      sublabel: "líquido - deuda TC",
      className: netPosition >= 0
        ? "bg-emerald-50 border-emerald-200"
        : "bg-red-50 border-red-200",
      valueClassName: netPosition >= 0 ? "text-emerald-700" : "text-red-600",
      show: hasCC,
    },
  ];

  const visibleCards = cards.filter((c) => c.show);

  return (
    <div className="space-y-2">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
        Saldos disponibles
      </span>
      <div className={`grid grid-cols-1 ${gridClass[visibleCards.length] ?? "lg:grid-cols-4"} gap-3`}>
        {visibleCards.map(({ label, value, sublabel, className, valueClassName }) => (
          <KpiCard
            key={label}
            variant="compact"
            label={label}
            value={value}
            sublabel={sublabel || undefined}
            valueClassName={valueClassName}
            className={className}
          />
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
      <div className="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between gap-3 flex-wrap">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Movimientos
        </p>
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400">Ver</span>
            {([10, 30, 100] as const).map((s) => (
              <button
                key={s}
                onClick={() => onPageSize(s)}
                aria-label={`Mostrar ${s} por página`}
                aria-pressed={pageSize === s}
                className={`text-[11px] sm:text-[10px] font-medium min-w-[32px] h-8 sm:h-auto sm:min-w-0 px-2 sm:px-1.5 sm:py-0.5 rounded transition-colors ${
                  pageSize === s
                    ? "bg-luka-primary text-white"
                    : "text-slate-500 hover:text-luka-primary"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <p className="hidden sm:block text-[10px] text-slate-400">
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
              aria-label="Primera página"
              className="hidden lg:flex items-center justify-center w-7 h-7 rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronsLeft size={13} />
            </button>
            <button
              onClick={() => onPage(page - 1)}
              disabled={page === 1}
              aria-label="Página anterior"
              className="flex items-center gap-1 h-10 min-w-[44px] sm:h-7 sm:min-w-0 px-3 sm:px-2.5 rounded-lg border border-slate-200 bg-white text-[13px] sm:text-[11px] font-medium text-slate-600 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={14} /> <span className="hidden sm:inline">Anterior</span>
            </button>
          </div>
          <span className="text-[11px] font-medium text-slate-500 text-center shrink-0">
            <span className="text-luka-dark font-semibold">{page}</span>
            <span className="hidden sm:inline"> de </span>
            <span className="sm:hidden">/</span>
            {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPage(page + 1)}
              disabled={page === totalPages}
              aria-label="Página siguiente"
              className="flex items-center gap-1 h-10 min-w-[44px] sm:h-7 sm:min-w-0 px-3 sm:px-2.5 rounded-lg border border-slate-200 bg-white text-[13px] sm:text-[11px] font-medium text-slate-600 hover:border-luka-primary hover:text-luka-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <span className="hidden sm:inline">Siguiente</span> <ChevronRight size={14} />
            </button>
            <button
              onClick={() => onPage(totalPages)}
              disabled={page === totalPages}
              aria-label="Última página"
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
  const [selectedMonth, setSelectedMonth] = useState<string>(ALL_MONTHS);
  const nowKey = currentMonthKey();
  const [selectedBank, setSelectedBank] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [onlyUncategorized, setOnlyUncategorized] = useState(false);
  const [pageSize, setPageSize] = useState<10 | 30 | 100>(30);
  const [page, setPage] = useState(1);
  const householdId = useLukaStore((s) => s.householdId);
  const filterPanel = useFilterPanel();

  const primaryCurrency = usePrimaryCurrency();

  const [selectedCurrency, setSelectedCurrency] = useState<string>("");

  useEffect(() => {
    if (!selectedCurrency && primaryCurrency) {
      setSelectedCurrency(primaryCurrency);
    }
  }, [primaryCurrency, selectedCurrency]);

  const { data: myTxns = [], isLoading: loadingMine } = useMyTransactions();
  const { data: sharedTxns = [], isLoading: loadingShared } = useSharedTransactions();
  const { data: accounts = [] } = useQuery<BankAccountRow[]>({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 60 * 1000,
  });

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
    if (selectedCurrency) {
      result = result.filter((t) => (t.currency ?? "CLP") === selectedCurrency);
    }
    if (selectedMonth !== ALL_MONTHS) result = result.filter((t) => getMonthKey(t.transaction_date) === selectedMonth);
    if (selectedBank !== "all") result = result.filter((t) => t.bank_name === selectedBank);
    if (selectedType !== "all") result = result.filter((t) => t.transaction_type === selectedType);
    if (onlyUncategorized) {
      result = result.filter((t) => !t.category && t.transaction_type !== "transfer");
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

  useEffect(() => { setPage(1); }, [selectedMonth, selectedBank, selectedCategory, selectedType, onlyUncategorized, search, selectedCurrency]);

  const filteredMine = useMemo(() => applyFilters(personalTxns), [personalTxns, selectedMonth, selectedBank, selectedCategory, selectedType, onlyUncategorized, search, selectedCurrency]);
  const filteredShared = useMemo(() => applyFilters(sharedTxns), [sharedTxns, selectedMonth, selectedBank, selectedCategory, selectedType, onlyUncategorized, search, selectedCurrency]);
  const filteredAll = useMemo(() => {
    const combined = [...myTxns, ...sharedTxns];
    // dedupe by id
    const seen = new Set<string>();
    const unique = combined.filter((t) => { if (seen.has(t.id)) return false; seen.add(t.id); return true; });
    return applyFilters(unique).sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
  }, [myTxns, sharedTxns, selectedMonth, selectedBank, selectedCategory, selectedType, onlyUncategorized, search, selectedCurrency]);

  // Mobile: 44px touch target + 16px-adjacent text so iOS Safari doesn't
  // zoom-on-focus. Shrinks back to the desktop-compact size at sm+.
  const selectClass =
    "w-full h-11 sm:h-8 sm:w-auto rounded-lg border border-slate-200 bg-white px-3 text-[15px] sm:text-[11px] font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-luka-primary appearance-none pr-8 cursor-pointer";

  return (
    <div className="space-y-6">
      <ProcessingBanner />
      {(() => {
        const activeCount = [
          selectedBank !== "all" ? 1 : 0,
          selectedCategory !== "all" ? 1 : 0,
          selectedType !== "all" ? 1 : 0,
          onlyUncategorized ? 1 : 0,
        ].reduce((a, b) => a + b, 0);
        return (
          <PageHeader
            title="Transacciones"
            subtitle="Historial de movimientos"
            controls={
              <>
                {selectedCurrency && (
                  <CurrencyToggle value={selectedCurrency} onChange={setSelectedCurrency} />
                )}
                <MonthSelector
                  value={selectedMonth}
                  onChange={setSelectedMonth}
                  currentMonth={nowKey}
                  currency={selectedCurrency || undefined}
                  size="md"
                  allowAll
                />
              </>
            }
            actions={
              <FilterPanelTriggers
                searchOpen={filterPanel.searchOpen}
                filtersOpen={filterPanel.filtersOpen}
                onToggleSearch={filterPanel.toggleSearch}
                onToggleFilters={filterPanel.toggleFilters}
                activeCount={activeCount}
              />
            }
          />
        );
      })()}

      {/* Filter body — mobile collapsibles + desktop inline filters */}
      <FilterPanelBody
        searchOpen={filterPanel.searchOpen}
        filtersOpen={filterPanel.filtersOpen}
        onCloseSearch={filterPanel.closeSearch}
        onCloseFilters={filterPanel.closeFilters}
        activeCount={[
          selectedBank !== "all" ? 1 : 0,
          selectedCategory !== "all" ? 1 : 0,
          selectedType !== "all" ? 1 : 0,
          onlyUncategorized ? 1 : 0,
        ].reduce((a, b) => a + b, 0)}
        onClear={() => {
          setSelectedMonth(ALL_MONTHS);
          setSelectedBank("all");
          setSelectedCategory("all");
          setSelectedType("all");
          setOnlyUncategorized(false);
          setSearch("");
        }}
        searchValue={search}
        onSearchChange={setSearch}
      >
        {/* Type dropdown */}
        <div className="relative">
          <select value={selectedType} onChange={(e) => setSelectedType(e.target.value)} className={selectClass}>
            <option value="all">Tipos de movimiento</option>
            <option value="expense">Gasto</option>
            <option value="income">Ingreso</option>
            <option value="transfer">Transferencia entre cuentas</option>
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
      </FilterPanelBody>

      {/* Summary cards — account balances */}
      {selectedCurrency && (
        <SummaryBar
          accounts={accounts}
          selectedCurrency={selectedCurrency}
          selectedBank={selectedBank}
        />
      )}

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
