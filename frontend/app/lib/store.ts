import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OnboardingDraft {
  type: "individual" | "group" | null;
  partnerEmail: string;
}

interface LukaStore {
  householdId: string | null;
  userId: string | null;
  userFullName: string | null;
  onboardingDraft: OnboardingDraft | null;
  setHousehold: (id: string) => void;
  setUser: (id: string, name: string) => void;
  setOnboardingDraft: (draft: OnboardingDraft | null) => void;
  reset: () => void;
}

export const useLukaStore = create<LukaStore>()(
  persist(
    (set) => ({
      householdId: null,
      userId: null,
      userFullName: null,
      onboardingDraft: null,
      setHousehold: (id) => set({ householdId: id }),
      setUser: (id, name) => set({ userId: id, userFullName: name }),
      setOnboardingDraft: (draft) => set({ onboardingDraft: draft }),
      reset: () =>
        set({
          householdId: null,
          userId: null,
          userFullName: null,
          onboardingDraft: null,
        }),
    }),
    {
      name: "luka-store",
      partialize: (state) => ({
        householdId: state.householdId,
        userId: state.userId,
        userFullName: state.userFullName,
      }),
    }
  )
);
