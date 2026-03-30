import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";
import { StoreInitializer } from "./components/StoreInitializer";
import { SessionGuard } from "./components/SessionGuard";
import { createClient } from "@/app/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  // Use getSession() (reads cookie locally, ~0ms) instead of getUser() (external API, ~50-100ms).
  // Backend validates the JWT on /auth/me — no need to double-validate here.
  const { data: { session } } = await supabase.auth.getSession();
  const authUser = session?.user ?? null;

  if (!authUser) {
    redirect("/login");
  }

  // Fetch user profile once here (SSR) — pass to StoreInitializer so client
  // queries can fire immediately without a client-side getMe() waterfall.
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  let userData: { id: string; full_name: string; household_id: string | null } | null = null;
  try {
    const res = await fetch(`${apiUrl}/auth/me`, {
      headers: { Authorization: `Bearer ${session?.access_token}` },
      next: { revalidate: 60 },
    });
    if (res.ok) userData = await res.json();
  } catch {
    // Network error — client-side StoreInitializer will handle it
  }

  if (userData && !userData.household_id) {
    redirect("/onboarding/setup-household");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-luka-surface">
      <StoreInitializer
        userId={userData?.id ?? null}
        householdId={userData?.household_id ?? null}
        userFullName={userData?.full_name ?? null}
      />
      <SessionGuard />
      {/* Sidebar — desktop only */}
      <Sidebar />
      {/* Main scrolling area */}
      <main className="flex-1 overflow-y-auto pb-24 lg:pb-0">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {children}
        </div>
      </main>
      {/* Bottom nav — mobile only */}
      <BottomNav />
    </div>
  );
}
