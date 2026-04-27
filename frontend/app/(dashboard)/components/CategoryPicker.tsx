"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";
import { getCategoryIconOrInitial } from "@/app/lib/category-icons";

export interface CategoryPickerProps {
  open: boolean;
  onClose: () => void;
  currentCategory: string | null;
  onSelect: (category: string | null) => void;
  // LLM picks; render a "Sugeridas" amber-framed card at top when non-empty.
  // The component itself filters out "Otros" before rendering.
  suggestions?: string[];
  // Drives section order: positive => Ingresos first; negative or undefined => Gastos first.
  // Both sections always rendered.
  dominantSign?: "positive" | "negative";
  // When true, render the body inline — no sheet/popover shell. Used by edit mode.
  inline?: boolean;
  // Optional anchor element for desktop popover positioning.
  anchorRef?: React.RefObject<HTMLElement | null>;
}

const collator = new Intl.Collator("es", { sensitivity: "base" });

function CategoryTile({
  category,
  selected,
  onClick,
}: {
  category: string;
  selected: boolean;
  onClick: () => void;
}) {
  const { icon, isEmoji } = getCategoryIconOrInitial(category);
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg p-2.5 flex flex-col items-center gap-1 transition-colors border",
        selected
          ? "bg-luka-primary border-luka-primary"
          : "bg-slate-50 border-slate-100 hover:bg-slate-100"
      )}
    >
      <span className="w-7 h-7 bg-white rounded-md flex items-center justify-center text-base">
        {isEmoji ? icon : <span className="text-xs font-semibold text-slate-700">{icon}</span>}
      </span>
      <span
        className={cn(
          "text-[10px] font-medium text-center leading-tight line-clamp-2 min-h-[24px]",
          selected ? "text-white" : "text-slate-600"
        )}
      >
        {category}
      </span>
    </button>
  );
}

function CategorySection({
  label,
  categories,
  currentCategory,
  onPick,
}: {
  label: string;
  categories: string[];
  currentCategory: string | null;
  onPick: (cat: string) => void;
}) {
  if (categories.length === 0) return null;
  return (
    <div className="mb-3">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
        {label}
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {categories.map((cat) => (
          <CategoryTile
            key={cat}
            category={cat}
            selected={currentCategory === cat}
            onClick={() => onPick(cat)}
          />
        ))}
      </div>
    </div>
  );
}

function PickerBody({
  currentCategory,
  onSelect,
  onClose,
  suggestions,
  dominantSign,
}: {
  currentCategory: string | null;
  onSelect: (category: string | null) => void;
  onClose: () => void;
  suggestions?: string[];
  dominantSign?: "positive" | "negative";
}) {
  const { expense, income } = useCategories();

  const sortedExpense = useMemo(
    () => [...expense].sort((a, b) => collator.compare(a, b)),
    [expense]
  );
  const sortedIncome = useMemo(
    () => [...income].sort((a, b) => collator.compare(a, b)),
    [income]
  );

  const filteredSuggestions = useMemo(
    () => (suggestions ?? []).filter((s) => s && s.toLowerCase() !== "otros"),
    [suggestions]
  );

  function handlePick(cat: string | null) {
    onSelect(cat);
    onClose();
  }

  const incomeFirst = dominantSign === "positive";

  return (
    <div>
      {currentCategory !== null && (
        <button
          type="button"
          onClick={() => handlePick(null)}
          className="w-full text-left px-3 py-2 mb-3 text-xs font-medium text-slate-500 hover:bg-slate-100 bg-slate-50 rounded-lg transition-colors"
        >
          Sin categoría
        </button>
      )}

      {filteredSuggestions.length > 0 && (
        <div className="bg-gradient-to-br from-amber-50 to-amber-100/50 border border-amber-200 rounded-xl p-3 mb-3">
          <div className="text-[10px] font-bold text-amber-800 uppercase tracking-wider mb-2 flex items-center gap-1">
            <span>✨</span>
            <span>Sugeridas</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {filteredSuggestions.map((cat) => {
              const selected = currentCategory === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => handlePick(cat)}
                  className={cn(
                    "text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors",
                    selected
                      ? "bg-amber-600 text-white border-amber-600"
                      : "bg-white border-amber-200 text-amber-800 hover:bg-amber-50"
                  )}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {incomeFirst ? (
        <>
          <CategorySection
            label="Ingresos"
            categories={sortedIncome}
            currentCategory={currentCategory}
            onPick={(c) => handlePick(c)}
          />
          <CategorySection
            label="Gastos"
            categories={sortedExpense}
            currentCategory={currentCategory}
            onPick={(c) => handlePick(c)}
          />
        </>
      ) : (
        <>
          <CategorySection
            label="Gastos"
            categories={sortedExpense}
            currentCategory={currentCategory}
            onPick={(c) => handlePick(c)}
          />
          <CategorySection
            label="Ingresos"
            categories={sortedIncome}
            currentCategory={currentCategory}
            onPick={(c) => handlePick(c)}
          />
        </>
      )}
    </div>
  );
}

function DesktopPopover({
  open,
  onClose,
  anchorRef,
  children,
}: {
  open: boolean;
  onClose: () => void;
  anchorRef?: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
}) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    function updatePos() {
      const el = anchorRef?.current;
      if (!el) {
        // Fallback: center on viewport.
        setPos({ top: window.innerHeight / 2 - 200, left: window.innerWidth / 2 - 180 });
        return;
      }
      const rect = el.getBoundingClientRect();
      const width = 360;
      let left = rect.left;
      if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8;
      if (left < 8) left = 8;
      const top = rect.bottom + 6;
      setPos({ top, left });
    }
    updatePos();
    window.addEventListener("resize", updatePos);
    window.addEventListener("scroll", updatePos, true);
    return () => {
      window.removeEventListener("resize", updatePos);
      window.removeEventListener("scroll", updatePos, true);
    };
  }, [open, anchorRef]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (popoverRef.current?.contains(target)) return;
      if (anchorRef?.current?.contains(target)) return;
      onClose();
    }
    document.addEventListener("keydown", handleKey);
    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("mousedown", handleClick);
    };
  }, [open, onClose, anchorRef]);

  if (!open || !pos) return null;

  return createPortal(
    <div
      ref={popoverRef}
      role="dialog"
      aria-modal="false"
      aria-label="Categoría"
      className="fixed z-50 bg-white rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.16)] border border-slate-200 w-[360px] max-h-[70vh] overflow-y-auto p-4"
      style={{ top: pos.top, left: pos.left }}
    >
      <div className="text-sm font-semibold text-slate-900 mb-3">Categoría</div>
      {children}
    </div>,
    document.body
  );
}

export function CategoryPicker({
  open,
  onClose,
  currentCategory,
  onSelect,
  suggestions,
  dominantSign,
  inline,
  anchorRef,
}: CategoryPickerProps) {
  const body = (
    <PickerBody
      currentCategory={currentCategory}
      onSelect={onSelect}
      onClose={inline ? () => {} : onClose}
      suggestions={suggestions}
      dominantSign={dominantSign}
    />
  );

  if (inline) {
    return <div>{body}</div>;
  }

  return <ResponsiveShell open={open} onClose={onClose} anchorRef={anchorRef}>{body}</ResponsiveShell>;
}

function ResponsiveShell({
  open,
  onClose,
  anchorRef,
  children,
}: {
  open: boolean;
  onClose: () => void;
  anchorRef?: React.RefObject<HTMLElement | null>;
  children: React.ReactNode;
}) {
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  if (isDesktop) {
    return (
      <DesktopPopover open={open} onClose={onClose} anchorRef={anchorRef}>
        {children}
      </DesktopPopover>
    );
  }
  return (
    <BottomSheet open={open} onClose={onClose} title="Categoría">
      {children}
    </BottomSheet>
  );
}
