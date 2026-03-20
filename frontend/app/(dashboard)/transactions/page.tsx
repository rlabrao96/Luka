"use client";
import { useState, useMemo } from "react";
import { Search, SlidersHorizontal, TrendingDown, Hash, ChevronDown } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecentTransactions } from "../components/RecentTransactions";
import { useMyTransactions, useSharedTransactions } from "@/app/lib/hooks/useTransactions";
import { Transaction } from "@/app/lib/api";

function formatCLP(n: number) {
  return `$${Math.round(n).toLocaleString("es-CL")}`;
}

function getMonthKey(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function getMonthLabel(key: string) {
  const [year, month] = key.split("-");
  const d = new Date(Number(year), Number(month) - 1, 1);
  return d.toLocaleDateString("es-CL", { month: "long", year: "numeric" });
}

interface SummaryBarProps {
  transactions: Transaction[];
}

function SummaryBar({ transactions }: SummaryBarProps) {
  const total = transactions.reduce((s, t) => s + t.amount, 0);
  const count = transactions.length;
  const avg = count > 0 ? total / count : 0;

  return (
    <div className="grid grid-cols-3 gap-3">
      {[
        {
          label: "Total egresos",
          value: formatCLP(total),
          icon: TrendingDown,
          iconClass: "text-red-400",
          iconBg: "bg-red-50",
        },
        {
          label: "Transacciones",
          value: String(count),
          icon: Hash,
          iconClass: "text-luka-primary",
          iconBg: "bg-blue-50",
        },
        {
          label: "Promedio",
          value: formatCLP(avg),
          icon: SlidersHorizontal,
          iconClass: "text-slate-400",
          iconBg: "bg-slate-50",
        },
      ].map(({ label, value, icon: Icon, iconClass, iconBg }) => (
        <div
          key={label}
          className="bg-white rounded-xl border border-slate-100 p-4 flex items-center gap-3"
        >
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${iconBg}`}>
            <Icon size={15} className={iconClass} strokeWidth={2} />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
              {label}
            </p>
            <p className="text-base font-bold text-luka-dark tabular-nums truncate">{value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [selectedMonth, setSelectedMonth] = useState<string>("all");
  const [selectedBank, setSelectedBank] = useState<string>("all");

  const { data: myTxns = [], isLoading: loadingMine } = useMyTransactions(200);
  const { data: sharedTxns = [], isLoading: loadingShared } = useSharedTransactions(200);

  // Build month options from all transactions
  const monthOptions = useMemo(() => {
    const keys = new Set<string>();
    [...myTxns, ...sharedTxns].forEach((t) => keys.add(getMonthKey(t.transaction_date)));
    return Array.from(keys).sort().reverse();
  }, [myTxns, sharedTxns]);

  // Build bank options
  const bankOptions = useMemo(() => {
    const banks = new Set<string>();
    [...myTxns, ...sharedTxns].forEach((t) => {
      if (t.bank_name) banks.add(t.bank_name);
    });
    return Array.from(banks).sort();
  }, [myTxns, sharedTxns]);

  const applyFilters = (txns: Transaction[]) => {
    let result = txns;
    if (selectedMonth !== "all") {
      result = result.filter((t) => getMonthKey(t.transaction_date) === selectedMonth);
    }
    if (selectedBank !== "all") {
      result = result.filter((t) => t.bank_name === selectedBank);
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

  const filteredMine = useMemo(() => applyFilters(myTxns), [myTxns, selectedMonth, selectedBank, search]);
  const filteredShared = useMemo(() => applyFilters(sharedTxns), [sharedTxns, selectedMonth, selectedBank, search]);

  const selectClass =
    "h-8 rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-luka-primary appearance-none pr-7 cursor-pointer";

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-luka-dark tracking-tight">Transacciones</h2>
        <p className="text-xs text-slate-400 mt-0.5 uppercase tracking-widest font-medium">
          Historial de movimientos
        </p>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar comercio, banco o categoría..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-8 pr-3 rounded-lg border border-slate-200 bg-white text-[11px] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-luka-primary"
          />
        </div>

        {/* Month filter */}
        <div className="relative">
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className={selectClass}
          >
            <option value="all">Todos los meses</option>
            {monthOptions.map((m) => (
              <option key={m} value={m}>
                {getMonthLabel(m)}
              </option>
            ))}
          </select>
          <ChevronDown
            size={12}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
          />
        </div>

        {/* Bank filter */}
        {bankOptions.length > 0 && (
          <div className="relative">
            <select
              value={selectedBank}
              onChange={(e) => setSelectedBank(e.target.value)}
              className={selectClass}
            >
              <option value="all">Todos los bancos</option>
              {bankOptions.map((b) => (
                <option key={b} value={b}>
                  {b
                    .split(" ")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                    .join(" ")}
                </option>
              ))}
            </select>
            <ChevronDown
              size={12}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
            />
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="mine">
        <TabsList className="bg-white border border-slate-100 rounded-xl p-1 h-auto">
          <TabsTrigger
            value="mine"
            className="rounded-lg text-xs font-medium px-4 py-1.5 data-[state=active]:bg-luka-primary data-[state=active]:text-white data-[state=active]:shadow-sm"
          >
            Personales
            <span className="ml-1.5 text-[10px] opacity-70">({filteredMine.length})</span>
          </TabsTrigger>
          <TabsTrigger
            value="shared"
            className="rounded-lg text-xs font-medium px-4 py-1.5 data-[state=active]:bg-luka-primary data-[state=active]:text-white data-[state=active]:shadow-sm"
          >
            Compartidas
            <span className="ml-1.5 text-[10px] opacity-70">({filteredShared.length})</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="mine" className="mt-4 space-y-4">
          <SummaryBar transactions={filteredMine} />
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Movimientos
              </p>
              <p className="text-[10px] text-slate-400">
                {filteredMine.length} resultado{filteredMine.length !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="px-5 py-1">
              {loadingMine ? (
                <div className="py-12 flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-luka-primary border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <RecentTransactions
                  transactions={filteredMine}
                  queryKeys={[["transactions", "mine", 200]]}
                />
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="shared" className="mt-4 space-y-4">
          <SummaryBar transactions={filteredShared} />
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
            <div className="px-5 py-3.5 border-b border-slate-50 flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                Movimientos
              </p>
              <p className="text-[10px] text-slate-400">
                {filteredShared.length} resultado{filteredShared.length !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="px-5 py-1">
              {loadingShared ? (
                <div className="py-12 flex items-center justify-center">
                  <div className="w-5 h-5 border-2 border-luka-primary border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <RecentTransactions
                  transactions={filteredShared}
                  queryKeys={[["transactions", "shared", null, 200]]}
                />
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
