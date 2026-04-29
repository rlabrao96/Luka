"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { findDuplicate, toCategoryCase } from "@/app/lib/category-dedup";
import {
  useAdoptHouseholdCategory,
  useHouseholdPartnerCategories,
} from "@/app/lib/hooks/useHouseholdCategories";

const COLLATOR = new Intl.Collator("es", { sensitivity: "base" });

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

  // Sentinel for "leave transactions uncategorized" radio. Backend receives null.
  const NONE = "__none__";
  const wireReclassify = reclassifyTo === NONE ? null : reclassifyTo;

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteCategory(category, wireReclassify),
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
              <label
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 cursor-pointer border-t border-slate-100 mt-1 pt-2"
              >
                <input
                  type="radio"
                  name="reclassify"
                  value={NONE}
                  checked={reclassifyTo === NONE}
                  onChange={() => setReclassifyTo(NONE)}
                  className="accent-slate-500"
                />
                <span className="text-sm text-slate-500 italic">
                  Dejar sin categoría
                </span>
              </label>
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
            {count === 0
              ? "Eliminar"
              : reclassifyTo === NONE
                ? "Eliminar y dejar sin categoría"
                : "Eliminar y reclasificar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CategoryRow
// ---------------------------------------------------------------------------

function CategoryRow({
  item,
  onDelete,
}: {
  item: CatPref;
  onDelete: (cat: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 px-2.5 py-2 bg-white rounded-lg border border-slate-100">
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
  onDelete,
}: {
  title: string;
  items: CatPref[];
  onDelete: (cat: string) => void;
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
        {title}
      </p>
      <div className="space-y-1.5">
        {items.map((item) => (
          <CategoryRow key={item.category} item={item} onDelete={onDelete} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// HouseholdPartnerCategoriesSection
// ---------------------------------------------------------------------------

function HouseholdPartnerCategoriesSection() {
  const { data, isLoading } = useHouseholdPartnerCategories();
  const adopt = useAdoptHouseholdCategory();
  const [pending, setPending] = useState<string | null>(null);

  const items = data?.categories ?? [];
  if (isLoading || items.length === 0) return null;

  const sorted = [...items].sort((a, b) => {
    if (a.category_type !== b.category_type) {
      return a.category_type === "expense" ? -1 : 1;
    }
    return COLLATOR.compare(a.category, b.category);
  });

  // Plural-aware copy: a single distinct partner → singular, else plural.
  const distinctPartners = new Set(items.flatMap((i) => i.member_ids));
  const title =
    distinctPartners.size <= 1
      ? "Categorías de tu pareja"
      : "Categorías de tu hogar";

  function handleAdd(category: string, categoryType: "expense" | "income") {
    const key = `${categoryType}::${category}`;
    setPending(key);
    adopt.mutate(
      { category, categoryType },
      { onSettled: () => setPending(null) }
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">
        {title}
      </h3>
      <p className="text-xs text-slate-400 mb-4">
        Usadas por otros miembros de tu hogar. Añádelas a tu lista para usarlas tú también.
      </p>
      <div className="space-y-1.5">
        {sorted.map((item) => {
          const key = `${item.category_type}::${item.category}`;
          const isPending = pending === key;
          return (
            <div
              key={key}
              className="flex items-center gap-2 px-2.5 py-2 bg-emerald-50 rounded-lg border border-emerald-100"
            >
              <span className="flex-1 text-sm text-emerald-700 truncate">
                {item.category}
              </span>
              <span className="text-[10px] text-emerald-600 font-medium px-1.5 py-0.5 rounded-full bg-emerald-100/70 shrink-0 uppercase tracking-wide">
                {item.category_type === "expense" ? "Gasto" : "Ingreso"}
              </span>
              <button
                onClick={() => handleAdd(item.category, item.category_type)}
                disabled={isPending}
                className="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 min-h-[28px] shrink-0"
                aria-label={`Añadir ${item.category}`}
              >
                {isPending ? "…" : "+ Añadir"}
              </button>
            </div>
          );
        })}
      </div>
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
  const [nearMatch, setNearMatch] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<CatPref | null>(null);

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

  const addMutation = useMutation({
    mutationFn: () => api.addCategory(toCategoryCase(addInput), addType),
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

  // Reset the near-match dialog whenever the input changes — a new edit
  // means the previous suggestion no longer applies.
  function handleInputChange(value: string) {
    setAddInput(value);
    setAddError(null);
    if (nearMatch) setNearMatch(null);
  }

  // Run dedup check before firing the API call. Exact dupe → inline error.
  // Near match → confirmation dialog. Otherwise submit as today.
  function handleAdd() {
    const trimmed = addInput.trim();
    if (!trimmed) return;
    const sameTypeNames = localCats
      .filter((c) => c.category_type === addType)
      .map((c) => c.category);
    const dup = findDuplicate(trimmed, sameTypeNames);
    if (dup.kind === "exact") {
      setAddError(`Ya tienes la categoría "${dup.canonical}".`);
      return;
    }
    if (dup.kind === "near") {
      setNearMatch(dup.canonical);
      return;
    }
    addMutation.mutate();
  }

  const expenseCats = localCats
    .filter((c) => c.category_type === "expense")
    .sort((a, b) => COLLATOR.compare(a.category, b.category));
  const incomeCats = localCats
    .filter((c) => c.category_type === "income")
    .sort((a, b) => COLLATOR.compare(a.category, b.category));

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
      <div className="space-y-4">
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
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !addDisabled) handleAdd();
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
              onClick={handleAdd}
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
              onDelete={(cat) => {
                const found = localCats.find((c) => c.category === cat);
                if (found) setDeleteTarget(found);
              }}
            />
          </div>
        </div>
      </div>

      <HouseholdPartnerCategoriesSection />
      </div>

      {nearMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-2">
              ¿Quisiste decir <span className="text-blue-600">{nearMatch}</span>?
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Si es algo distinto, podés crearla igual.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => {
                  setNearMatch(null);
                  setAddInput("");
                  setAddError(null);
                }}
                className="px-3 py-1.5 text-xs font-medium text-white bg-luka-primary rounded-lg hover:bg-blue-700"
              >
                Usar {nearMatch}
              </button>
              <button
                onClick={() => {
                  setNearMatch(null);
                  addMutation.mutate();
                }}
                className="px-3 py-1.5 text-xs text-slate-600 rounded-lg hover:bg-slate-50"
              >
                Crear igual
              </button>
            </div>
          </div>
        </div>
      )}

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
