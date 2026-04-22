"use client";

import { useState, useMemo, useEffect } from "react";
import { RefreshCw, ArrowUp, ArrowDown, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { CurrencyToggle } from "../components/CurrencyToggle";
import {
  useSubscriptions,
  useRefreshSubscriptions,
  useSubscriptionOverride,
} from "@/app/lib/hooks/useSubscriptions";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader } from "../components/PageHeader";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import type { RecurringExpense } from "@/app/lib/api";
import { formatStoredAmount } from "@/app/lib/currency";
import { localeForCurrency } from "@/app/lib/locale";
import { usePrimaryCurrency } from "@/app/lib/hooks/useCurrencies";

/* ── Formatting ─────────────────────────────────────────── */

function formatAmount(n: number, currency: string) {
  return formatStoredAmount(n, currency);
}

function relativeTime(iso: string | null) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 1) return "hace menos de 1 hora";
  if (hours < 24) return `hace ${hours}h`;
  const days = Math.floor(hours / 24);
  return `hace ${days} día${days > 1 ? "s" : ""}`;
}

/* ── Main Page ──────────────────────────────────────────── */

export default function SubscriptionsPage() {
  const { data, isLoading } = useSubscriptions();
  const refreshMutation = useRefreshSubscriptions();
  const overrideMutation = useSubscriptionOverride();

  const primaryCurrency = usePrimaryCurrency();
  const [currency, setCurrency] = useState("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<RecurringExpense | null>(null);

  useEffect(() => {
    if (!currency && primaryCurrency) setCurrency(primaryCurrency);
  }, [primaryCurrency, currency]);

  const allItems = data?.items ?? [];
  const summaryByCurrency = data?.summary_by_currency ?? {};
  const computedAt = data?.computed_at ?? null;

  // Filter by currency
  const items = useMemo(
    () => allItems.filter((s) => s.currency === currency),
    [allItems, currency],
  );

  const activeItems = useMemo(
    () => items.filter((s) => s.status === "active"),
    [items],
  );

  const summary = summaryByCurrency[currency];
  const alerts = activeItems.filter((s) => s.trend !== "stable");

  // Timeline sorted by next_charge_day
  const timelineSorted = useMemo(
    () => [...activeItems].sort((a, b) => a.next_charge_day - b.next_charge_day),
    [activeItems],
  );

  const today = new Date().getDate();

  if (isLoading) {
    return <p className="text-gray-400">Cargando...</p>;
  }

  if (allItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <p className="text-lg font-semibold text-gray-700">
          No hemos detectado gastos recurrentes aún
        </p>
        <p className="text-sm text-gray-400 mt-2 max-w-xs">
          Necesitamos al menos 2 meses de transacciones para identificar patrones
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Suscripciones"
        subtitle="Gastos recurrentes detectados automáticamente"
        controls={
          currency ? <CurrencyToggle value={currency} onChange={setCurrency} /> : undefined
        }
        actions={
          <button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
            aria-label="Actualizar suscripciones"
            className="w-9 h-9 rounded-lg border border-slate-200 bg-white hover:border-luka-primary hover:-translate-y-px transition-all shadow-[var(--shadow-card)] flex items-center justify-center text-slate-500 disabled:opacity-50"
            title={`Última actualización: ${relativeTime(computedAt)}`}
          >
            <RefreshCw
              size={16}
              className={refreshMutation.isPending ? "animate-spin" : ""}
            />
          </button>
        }
      />

      {/* Currency-specific empty state */}
      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-sm text-gray-400">
            No tienes suscripciones en {currency}
          </p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 gap-3">
            <Card>
              <CardContent className="p-4">
                <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                  Total mensual recurrente
                </p>
                <p className="text-[22px] font-bold text-gray-900 mt-1 tabular-nums">
                  {formatAmount(summary?.total_recurring ?? 0, currency)}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {summary?.count ?? 0} suscripciones activas
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                  % de gastos totales
                </p>
                <p className="text-[22px] font-bold text-blue-600 mt-1 tabular-nums">
                  {Math.round(summary?.pct_of_total ?? 0)}%
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  de {formatAmount(summary?.monthly_total ?? 0, currency)} este mes
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Price Change Alerts */}
          {alerts.length > 0 && (
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                Cambios de precio
              </p>
              <div className="space-y-2">
                {alerts.map((sub) => {
                  const isUp = sub.trend === "increased";
                  const prev = sub.previous_amount ?? sub.average_amount;
                  return (
                    <div
                      key={`alert-${sub.merchant_name}`}
                      className={`flex items-center gap-3 bg-white rounded-lg border border-slate-200 p-3 ${
                        isUp ? "border-l-[3px] border-l-red-500" : "border-l-[3px] border-l-emerald-500"
                      }`}
                    >
                      <div
                        className={`flex items-center justify-center w-7 h-7 rounded-md shrink-0 ${
                          isUp ? "bg-red-50" : "bg-emerald-50"
                        }`}
                      >
                        {isUp ? (
                          <ArrowUp size={14} className="text-red-500" />
                        ) : (
                          <ArrowDown size={14} className="text-emerald-500" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-gray-900">
                          {sub.merchant_name}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatAmount(prev, currency)} → {formatAmount(sub.last_amount, currency)}
                        </p>
                      </div>
                      <span
                        className={`text-xs font-semibold whitespace-nowrap ${
                          isUp ? "text-red-500" : "text-emerald-500"
                        }`}
                      >
                        {isUp ? "+" : "-"}
                        {Math.abs(Math.round(sub.trend_pct ?? 0))}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Generic Month Timeline */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-4">
              Calendario de cobros
            </p>
            <div className="relative border-l-2 border-blue-100 ml-3 pl-6 space-y-4">
              {(() => {
                // Build timeline entries: charges + today marker as peers
                const entries: ({ type: "charge"; sub: typeof timelineSorted[0] } | { type: "today" })[] = [];
                let todayInserted = false;
                for (const sub of timelineSorted) {
                  if (!todayInserted && sub.next_charge_day > today) {
                    entries.push({ type: "today" });
                    todayInserted = true;
                  }
                  entries.push({ type: "charge", sub });
                }
                if (!todayInserted) entries.push({ type: "today" });

                return entries.map((entry, idx) => {
                  if (entry.type === "today") {
                    return (
                      <div key="today-marker" className="relative">
                        <div className="absolute -left-[36px] top-0 w-5 h-5 rounded-full bg-blue-600 border-2 border-white flex items-center justify-center z-10">
                          <span className="text-[8px] font-extrabold text-white">
                            {today}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <p className="text-[11px] font-bold text-blue-600 uppercase tracking-wide leading-5">
                            Hoy — Día {today}
                          </p>
                          <div className="flex-1 h-0.5 bg-gradient-to-r from-blue-600 to-transparent" />
                        </div>
                      </div>
                    );
                  }
                  const { sub } = entry;
                  const isBeforeToday = sub.next_charge_day <= today;
                  return (
                    <div key={sub.merchant_name} className="relative">
                      <div
                        className={`absolute -left-[31px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white ${
                          isBeforeToday ? "bg-blue-600" : "bg-blue-400"
                        }`}
                      />
                      <p
                        className={`text-[11px] font-bold uppercase ${
                          isBeforeToday ? "text-blue-600" : "text-blue-400"
                        }`}
                      >
                        Día {sub.next_charge_day}
                      </p>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-sm text-gray-700">
                          {sub.merchant_name}
                        </span>
                        <span className="text-sm font-bold text-gray-900 tabular-nums">
                          {formatAmount(sub.last_amount, currency)}
                        </span>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          </div>

          {/* Summary — table on desktop, stacked cards on mobile */}
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
              Detalle de suscripciones
            </p>
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              {/* Table header — desktop only */}
              <div className="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr_1fr_60px] gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200">
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Servicio</span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Monto</span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Último cobro</span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Categoría</span>
                <span className="text-[11px] font-semibold text-slate-400 uppercase">Clasificación</span>
                <span />
              </div>

              {/* Rows — sorted by next_charge_day */}
              {[...items]
                .filter((s) => s.status !== "dismissed")
                .sort((a, b) => a.next_charge_day - b.next_charge_day)
                .map((sub) => {
                  const isExpanded = expandedRow === sub.merchant_name;
                  const isInactive = sub.status === "inactive";
                  const lastChargeLabel = new Date(sub.last_charge_date + "T00:00:00").toLocaleDateString(
                    localeForCurrency(currency),
                    { day: "numeric", month: "short", year: "numeric" },
                  );

                  return (
                    <div
                      key={sub.merchant_name}
                      className={`border-b border-slate-100 last:border-b-0 ${
                        isInactive ? "opacity-55" : ""
                      }`}
                    >
                      {/* Mobile row — stacked layout */}
                      <div
                        className="sm:hidden px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors"
                        onClick={() => setExpandedRow(isExpanded ? null : sub.merchant_name)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              {isExpanded ? (
                                <ChevronUp size={14} className="text-slate-300 shrink-0" />
                              ) : (
                                <ChevronDown size={14} className="text-slate-300 shrink-0" />
                              )}
                              <p className="text-sm font-semibold text-gray-900 truncate">
                                {sub.merchant_name}
                              </p>
                              {isInactive && (
                                <span className="text-[9px] font-semibold text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded uppercase shrink-0">
                                  Inactiva
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400 mt-0.5 ml-[18px]">
                              {sub.months_seen} meses · {lastChargeLabel}
                            </p>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-sm font-bold text-gray-900 tabular-nums">
                              {formatAmount(sub.last_amount, currency)}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center justify-between gap-2 mt-2 ml-[18px] flex-wrap">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded truncate max-w-[140px]">
                              {sub.category ?? "—"}
                            </span>
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                                sub.split_type === "shared"
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-blue-50 text-blue-700"
                              }`}
                            >
                              {sub.split_type === "shared" ? "Compartido" : "Personal"}
                            </span>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingItem(sub);
                            }}
                            className="text-xs text-blue-600 font-medium hover:underline min-h-[32px] px-1"
                          >
                            Editar
                          </button>
                        </div>
                      </div>

                      {/* Desktop row — original 6-column grid */}
                      <div
                        className="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr_1fr_60px] gap-2 px-4 py-3 items-center cursor-pointer hover:bg-slate-50 transition-colors"
                        onClick={() => setExpandedRow(isExpanded ? null : sub.merchant_name)}
                      >
                        <div className="flex items-center gap-1.5 min-w-0">
                          {isExpanded ? (
                            <ChevronUp size={14} className="text-slate-300 shrink-0" />
                          ) : (
                            <ChevronDown size={14} className="text-slate-300 shrink-0" />
                          )}
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <p className="text-[13px] font-semibold text-gray-900 truncate">
                                {sub.merchant_name}
                              </p>
                              {isInactive && (
                                <span className="text-[9px] font-semibold text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded uppercase shrink-0">
                                  Inactiva
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-400">
                              {sub.months_seen} meses · {sub.frequency}
                            </p>
                          </div>
                        </div>
                        <span className="text-[13px] font-semibold text-gray-900 tabular-nums">
                          {formatAmount(sub.last_amount, currency)}
                        </span>
                        <span className="text-xs text-slate-500">{lastChargeLabel}</span>
                        <span className="text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded text-center truncate">
                          {sub.category ?? "—"}
                        </span>
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full text-center ${
                            sub.split_type === "shared"
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-blue-50 text-blue-700"
                          }`}
                        >
                          {sub.split_type === "shared" ? "Compartido" : "Personal"}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingItem(sub);
                          }}
                          className="text-[11px] text-blue-600 font-medium hover:underline"
                        >
                          Editar
                        </button>
                      </div>

                      {/* Expanded recent charges */}
                      {isExpanded && sub.recent_charges.length > 0 && (
                        <div className="px-4 pb-3 ml-2 border-l-2 border-blue-100">
                          {sub.recent_charges.map((charge, i) => (
                            <div
                              key={i}
                              className="flex justify-between py-1 pl-3"
                            >
                              <span className="text-[11px] text-slate-400">
                                {new Date(charge.date + "T00:00:00").toLocaleDateString(
                                  localeForCurrency(currency),
                                  { day: "numeric", month: "short", year: "numeric" },
                                )}
                              </span>
                              <span className="text-[11px] font-medium text-gray-700 tabular-nums">
                                {formatAmount(charge.amount, currency)}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        </>
      )}

      {/* Edit Modal */}
      {editingItem && (
        <EditModal
          item={editingItem}
          currency={currency}
          onClose={() => setEditingItem(null)}
          onSave={(body) => {
            setEditingItem(null);
            overrideMutation.mutate(body);
          }}
        />
      )}
    </div>
  );
}

/* ── Edit Modal ─────────────────────────────────────────── */

function EditModal({
  item,
  currency,
  onClose,
  onSave,
}: {
  item: RecurringExpense;
  currency: string;
  onClose: () => void;
  onSave: (body: {
    merchant_key: string;
    status?: string;
    category?: string;
    next_charge_day?: number | null;
    split_type?: "personal" | "shared";
  }) => void;
}) {
  const [status, setStatus] = useState(item.status);
  const [category, setCategory] = useState(item.category ?? "");
  const [chargeDay, setChargeDay] = useState<string>(
    item.next_charge_day ? String(item.next_charge_day) : "",
  );
  const initialSplitType: "personal" | "shared" =
    item.split_type === "shared" ? "shared" : "personal";
  const [splitType, setSplitType] = useState<"personal" | "shared">(initialSplitType);

  const { data: categories } = useQuery({
    queryKey: ["categories", "preferences"],
    queryFn: () => api.getCategoryPreferences(),
  });

  const categoryList: string[] = useMemo(() => {
    if (!categories) return [];
    return categories.categories.map((c) => c.category).sort();
  }, [categories]);

  const statusOptions = [
    { value: "active", label: "Activa" },
    { value: "inactive", label: "Inactiva" },
    { value: "dismissed", label: "No es suscripción" },
  ] as const;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="pr-8">Editar — {item.merchant_name}</DialogTitle>
        </DialogHeader>

        {/* Category */}
        <div>
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Categoría
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700 bg-white"
          >
            <option value="">— Sin cambio —</option>
            {categoryList.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div>
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Estado
          </label>
          <div className="flex gap-1.5">
            {statusOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setStatus(opt.value)}
                className={`flex-1 px-2 h-10 rounded-lg text-xs font-semibold transition-colors ${
                  status === opt.value
                    ? "bg-luka-primary text-white"
                    : "bg-slate-100 text-slate-500 border border-slate-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Classification */}
        <div>
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Clasificación
          </label>
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => setSplitType("personal")}
              className={`flex-1 px-2 h-10 rounded-lg text-xs font-semibold transition-colors ${
                splitType === "personal"
                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                  : "bg-slate-100 text-slate-500 border border-slate-200"
              }`}
            >
              Personal
            </button>
            <button
              type="button"
              onClick={() => setSplitType("shared")}
              className={`flex-1 px-2 h-10 rounded-lg text-xs font-semibold transition-colors ${
                splitType === "shared"
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-slate-100 text-slate-500 border border-slate-200"
              }`}
            >
              Compartido
            </button>
          </div>
        </div>

        {/* Next Charge Day — text-base avoids iOS zoom-on-focus */}
        <div>
          <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
            Día del mes (opcional)
          </label>
          <input
            type="number"
            min={1}
            max={31}
            inputMode="numeric"
            value={chargeDay}
            onChange={(e) => setChargeDay(e.target.value)}
            placeholder={String(item.next_charge_day)}
            className="w-full border border-slate-200 rounded-lg px-3 h-11 sm:h-10 text-base sm:text-[13px] text-gray-700"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 sm:flex-initial px-4 h-11 rounded-lg bg-slate-50 text-slate-500 border border-slate-200 text-sm font-medium hover:bg-slate-100 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() =>
              onSave({
                merchant_key: item.merchant_name,
                status,
                category: category || undefined,
                next_charge_day: chargeDay ? Number(chargeDay) : null,
                // Only send split_type if it actually changed — avoids
                // running the 3-month cascade on every Editar save.
                ...(splitType !== initialSplitType && { split_type: splitType }),
              })
            }
            className="flex-1 px-4 h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            Guardar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
