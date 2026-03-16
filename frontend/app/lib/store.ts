import { create } from "zustand";
import { persist } from "zustand/middleware";

interface LukaStore {
  householdId: string | null;
  userId: string | null;
  userFullName: string | null;
  setHousehold: (id: string) => void;
  setUser: (id: string, name: string) => void;
}

export const useLukaStore = create<LukaStore>()(
  persist(
    (set) => ({
      householdId: null,
      userId: null,
      userFullName: null,
      setHousehold: (id) => set({ householdId: id }),
      setUser: (id, name) => set({ userId: id, userFullName: name }),
    }),
    { name: "luka-store" }
  )
);
