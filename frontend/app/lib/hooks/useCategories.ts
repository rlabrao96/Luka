import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useCategories() {
  const { data } = useQuery({
    queryKey: ["category-preferences"],
    queryFn: () => api.getCategoryPreferences(),
    staleTime: Infinity,
  });

  // Partner-only categories (in some household member's prefs but not mine).
  // staleTime mirrors useHouseholdPartnerCategories so cells share the cache.
  const { data: partnerData } = useQuery({
    queryKey: ["household-categories"],
    queryFn: () => api.getHouseholdPartnerCategories(),
    staleTime: 60 * 1000,
  });

  const all = data?.categories ?? [];
  const expense = all.filter((c) => c.category_type === "expense").map((c) => c.category);
  const income = all.filter((c) => c.category_type === "income").map((c) => c.category);

  const partner = partnerData?.categories ?? [];
  const partnerExpense = partner
    .filter((c) => c.category_type === "expense")
    .map((c) => c.category);
  const partnerIncome = partner
    .filter((c) => c.category_type === "income")
    .map((c) => c.category);

  return { expense, income, partnerExpense, partnerIncome };
}
