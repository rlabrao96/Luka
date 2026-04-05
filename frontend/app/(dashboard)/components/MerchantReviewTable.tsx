"use client";
import { useState } from "react";
import { ReviewCard } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { Check, SkipForward, Pencil, ChevronDown, ChevronUp, X } from "lucide-react";

const EXPENSE_CATEGORIES = [
  "Alimentacion", "Supermercado", "Transporte", "Combustible",
  "Entretenimiento", "Salud", "Farmacia", "Hogar", "Ropa",
  "Tecnologia", "Educacion", "Viajes", "Servicios", "Otros",
];

const CATEGORY_ICONS: Record<string, string> = {
  Alimentacion: "🍽️", Supermercado: "🛒", Transporte: "🚗", Combustible: "⛽",
  Entretenimiento: "🎬", Salud: "🏥", Farmacia: "💊", Hogar: "🏠", Ropa: "👕",
  Tecnologia: "💻", Educacion: "📚", Viajes: "✈️", Servicios: "🔧", Otros: "📦",
};

function formatAmount(amount: number): string {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(Math.abs(amount));
}

function formatTxAmount(amount: number): string {
  const formatted = formatAmount(amount);
  if (amount < 0) return `(${formatted})`;
  if (amount > 0) return `+${formatted}`;
  return formatted;
}

interface MerchantRowProps {
  card: ReviewCard;
  onApprove: (displayName?: string, category?: string) => void;
  onSkip: () => void;
  isProcessed: boolean;
}

function MerchantRow({ card, onApprove, onSkip, isProcessed }: MerchantRowProps) {
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [displayName, setDisplayName] = useState(card.display_name);
  const [selectedCategory, setSelectedCategory] = useState(
    card.default_category ?? (card.llm_suggested_categories ?? [])[0] ?? ""
  );
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);

  const icon = CATEGORY_ICONS[selectedCategory] ?? "📦";
  const transactions = card.transactions ?? [];

  const handleApprove = () => {
    const nameChanged = displayName !== card.display_name ? displayName : undefined;
    onApprove(nameChanged, selectedCategory || undefined);
  };

  if (isProcessed) {
    return (
      <div className="bg-slate-50/50 rounded-xl px-5 py-4 flex items-center gap-4 opacity-50">
        <span className="text-xl w-8 text-center">{icon}</span>
        <span className="font-medium text-slate-400 flex-1">{card.display_name}</span>
        <span className="text-xs text-slate-400 bg-slate-100 px-2.5 py-1 rounded-md">{selectedCategory}</span>
        <span className="text-xs text-emerald-500 font-medium">Done</span>
      </div>
    );
  }

  return (
    <div className={cn(
      "bg-white rounded-xl border transition-all duration-200",
      editing ? "border-luka-primary shadow-lg shadow-blue-100" : "border-slate-100 hover:border-slate-200 hover:shadow-sm"
    )}>
      {/* Main row */}
      <div className="px-5 py-4 flex items-center gap-4">
        {/* Icon + Name */}
        <span className="text-2xl w-9 text-center shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          {editing ? (
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border-2 border-luka-primary rounded-lg px-3 py-1.5 text-base font-semibold text-luka-dark bg-blue-50/50 focus:outline-none"
              autoFocus
            />
          ) : (
            <h3 className="font-semibold text-base text-luka-dark truncate">{card.display_name}</h3>
          )}
        </div>

        {/* Category */}
        <div className="relative shrink-0">
          <button
            onClick={() => { setShowCategoryPicker(!showCategoryPicker); setEditing(true); }}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              selectedCategory
                ? "bg-blue-50 text-luka-primary hover:bg-blue-100"
                : "bg-amber-50 text-amber-600 hover:bg-amber-100"
            )}
          >
            {selectedCategory || "Sin categoría"}
            <ChevronDown size={14} />
          </button>
          {showCategoryPicker && (
            <div className="absolute right-0 top-full mt-1 z-50 bg-white rounded-xl shadow-xl border border-slate-200 p-2 w-56 max-h-64 overflow-y-auto">
              {EXPENSE_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => { setSelectedCategory(cat); setShowCategoryPicker(false); }}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors",
                    selectedCategory === cat
                      ? "bg-luka-primary text-white"
                      : "hover:bg-slate-50 text-slate-700"
                  )}
                >
                  <span>{CATEGORY_ICONS[cat] ?? "📦"}</span>
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="text-right shrink-0 w-24">
          <p className="text-sm font-semibold text-luka-dark tabular-nums">{formatAmount(card.total_amount)}</p>
          <p className="text-[11px] text-slate-400">{card.transaction_count} txns</p>
        </div>

        {/* Expand */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 transition-colors shrink-0"
        >
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {/* Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          {editing ? (
            <>
              <button
                onClick={() => { setEditing(false); setShowCategoryPicker(false); setDisplayName(card.display_name); }}
                className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:bg-slate-50 transition-colors"
                title="Cancel"
              >
                <X size={14} />
              </button>
              <button
                onClick={() => { handleApprove(); setEditing(false); }}
                className="h-8 px-3 rounded-lg bg-luka-primary text-white text-xs font-semibold hover:bg-blue-700 transition-colors flex items-center gap-1"
              >
                <Check size={14} />
                Save
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:text-luka-primary hover:border-luka-primary transition-colors"
                title="Edit"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={onSkip}
                className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
                title="Skip"
              >
                <SkipForward size={14} />
              </button>
              <button
                onClick={() => handleApprove()}
                className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center text-white hover:bg-emerald-600 transition-colors shadow-sm"
                title="Approve"
              >
                <Check size={16} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Expanded transactions */}
      {expanded && transactions.length > 0 && (
        <div className="px-5 pb-4 pt-0">
          <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] uppercase text-slate-400 tracking-wider">
                  <th className="text-left px-4 py-2 font-medium">Merchant name</th>
                  <th className="text-left px-4 py-2 font-medium">Date</th>
                  <th className="text-right px-4 py-2 font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-4 py-2.5 text-slate-600">{tx.raw_name}</td>
                    <td className="px-4 py-2.5 text-slate-400">{tx.date}</td>
                    <td className="px-4 py-2.5 text-right font-medium text-slate-700 tabular-nums">
                      {formatTxAmount(tx.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200">
                  <td colSpan={2} className="px-4 py-2.5 text-right text-xs font-semibold text-slate-500 uppercase">Total</td>
                  <td className="px-4 py-2.5 text-right font-bold text-slate-800 tabular-nums">{formatAmount(card.total_amount)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

interface Props {
  cards: ReviewCard[];
  onApprove: (canonicalId: string, displayName?: string, category?: string) => void;
  onSkip: (canonicalId: string) => void;
  onSkipAll: () => void;
}

export function MerchantReviewTable({ cards, onApprove, onSkip, onSkipAll }: Props) {
  const [processedIds, setProcessedIds] = useState<Set<string>>(new Set());

  const remaining = cards.length - processedIds.size;
  const progress = cards.length > 0 ? (processedIds.size / cards.length) * 100 : 0;

  const handleApprove = (card: ReviewCard, displayName?: string, category?: string) => {
    onApprove(card.canonical_merchant_id, displayName, category);
    setProcessedIds((prev) => new Set(prev).add(card.canonical_merchant_id));
  };

  const handleSkip = (card: ReviewCard) => {
    onSkip(card.canonical_merchant_id);
    setProcessedIds((prev) => new Set(prev).add(card.canonical_merchant_id));
  };

  // Sort: unprocessed first, processed at bottom
  const sorted = [...cards].sort((a, b) => {
    const aProcessed = processedIds.has(a.canonical_merchant_id) ? 1 : 0;
    const bProcessed = processedIds.has(b.canonical_merchant_id) ? 1 : 0;
    return aProcessed - bProcessed;
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-luka-dark">Review Merchants</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {remaining > 0 ? `${remaining} of ${cards.length} remaining` : "All done!"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {remaining > 0 && (
            <>
              <button
                onClick={() => {
                  cards.forEach((c) => {
                    if (!processedIds.has(c.canonical_merchant_id)) {
                      handleApprove(c);
                    }
                  });
                }}
                className="px-4 py-2 bg-emerald-500 text-white text-sm font-semibold rounded-lg hover:bg-emerald-600 transition-colors flex items-center gap-1.5"
              >
                <Check size={16} />
                Approve All
              </button>
              <button
                onClick={onSkipAll}
                className="px-4 py-2 border border-slate-200 text-sm text-slate-500 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Skip All
              </button>
            </>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="bg-slate-100 rounded-full h-1.5 overflow-hidden mb-6">
        <div
          className="bg-luka-primary h-full rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Merchant rows */}
      <div className="flex flex-col gap-2">
        {sorted.map((card) => (
          <MerchantRow
            key={card.canonical_merchant_id}
            card={card}
            onApprove={(dn, cat) => handleApprove(card, dn, cat)}
            onSkip={() => handleSkip(card)}
            isProcessed={processedIds.has(card.canonical_merchant_id)}
          />
        ))}
      </div>
    </div>
  );
}
