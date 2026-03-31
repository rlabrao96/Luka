"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { ProfileSection } from "./components/ProfileSection";
import { BankAccountsSection } from "./components/BankAccountsSection";
import { HogarSection } from "./components/HogarSection";
import { NotificationsSection } from "./components/NotificationsSection";
import { CategoriesSection } from "./components/CategoriesSection";
import { TransactionsConfigSection } from "./components/TransactionsConfigSection";
import { PrivacySection } from "./components/PrivacySection";
import { DeleteAccountSection } from "./components/DeleteAccountSection";

export default function SettingsPage() {
  const householdId = useLukaStore((s) => s.householdId);

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

        <HogarSection />

        <NotificationsSection />

        <CategoriesSection />

        <PrivacySection />

        <DeleteAccountSection />
      </div>
    </div>
  );
}
