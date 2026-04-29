import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export type HouseholdPartnerCategory = {
  category: string;
  category_type: "expense" | "income";
  member_ids: string[];
  count: number;
};

/**
 * List of categories that exist in OTHER active household members'
 * preference lists but NOT in mine. Surfaces partner-only categories so
 * they can be displayed (filter dropdowns, row dropdowns) and optionally
 * adopted into the caller's own preferences.
 *
 * Read-only with respect to partner rows.
 */
export function useHouseholdPartnerCategories() {
  return useQuery({
    queryKey: ["household-categories"],
    queryFn: () => api.getHouseholdPartnerCategories(),
    staleTime: 60 * 1000,
  });
}

/**
 * Adopt a partner's category into the caller's own preference list.
 * Idempotent. Invalidates both ["category-preferences"] and
 * ["household-categories"] so the surface settles consistently.
 */
export function useAdoptHouseholdCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      category,
      categoryType,
    }: {
      category: string;
      categoryType: "expense" | "income";
    }) => api.adoptHouseholdCategory(category, categoryType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["category-preferences"] });
      queryClient.invalidateQueries({ queryKey: ["household-categories"] });
    },
  });
}
