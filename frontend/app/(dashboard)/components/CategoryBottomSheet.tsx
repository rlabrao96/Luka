"use client";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { cn } from "@/lib/utils";
import { useCategories } from "@/app/lib/hooks/useCategories";

interface CategoryBottomSheetProps {
  open: boolean;
  onClose: () => void;
  currentCategory: string | null;
  isIncome: boolean;
  onSelect: (category: string | null) => void;
}

export function CategoryBottomSheet({
  open,
  onClose,
  currentCategory,
  isIncome,
  onSelect,
}: CategoryBottomSheetProps) {
  const { expense: expenseCats, income: incomeCats } = useCategories();
  const categories = isIncome ? incomeCats : expenseCats;

  function handleSelect(cat: string | null) {
    onSelect(cat);
    onClose();
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Categoría">
      <button
        onClick={() => handleSelect(null)}
        className="w-full text-left px-3 py-2.5 text-sm text-slate-400 hover:bg-slate-50 rounded-lg"
      >
        Sin categoría
      </button>
      <div className="h-px bg-slate-100 my-1" />
      {categories.map((cat) => (
        <button
          key={cat}
          onClick={() => handleSelect(cat)}
          className={cn(
            "w-full text-left px-3 py-2.5 text-sm hover:bg-blue-50 hover:text-luka-primary rounded-lg transition-colors",
            currentCategory === cat
              ? "text-luka-primary font-semibold bg-blue-50"
              : "text-slate-700"
          )}
        >
          {cat}
        </button>
      ))}
    </BottomSheet>
  );
}
