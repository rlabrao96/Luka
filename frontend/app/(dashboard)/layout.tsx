import { Sidebar } from "./components/Sidebar";
import { BottomNav } from "./components/BottomNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-luka-light">
      <Sidebar />
      <main className="flex-1 p-4 lg:p-8 pb-20 lg:pb-8 overflow-auto">
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
