"use client";
import { useState, useEffect, useRef } from "react";
import { ReviewCard } from "@/app/lib/api";
import { cn } from "@/lib/utils";
import { getCategoryIconOrInitial } from "@/app/lib/category-icons";
import { formatAmount } from "@/app/lib/currency";
import { CategoryPicker } from "./CategoryPicker";

// USD and other decimal currencies stored as cents in DB — divide by 100
function formatTxAmount(amount: number, currency: string): string {
  const isDecimal = currency !== "CLP" && currency !== "COP" && currency !== "PYG" && currency !== "CRC";
  const val = isDecimal ? Math.abs(amount) / 100 : Math.abs(amount);
  const formatted = formatAmount(val, currency);
  if (amount < 0) return `(${formatted})`;
  if (amount > 0) return `+${formatted}`;
  return formatted;
}

type SplitType = "personal" | "shared";

interface Props {
  card: ReviewCard;
  onApprove: (displayName?: string, category?: string, splitType?: SplitType) => void;
  onSplitChange?: (splitType: SplitType) => void;
  editRequested?: boolean;
}

export function MerchantCard({ card, onApprove, onSplitChange, editRequested }: Props) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(card.display_name);
  const [selectedCategory, setSelectedCategory] = useState(
    card.default_category ?? (card.llm_suggested_categories ?? [])[0] ?? ""
  );
  const [splitType, setSplitTypeState] = useState<SplitType>(
    card.is_joint_account ? "shared" : "personal"
  );
  const setSplitType = (next: SplitType | ((prev: SplitType) => SplitType)) => {
    setSplitTypeState((prev) => {
      const value = typeof next === "function" ? (next as (p: SplitType) => SplitType)(prev) : next;
      onSplitChange?.(value);
      return value;
    });
  };
  const [pickerOpen, setPickerOpen] = useState(false);
  const categoryAnchorRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (editRequested) setEditing(true);
  }, [editRequested]);

  const dominantSign: "positive" | "negative" =
    card.total_amount >= 0 ? "positive" : "negative";
  const filteredSuggestions = (card.llm_suggested_categories ?? []).filter(
    (c) => c.toLowerCase() !== "otros"
  );

  const handleSaveApprove = () => {
    const nameChanged = displayName !== card.display_name ? displayName : undefined;
    onApprove(nameChanged, selectedCategory || undefined, splitType);
  };

  const toggleSplit = () =>
    setSplitType((prev) => (prev === "personal" ? "shared" : "personal"));

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
            Tipo
          </label>
          <div className="flex gap-2 mt-1.5">
            <button
              type="button"
              onClick={() => setSplitType("personal")}
              className={cn(
                "px-3.5 py-1 rounded-full text-sm font-medium transition-colors",
                splitType === "personal"
                  ? "bg-blue-50 text-blue-600"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              )}
            >
              Personal
            </button>
            <button
              type="button"
              onClick={() => setSplitType("shared")}
              className={cn(
                "px-3.5 py-1 rounded-full text-sm font-medium transition-colors",
                splitType === "shared"
                  ? "bg-emerald-50 text-emerald-600"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200"
              )}
            >
              Compartido
            </button>
          </div>
        </div>

        <div className="mb-4">
          <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Categoría
          </label>
          <div className="mt-1.5">
            <CategoryPicker
              inline
              open
              onClose={() => {}}
              currentCategory={selectedCategory || null}
              suggestions={filteredSuggestions}
              dominantSign={dominantSign}
              onSelect={(cat) => setSelectedCategory(cat ?? "")}
            />
          </div>
        </div>

        <div className="bg-slate-50 rounded-xl p-3 mb-4">
          <p className="text-[10px] font-semibold text-slate-400 uppercase mb-1">
            Movimientos ({card.transaction_count})
          </p>
          <div className="flex flex-col gap-1 max-h-[180px] overflow-y-auto">
            {(card.transactions ?? []).map((tx, i) => (
              <div key={i} className="flex items-center bg-white border border-slate-200 px-2 py-1 rounded-md text-[10px]">
                <span className="text-slate-500 truncate flex-1 min-w-0">{tx.raw_name}</span>
                <span className="flex gap-2 text-slate-400 shrink-0 ml-2">
                  <span className="hidden sm:inline">{tx.date}</span>
                  <span className="font-medium text-slate-600 whitespace-nowrap">{formatTxAmount(tx.amount, tx.currency ?? "CLP")}</span>
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
    <div className="bg-white rounded-2xl shadow-lg p-6 w-full h-full flex flex-col">
      <div className="text-center mb-5">
        {(() => {
          const { icon, isEmoji } = getCategoryIconOrInitial(selectedCategory || card.display_name);
          return (
            <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-3">
              <span className={isEmoji ? "text-3xl" : "text-xl font-bold text-luka-primary"}>{icon}</span>
            </div>
          );
        })()}
        <h2 className="text-2xl font-bold text-luka-dark">{card.display_name}</h2>
        <div className="flex flex-col items-center gap-1.5 mt-2">
          <button
            ref={categoryAnchorRef}
            type="button"
            onClick={() => setPickerOpen(true)}
            className="bg-slate-100 text-slate-600 text-sm font-medium px-3.5 py-1 rounded-full hover:bg-slate-200 transition-colors"
          >
            {selectedCategory || "Sin categoría"}
          </button>
          <button
            type="button"
            onClick={toggleSplit}
            className={cn(
              "text-sm font-medium px-3.5 py-1 rounded-full transition-colors",
              splitType === "shared"
                ? "bg-emerald-50 text-emerald-600 hover:bg-emerald-100"
                : "bg-blue-50 text-blue-600 hover:bg-blue-100"
            )}
          >
            {splitType === "shared" ? "Compartido" : "Personal"}
          </button>
        </div>
        <CategoryPicker
          open={pickerOpen}
          onClose={() => setPickerOpen(false)}
          currentCategory={selectedCategory || null}
          suggestions={filteredSuggestions}
          dominantSign={dominantSign}
          anchorRef={categoryAnchorRef}
          onSelect={(cat) => {
            setSelectedCategory(cat ?? "");
            setPickerOpen(false);
          }}
        />
      </div>

      <div className="bg-slate-50 rounded-xl p-4 flex-1 flex flex-col">
        <p className="text-xs font-semibold text-slate-400 uppercase mb-2">
          Movimientos ({card.transaction_count})
        </p>
        <div className="flex flex-col gap-1.5 max-h-[200px] overflow-y-auto flex-1">
          {(card.transactions ?? []).map((tx, i) => (
            <div key={i} className="flex items-center bg-white border border-slate-200 px-3 py-1.5 rounded-lg text-xs">
              <span className="text-slate-600 truncate flex-1 min-w-0">{tx.raw_name}</span>
              <span className="flex gap-3 text-slate-400 shrink-0 ml-3">
                <span>{tx.date}</span>
                <span className="font-medium text-slate-700 whitespace-nowrap">{formatTxAmount(tx.amount, tx.currency ?? "CLP")}</span>
              </span>
            </div>
          ))}
        </div>
        <div className="flex justify-end mt-3 pt-3 border-t border-slate-200">
          <span className="text-sm font-semibold text-slate-700">Total: {formatTxAmount(card.total_amount, card.currency ?? (card.transactions ?? [])[0]?.currency ?? "CLP")}</span>
        </div>
      </div>
    </div>
  );
}
