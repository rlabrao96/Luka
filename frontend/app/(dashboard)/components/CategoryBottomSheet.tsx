"use client";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { cn } from "@/lib/utils";

const EXPENSE_CATEGORIES = [
  "Alimentación", "Supermercado", "Transporte", "Combustible",
  "Entretenimiento", "Salud", "Farmacia", "Hogar",
  "Ropa", "Tecnología", "Educación", "Viajes", "Servicios", "Otros",
];

const INCOME_CATEGORIES = [
  "Sueldo", "Freelance", "Inversiones", "Arriendo",
  "Bono", "Transferencia de terceros", "Deuda pendiente", "Otros ingresos",
];

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
  const categories = isIncome ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

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
