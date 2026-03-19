"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";
import { api } from "@/app/lib/api";

export function StoreInitializer() {
  const { userId, setUser, setHousehold } = useLukaStore();
  const router = useRouter();
  const attempted = useRef(false);

  useEffect(() => {
    // Already attempted — skip
    if (attempted.current) return;
    attempted.current = true;

    api
      .getMe()
      .then((user) => {
        setUser(String(user.id), user.full_name);
        if (user.household_id) {
          setHousehold(user.household_id);
        } else {
          // User exists in DB but has no household
          if (!window.location.pathname.includes("/onboarding")) {
            router.push("/onboarding/setup-household");
          }
        }
      })
      .catch(() => {
        // Backend unavailable (e.g. 401 / network error) — stay on page.
        // The dashboard will render with empty data; the user can try again.
        // Only redirect if backend explicitly tells us the user is not registered
        // (that case is handled above via the .then() branch).
      });
  }, [userId, setUser, setHousehold, router]);

  return null;
}
