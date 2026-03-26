"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";

export function useSubscriptions() {
  return useQuery({
    queryKey: ["subscriptions", "detected"],
    queryFn: () => api.getSubscriptions(),
    staleTime: 5 * 60 * 1000,
  });
}
