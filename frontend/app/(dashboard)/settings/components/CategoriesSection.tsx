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

type CatPref = { category: string; sort_order: number; hidden: boolean };

function SortableItem({
  item,
  onToggleHidden,
}: {
  item: CatPref;
  onToggleHidden: (cat: string) => void;
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
      className={`flex items-center gap-3 px-3 py-2.5 bg-white rounded-lg border border-slate-100 ${
        item.hidden ? "opacity-40" : ""
      }`}
    >
      <button {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing p-1 touch-none">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="text-slate-300">
          <circle cx="5" cy="4" r="1.5" fill="currentColor" />
          <circle cx="11" cy="4" r="1.5" fill="currentColor" />
          <circle cx="5" cy="8" r="1.5" fill="currentColor" />
          <circle cx="11" cy="8" r="1.5" fill="currentColor" />
          <circle cx="5" cy="12" r="1.5" fill="currentColor" />
          <circle cx="11" cy="12" r="1.5" fill="currentColor" />
        </svg>
      </button>
      <span className="flex-1 text-sm text-slate-700">{item.category}</span>
      <button
        onClick={() => onToggleHidden(item.category)}
        className="p-1.5 rounded-md hover:bg-slate-50 min-w-[44px] min-h-[44px] flex items-center justify-center"
      >
        {item.hidden ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-300">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
            <line x1="1" y1="1" x2="23" y2="23" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-500">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    </div>
  );
}

export function CategoriesSection() {
  const queryClient = useQueryClient();
  const [localCats, setLocalCats] = useState<CatPref[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const { data, isLoading } = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
  });

  useEffect(() => {
    if (data?.categories) {
      setLocalCats(data.categories);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (cats: CatPref[]) => api.updateCategoryPreferences(cats),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
    },
  });

  const mutateRef = useRef(mutation.mutate);
  mutateRef.current = mutation.mutate;

  const debouncedSave = useCallback(
    (cats: CatPref[]) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        mutateRef.current(cats);
      }, 500);
    },
    []
  );

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(TouchSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = localCats.findIndex((c) => c.category === active.id);
    const newIndex = localCats.findIndex((c) => c.category === over.id);
    const reordered = arrayMove(localCats, oldIndex, newIndex).map((c, i) => ({
      ...c,
      sort_order: i,
    }));
    setLocalCats(reordered);
    debouncedSave(reordered);
  }

  function handleToggleHidden(category: string) {
    const updated = localCats.map((c) =>
      c.category === category ? { ...c, hidden: !c.hidden } : c
    );
    setLocalCats(updated);
    debouncedSave(updated);
  }

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

  const visible = localCats.filter((c) => !c.hidden);
  const hidden = localCats.filter((c) => c.hidden);
  const sorted = [...visible, ...hidden];

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] p-5">
      <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">
        Categorías
      </h3>
      <p className="text-xs text-slate-400 mb-3">Arrastra para reordenar. Oculta las que no uses.</p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={sorted.map((c) => c.category)} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {sorted.map((item) => (
              <SortableItem key={item.category} item={item} onToggleHidden={handleToggleHidden} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      {mutation.isError && (
        <p className="text-xs text-red-500 mt-2">Error al guardar. Intenta de nuevo.</p>
      )}
    </div>
  );
}
