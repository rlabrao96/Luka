import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OnboardingDraft {
  type: "individual" | "group" | null;
  memberEmail: string;
}

interface LukaStore {
  householdId: string | null;
  userId: string | null;
  userFullName: string | null;
  onboardingDraft: OnboardingDraft | null;
  /** Opt-in: surface the "Marcar como cuota" action on expense rows.
   *  Kept client-only for now; persisted per device via localStorage. */
  showCuotaButton: boolean;
  setHousehold: (id: string) => void;
  setUser: (id: string, name: string) => void;
  setOnboardingDraft: (draft: OnboardingDraft | null) => void;
  setShowCuotaButton: (enabled: boolean) => void;
  reset: () => void;
}

export const useLukaStore = create<LukaStore>()(
  persist(
    (set) => ({
      householdId: null,
      userId: null,
      userFullName: null,
      onboardingDraft: null,
      showCuotaButton: false,
      setHousehold: (id) => set({ householdId: id }),
      setUser: (id, name) => set({ userId: id, userFullName: name }),
      setOnboardingDraft: (draft) => set({ onboardingDraft: draft }),
      setShowCuotaButton: (enabled) => set({ showCuotaButton: enabled }),
      reset: () =>
        set({
          householdId: null,
          userId: null,
          userFullName: null,
          onboardingDraft: null,
          // showCuotaButton survives sign-out on purpose: it's a device
          // preference, not tied to the user session.
        }),
    }),
    {
      name: "luka-store",
      partialize: (state) => ({
        householdId: state.householdId,
        userId: state.userId,
        userFullName: state.userFullName,
        onboardingDraft: state.onboardingDraft,
        showCuotaButton: state.showCuotaButton,
      }),
    }
  )
);
