"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";

interface Props {
  userId?: string | null;
  householdId?: string | null;
  userFullName?: string | null;
}

export function StoreInitializer({ userId, householdId, userFullName }: Props) {
  const { setUser, setHousehold } = useLukaStore();
  const router = useRouter();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    if (userId) {
      setUser(userId, userFullName ?? "");
    }
    if (householdId) {
      setHousehold(householdId);
    } else if (userId) {
      // Authenticated but no household — send to onboarding
      if (!window.location.pathname.includes("/onboarding")) {
        router.push("/onboarding/setup-household");
      }
    }
  }, [userId, householdId, userFullName, setUser, setHousehold, router]);

  return null;
}
