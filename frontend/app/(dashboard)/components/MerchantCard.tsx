"use client";
import { useState, useEffect } from "react";
import { ReviewCard, ReviewTransactionInfo } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { getCategoryIconOrInitial } from "@/app/lib/category-icons";


function formatAmount(amount: number, currency = "CLP"): string {
  return new Intl.NumberFormat("es-CL", { style: "currency", currency, maximumFractionDigits: 0 }).format(Math.abs(amount));
}

function formatTxAmount(amount: number): string {
  const formatted = formatAmount(amount);
  if (amount < 0) return `(${formatted})`;
  if (amount > 0) return `+${formatted}`;
  return formatted;
}

interface Props {
  card: ReviewCard;
  categories: string[];
  onApprove: (displayName?: string, category?: string) => void;
  onSkip: () => void;
  editRequested?: boolean;
}

export function MerchantCard({ card, categories, onApprove, onSkip, editRequested }: Props) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(card.display_name);
  const [selectedCategory, setSelectedCategory] = useState(
    card.default_category ?? (card.llm_suggested_categories ?? [])[0] ?? ""
  );
  const [showAllCategories, setShowAllCategories] = useState(false);

  useEffect(() => {
    if (editRequested) setEditing(true);
  }, [editRequested]);

  const llmSuggestions = card.llm_suggested_categories ?? [];
  const suggestions = llmSuggestions.length > 0
    ? llmSuggestions
    : [card.default_category].filter(Boolean) as string[];

  const handleSaveApprove = () => {
    const nameChanged = displayName !== card.display_name ? displayName : undefined;
    onApprove(nameChanged, selectedCategory || undefined);
  };

  if (editing) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 w-full border-2 border-luka-primary">
        <span className="inline-block bg-blue-50 text-luka-primary text-[10px] font-semibold px-2.5 py-1 rounded-md mb-4">
          EDITANDO
        </span>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Nombre
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 w-full border-2 border-luka-primary rounded-xl px-4 py-2.5 text-lg font-bold text-luka-dark bg-slate-50 focus:outline-none"
            autoFocus
          />
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Categoría
          </label>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {suggestions.map((cat) => (
              <button
                key={cat}
                onClick={() => { setSelectedCategory(cat); setShowAllCategories(false); }}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                  selectedCategory === cat
                    ? "bg-luka-primary text-white"
                    : "bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
                )}
              >
                {cat}
              </button>
            ))}
            {!showAllCategories && (
              <button
                onClick={() => setShowAllCategories(true)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
              >
                Otra...
              </button>
            )}
          </div>
          {showAllCategories && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-slate-100">
              {categories.filter((c) => !suggestions.includes(c)).map((cat) => (
                <button
                  key={cat}
                  onClick={() => { setSelectedCategory(cat); setShowAllCategories(false); }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                    selectedCategory === cat
                      ? "bg-luka-primary text-white"
                      : "bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-50 rounded-xl p-3 mb-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">
            Movimientos ({card.transaction_count})
          </p>
          <div className="flex flex-col gap-1 max-h-[180px] overflow-y-auto">
            {(card.transactions ?? []).map((tx, i) => (
              <div key={i} className="flex items-center justify-between bg-white border border-slate-200 px-2 py-1 rounded-md text-[10px]">
                <span className="text-slate-500 truncate">{tx.raw_name}</span>
                <span className="flex gap-2 text-slate-400 shrink-0 ml-2">
                  <span>{tx.date}</span>
                  <span className="font-medium text-slate-600">{formatTxAmount(tx.amount)}</span>
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setEditing(false)}
            className="flex-1 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-500 hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            onClick={handleSaveApprove}
            className="flex-[1.5] py-2.5 bg-luka-primary text-white rounded-xl text-sm font-bold hover:bg-blue-700"
          >
            Guardar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 w-full">
      <div className="text-center mb-5">
        {(() => {
          const { icon, isEmoji } = getCategoryIconOrInitial(selectedCategory || card.display_name);
          return (
            <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-3">
              <span className={isEmoji ? "text-2xl" : "text-lg font-bold text-luka-primary"}>{icon}</span>
            </div>
          );
        })()}
        <h2 className="text-xl font-bold text-luka-dark">{card.display_name}</h2>
        {selectedCategory && (
          <span className="inline-block mt-1.5 bg-blue-50 text-luka-primary text-xs font-medium px-3 py-1 rounded-full">
            {selectedCategory}
          </span>
        )}
      </div>

      <div className="bg-slate-50 rounded-xl p-3">
        <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1.5">
          Movimientos ({card.transaction_count})
        </p>
        <div className="flex flex-col gap-1 max-h-[180px] overflow-y-auto">
          {(card.transactions ?? []).map((tx, i) => (
            <div key={i} className="flex items-center justify-between bg-white border border-slate-200 px-2 py-1 rounded-md text-[10px]">
              <span className="text-slate-500 truncate">{tx.raw_name}</span>
              <span className="flex gap-2 text-slate-400 shrink-0 ml-2">
                <span>{tx.date}</span>
                <span className="font-medium text-slate-600">{formatTxAmount(tx.amount)}</span>
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-end mt-2 pt-2 border-t border-slate-200">
          <span className="text-xs font-semibold text-slate-600">Total: {formatTxAmount(card.total_amount)}</span>
        </div>
      </div>
    </div>
  );
}
