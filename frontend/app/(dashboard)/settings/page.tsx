"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { ProfileSection } from "./components/ProfileSection";
import { BankAccountsSection } from "./components/BankAccountsSection";
import { CompartidoSection } from "./components/CompartidoSection";
import { ContributionSection } from "./components/ContributionSection";
import { NotificationsSection } from "./components/NotificationsSection";
import { CategoriesSection } from "./components/CategoriesSection";
import { TransactionsConfigSection } from "./components/TransactionsConfigSection";
import { BudgetSettingsSection } from "./components/BudgetSettingsSection";
import { CategoryBudgetsSection } from "./components/CategoryBudgetsSection";
import { PrivacySection } from "./components/PrivacySection";
import { DeleteAccountSection } from "./components/DeleteAccountSection";

export default function SettingsPage() {
  const householdId = useLukaStore((s) => s.householdId);
  const queryClient = useQueryClient();

  // Prefetch categories in parallel with the me query so the section
  // renders instantly instead of waiting for a second waterfall request.
  useEffect(() => {
    queryClient.prefetchQuery({
      queryKey: ["category-preferences"],
      queryFn: () => api.getCategoryPreferences(),
      staleTime: 5 * 60 * 1000,
    });
  }, [queryClient]);

  const { data: me, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  if (isLoading || !me) {
    return (
      <div className="space-y-4 p-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-32 bg-white rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-32">
      <div>
        <h1 className="text-2xl font-bold text-luka-dark">Configuración</h1>
        <p className="text-sm text-slate-500 mt-1">Administra tu cuenta y preferencias</p>
      </div>

      <div className="space-y-4">
        <ProfileSection
          user={{
            full_name: me.full_name,
            email: me.email,
            phone_whatsapp: me.phone_whatsapp ?? null,
          }}
        />

        <TransactionsConfigSection preferredCurrency={me.preferred_currency ?? "CLP"} />

        <BankAccountsSection householdId={householdId} />

        <CompartidoSection />

        <ContributionSection />

        <BudgetSettingsSection />

        <CategoryBudgetsSection />

        <NotificationsSection />

        <CategoriesSection />

        <PrivacySection />

        <DeleteAccountSection />
      </div>
    </div>
  );
}
