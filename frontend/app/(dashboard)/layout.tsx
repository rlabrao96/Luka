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
      cache: "no-store",
    });
    if (res.ok) userData = await res.json();
  } catch {
    // Network error — client-side StoreInitializer will handle it
  }

  if (userData && !userData.household_id) {
    redirect("/onboarding/setup-household");
  }

  return (
    <div className="flex min-h-screen bg-luka-surface overflow-x-clip">
      <StoreInitializer
        userId={userData?.id ?? null}
        householdId={userData?.household_id ?? null}
        userFullName={userData?.full_name ?? null}
      />
      <SessionGuard />
      {/* Sidebar — desktop only. Sticky so it stays put while the page
          scrolls naturally at the document level. A single scrollbar (the
          browser's) is less confusing than the nested main-scroll pattern. */}
      <Sidebar />
      {/*
        Main content — `min-w-0` lets the flex child shrink to the viewport
        width (flex defaults to min-content); without it, any descendant with
        long unbreakable text forces the page wider than the viewport and
        mobile browsers fall back to pinch-zoom. `overflow-x-clip` is a
        belt-and-suspenders guard against that.
      */}
      <main className="flex-1 min-w-0 overflow-x-clip pb-[calc(6rem+env(safe-area-inset-bottom,0px))] lg:pb-0">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {children}
        </div>
      </main>
      {/* Bottom nav — mobile only */}
      <BottomNav />
    </div>
  );
}
