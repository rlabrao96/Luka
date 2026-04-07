import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useCategories() {
  const { data } = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: Infinity,
  });

  const all = data?.categories ?? [];
  const expense = all.filter((c) => c.category_type === "expense").map((c) => c.category);
  const income = all.filter((c) => c.category_type === "income").map((c) => c.category);

  return { expense, income };
}
