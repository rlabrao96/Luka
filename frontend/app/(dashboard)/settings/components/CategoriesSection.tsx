"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "@/app/lib/api";

type CatPref = {
  category: string;
  sort_order: number;
  category_type: "expense" | "income";
  is_custom: boolean;
};

// ---------------------------------------------------------------------------
// DeleteConfirmModal
// ---------------------------------------------------------------------------

function DeleteConfirmModal({
  category,
  categoryType,
  allCats,
  onClose,
  onDeleted,
}: {
  category: string;
  categoryType: "expense" | "income";
  allCats: CatPref[];
  onClose: () => void;
  onDeleted: () => void;
}) {
  const queryClient = useQueryClient();
  const [reclassifyTo, setReclassifyTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: usageData, isLoading: usageLoading } = useQuery({
    queryKey: ["category-usage", category],
    queryFn: () => api.getCategoryUsage(category),
  });

  const count = usageData?.count ?? 0;
  const sameCats = allCats.filter(
    (c) => c.category !== category && c.category_type === categoryType
  );

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCategory(category, count > 0 ? reclassifyTo : null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      onDeleted();
    },
    onError: () => {
      setError("Error al eliminar. Intenta de nuevo.");
    },
  });

  const canConfirm = count === 0 || reclassifyTo !== null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-5">
        <h3 className="text-sm font-semibold text-slate-800 mb-1">
          Eliminar categoría
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          <span className="font-medium text-slate-700">{category}</span>
        </p>

        {usageLoading ? (
          <div className="h-4 w-48 bg-slate-100 rounded animate-pulse mb-4" />
        ) : count > 0 ? (
          <div className="mb-4">
            <p className="text-xs text-slate-600 mb-2">
              ¿En qué categoría quieres reclasificar las{" "}
              <span className="font-medium">{count}</span> transacciones que
              hasta este momento has clasificado como{" "}
              <span className="font-medium">{category}</span>?
            </p>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {sameCats.map((c) => (
                <label
                  key={c.category}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="reclassify"
                    value={c.category}
                    checked={reclassifyTo === c.category}
                    onChange={() => setReclassifyTo(c.category)}
                    className="accent-blue-500"
                  />
                  <span className="text-sm text-slate-700">{c.category}</span>
                </label>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500 mb-4">
            Esta categoría se eliminará de tu lista.
          </p>
        )}

        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}

        <div className="flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs text-slate-600 rounded-lg hover:bg-slate-50"
          >
            Cancelar
          </button>
          <button
            onClick={() => deleteMutation.mutate()}
            disabled={!canConfirm || deleteMutation.isPending}
            className="px-3 py-1.5 text-xs font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 disabled:opacity-40"
          >
            {count > 0 ? "Eliminar y reclasificar" : "Eliminar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SortableItem
// ---------------------------------------------------------------------------

function SortableItem({
  item,
  onDelete,
}: {
  item: CatPref;
  onDelete: (cat: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: item.category,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-2.5 py-2 bg-white rounded-lg border border-slate-100"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing p-0.5 touch-none"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          className="text-slate-300"
        >
          <circle cx="5" cy="4" r="1.5" fill="currentColor" />
          <circle cx="11" cy="4" r="1.5" fill="currentColor" />
          <circle cx="5" cy="8" r="1.5" fill="currentColor" />
          <circle cx="11" cy="8" r="1.5" fill="currentColor" />
          <circle cx="5" cy="12" r="1.5" fill="currentColor" />
          <circle cx="11" cy="12" r="1.5" fill="currentColor" />
        </svg>
      </button>
      <span className="flex-1 text-sm text-slate-700 truncate">{item.category}</span>
      {item.is_custom && (
        <span className="text-[10px] text-blue-600 font-medium px-1.5 py-0.5 rounded-full bg-blue-50 shrink-0">
          Tuya
        </span>
      )}
      <button
        onClick={() => onDelete(item.category)}
        className="p-1 rounded-md hover:bg-red-50 text-red-400 hover:text-red-600 min-w-[28px] min-h-[28px] flex items-center justify-center text-base font-medium"
        aria-label={`Eliminar ${item.category}`}
      >
        ×
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CategoryColumn
// ---------------------------------------------------------------------------

function CategoryColumn({
  title,
  items,
  sensors,
  onDragEnd,
  onDelete,
}: {
  title: string;
  items: CatPref[];
  sensors: ReturnType<typeof useSensors>;
  onDragEnd: (event: DragEndEvent, group: "expense" | "income") => void;
  onDelete: (cat: string) => void;
}) {
  const group = title === "Ingresos" ? "income" : "expense";

  return (
    <div>
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
        {title}
      </p>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={(e) => onDragEnd(e, group)}
      >
        <SortableContext
          items={items.map((c) => c.category)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-1.5">
            {items.map((item) => (
              <SortableItem key={item.category} item={item} onDelete={onDelete} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CategoriesSection
// ---------------------------------------------------------------------------

export function CategoriesSection() {
  const queryClient = useQueryClient();
  const [localCats, setLocalCats] = useState<CatPref[]>([]);
  const [addInput, setAddInput] = useState("");
  const [addType, setAddType] = useState<"expense" | "income">("expense");
  const [addError, setAddError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<CatPref | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const { data, isLoading } = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (data?.categories) {
      setLocalCats(data.categories);
    }
  }, [data]);

  const reorderMutation = useMutation({
    mutationFn: (cats: CatPref[]) => {
      const expense = cats
        .filter((c) => c.category_type === "expense")
        .map((c, i) => ({ category: c.category, sort_order: i }));
      const income = cats
        .filter((c) => c.category_type === "income")
        .map((c, i) => ({ category: c.category, sort_order: i }));
      return api.reorderCategoryPreferences([...expense, ...income]);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
    },
  });

  const addMutation = useMutation({
    mutationFn: () => api.addCategory(addInput.trim(), addType),
    onSuccess: () => {
      setAddInput("");
      setAddError(null);
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
    },
    onError: async (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : "Error al agregar categoría";
      if (msg.includes("409") || msg.toLowerCase().includes("duplicate")) {
        setAddError("Ya tienes una categoría con ese nombre");
      } else if (msg.includes("422") || msg.toLowerCase().includes("limit")) {
        setAddError("Límite de 19 categorías alcanzado");
      } else {
        setAddError(msg);
      }
    },
  });

  const mutateRef = useRef(reorderMutation.mutate);
  mutateRef.current = reorderMutation.mutate;

  const debouncedSave = useCallback((cats: CatPref[]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      mutateRef.current(cats);
    }, 500);
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const expenseCats = localCats.filter((c) => c.category_type === "expense");
  const incomeCats = localCats.filter((c) => c.category_type === "income");

  function handleDragEnd(event: DragEndEvent, group: "expense" | "income") {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const groupCats = group === "expense" ? expenseCats : incomeCats;
    const oldIndex = groupCats.findIndex((c) => c.category === active.id);
    const newIndex = groupCats.findIndex((c) => c.category === over.id);
    const reorderedGroup = arrayMove(groupCats, oldIndex, newIndex);

    const updated =
      group === "expense"
        ? [...reorderedGroup, ...incomeCats]
        : [...expenseCats, ...reorderedGroup];

    setLocalCats(updated);
    debouncedSave(updated);
  }

  const addTypeExpenseCount = expenseCats.length;
  const addTypeIncomeCount = incomeCats.length;
  const addDisabled =
    !addInput.trim() ||
    addMutation.isPending ||
    (addType === "expense" && addTypeExpenseCount >= 20) ||
    (addType === "income" && addTypeIncomeCount >= 20);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <div className="h-4 w-32 bg-slate-100 rounded animate-pulse mb-4" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-10 bg-slate-50 rounded-lg animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  return (
    <>
      <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">
          Categorías
        </h3>
        <p className="text-xs text-slate-400 mb-4">Arrastra para reordenar.</p>

        {/* Add row — stacks on mobile */}
        <div className="flex flex-col sm:flex-row gap-2 mb-2">
          <input
            type="text"
            value={addInput}
            onChange={(e) => {
              setAddInput(e.target.value);
              setAddError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !addDisabled) addMutation.mutate();
            }}
            maxLength={40}
            placeholder="Nueva categoría"
            className="w-full sm:flex-1 text-base sm:text-sm border border-slate-200 rounded-xl px-3 py-2 outline-none focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
          <div className="flex gap-2">
            <div className="flex gap-1 shrink-0">
              <button
                onClick={() => setAddType("expense")}
                className={`flex-1 sm:flex-none px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  addType === "expense"
                    ? "bg-blue-600 text-white"
                    : "bg-white text-slate-500 border border-slate-200 hover:bg-slate-50"
                }`}
              >
                Gasto
              </button>
              <button
                onClick={() => setAddType("income")}
                className={`flex-1 sm:flex-none px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                  addType === "income"
                    ? "bg-sky-500 text-white"
                    : "bg-white text-slate-500 border border-slate-200 hover:bg-slate-50"
                }`}
              >
                Ingreso
              </button>
            </div>
            <button
              onClick={() => addMutation.mutate()}
              disabled={addDisabled}
              className="flex-1 sm:flex-none px-4 py-1.5 text-xs font-semibold rounded-lg shrink-0 transition-colors bg-luka-primary text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
            >
              Agregar
            </button>
          </div>
        </div>

        {addError && <p className="text-xs text-red-500 mb-2">{addError}</p>}
        {!addError && addInput.trim() && (
          (addType === "expense" && addTypeExpenseCount >= 20)
            ? <p className="text-xs text-amber-600 mb-2">Límite de 20 gastos alcanzado. Elimina una para agregar otra.</p>
            : (addType === "income" && addTypeIncomeCount >= 20)
              ? <p className="text-xs text-amber-600 mb-2">Límite de 20 ingresos alcanzado. Elimina una para agregar otra.</p>
              : null
        )}

        {/* Counter line */}
        <p className="text-xs text-slate-400 mb-4">
          Gastos: {expenseCats.length}/20 · Ingresos: {incomeCats.length}/20
        </p>

        {/* Two-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="order-1">
            <CategoryColumn
              title="Ingresos"
              items={incomeCats}
              sensors={sensors}
              onDragEnd={handleDragEnd}
              onDelete={(cat) => {
                const found = localCats.find((c) => c.category === cat);
                if (found) setDeleteTarget(found);
              }}
            />
          </div>
          <div className="order-2">
            <CategoryColumn
              title="Gastos"
              items={expenseCats}
              sensors={sensors}
              onDragEnd={handleDragEnd}
              onDelete={(cat) => {
                const found = localCats.find((c) => c.category === cat);
                if (found) setDeleteTarget(found);
              }}
            />
          </div>
        </div>

        {reorderMutation.isError && (
          <p className="text-xs text-red-500 mt-2">Error al guardar. Intenta de nuevo.</p>
        )}
      </div>

      {deleteTarget && (
        <DeleteConfirmModal
          category={deleteTarget.category}
          categoryType={deleteTarget.category_type}
          allCats={localCats}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => {
            setLocalCats((prev) => prev.filter((c) => c.category !== deleteTarget.category));
            setDeleteTarget(null);
          }}
        />
      )}
    </>
  );
}
