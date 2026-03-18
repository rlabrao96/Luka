import dynamic from "next/dynamic";
import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";
import { StoreInitializer } from "./components/StoreInitializer";
import { InactivityGuard } from "./components/InactivityGuard";

// Rendered client-side only to avoid hydration mismatch
// (the banner polls an API and its initial state differs between server and client)
const ImportStatusBanner = dynamic(
  () => import("./components/ImportStatusBanner").then((m) => m.ImportStatusBanner),
  { ssr: false }
);

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-luka-surface">
      <StoreInitializer />
      <InactivityGuard />
      {/* Sidebar — desktop only */}
      <Sidebar />
      {/* Main scrolling area */}
      <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
        <ImportStatusBanner />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
          {children}
        </div>
      </main>
      {/* Bottom nav — mobile only */}
      <BottomNav />
    </div>
  );
}
