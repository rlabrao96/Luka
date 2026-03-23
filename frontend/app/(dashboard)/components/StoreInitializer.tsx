"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useLukaStore } from "@/app/lib/store";
import { api } from "@/app/lib/api";

interface Props {
  userId?: string | null;
  householdId?: string | null;
  userFullName?: string | null;
}

function getSince(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 6);
  return d.toISOString().split("T")[0];
}

function getMonthParam(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export function StoreInitializer({ userId, householdId, userFullName }: Props) {
  const { setUser, setHousehold } = useLukaStore();
  const router = useRouter();
  const queryClient = useQueryClient();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    if (userId) {
      setUser(userId, userFullName ?? "");
    }
    if (householdId) {
      setHousehold(householdId);

      const since = getSince();
      const month = getMonthParam();
      const staleTime = 5 * 60 * 1000;

      // Prefetch all dashboard data in parallel so navigation is instant
      queryClient.prefetchQuery({
        queryKey: ["transactions", "mine", since],
        queryFn: () => api.getMyTransactions(since),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["transactions", "shared", householdId, since],
        queryFn: () => api.getSharedTransactions(householdId, since),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["transactions", "monthly-summary", householdId],
        queryFn: () => api.getMonthlySpending(householdId),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["household", "summary", householdId],
        queryFn: () => api.getHouseholdSummary(householdId),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["budget", householdId, undefined],
        queryFn: () => api.getBudgetStatus(householdId),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["personalBudget", householdId, month],
        queryFn: () => api.getPersonalBudget(householdId, month),
        staleTime,
      });
      queryClient.prefetchQuery({
        queryKey: ["allocation", householdId, month],
        queryFn: () => api.getAllocation(householdId, month),
        staleTime,
      });
    } else if (userId) {
      if (!window.location.pathname.includes("/onboarding")) {
        router.push("/onboarding/setup-household");
      }
    }
  }, [userId, householdId, userFullName, setUser, setHousehold, router, queryClient]);

  return null;
}
