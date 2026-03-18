import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";
import { StoreInitializer } from "./components/StoreInitializer";
import { InactivityGuard } from "./components/InactivityGuard";
import { ImportStatusBannerClient } from "./components/ImportStatusBannerClient";
import { createClient } from "@/app/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const { data: { session } } = await supabase.auth.getSession();

  // SSR enforce household setup to completely prevent visual flash
  if (session) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    try {
      const res = await fetch(`${apiUrl}/auth/me`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
        cache: 'no-store'
      });
      if (res.ok) {
        const user = await res.json();
        if (!user.household_id) {
          redirect("/onboarding/verify-whatsapp");
        }
      }
    } catch (e) {
      // Silent catch; fallback to client-side StoreInitializer if network fails
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-luka-surface">
      <StoreInitializer />
      <InactivityGuard />
      {/* Sidebar — desktop only */}
      <Sidebar />
      {/* Main scrolling area */}
      <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
        <ImportStatusBannerClient />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {children}
        </div>
      </main>
      {/* Bottom nav — mobile only */}
      <BottomNav />
    </div>
  );
}
