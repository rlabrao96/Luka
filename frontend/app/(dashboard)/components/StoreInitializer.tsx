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

      // Prefetch 6-month transaction datasets so navigation is instant
      const since = getSince();
      queryClient.prefetchQuery({
        queryKey: ["transactions", "mine", since],
        queryFn: () => api.getMyTransactions(since),
        staleTime: 5 * 60 * 1000,
      });
      queryClient.prefetchQuery({
        queryKey: ["transactions", "shared", householdId, since],
        queryFn: () => api.getSharedTransactions(householdId, since),
        staleTime: 5 * 60 * 1000,
      });
    } else if (userId) {
      if (!window.location.pathname.includes("/onboarding")) {
        router.push("/onboarding/setup-household");
      }
    }
  }, [userId, householdId, userFullName, setUser, setHousehold, router, queryClient]);

  return null;
}
