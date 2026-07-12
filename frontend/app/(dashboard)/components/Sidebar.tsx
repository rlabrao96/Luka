"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import { Search, LogOut } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useLukaStore } from "@/app/lib/store";
import { createClient } from "@/app/lib/supabase/client";
import { api } from "@/app/lib/api";
import { NotificationBadge } from "./NotificationBadge";
import { visibleNavItems } from "./nav-items";

export function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const name     = useLukaStore((s) => s.userFullName) ?? "";
  const reset    = useLukaStore((s) => s.reset);

  // Read feature flags off the cached /auth/me payload — same query key as the
  // rest of the app so this piggybacks on the existing fetch (no waterfall).
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  const navItems = visibleNavItems({
    featureTripsEnabled: me?.feature_trips_enabled ?? false,
  });

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    reset?.();
    router.push("/login");
  };

  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  return (
    <aside className="hidden lg:flex flex-col w-64 shrink-0 sticky top-0 h-screen bg-white border-r border-slate-200/80 shadow-sm">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-slate-100">
        <div className="flex items-center justify-center py-3 border border-blue-100 bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200">
          <Image 
            src="/logo-dashboard.svg" 
            alt="Luka Logo" 
            width={140} 
            height={44} 
            className="h-11 w-auto"
            priority
          />
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1 px-3 py-4 flex-1">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("luka:open-search"))}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:bg-slate-50 hover:text-luka-dark transition-all duration-150"
        >
          <Search size={18} />
          Buscar
          <kbd className="ml-auto hidden lg:inline text-[10px] font-semibold text-slate-400 border border-slate-200 rounded px-1">
            ⌘K
          </kbd>
        </button>
        <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Menú
        </p>
        {navItems.filter((i) => i.showInSidebar).map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
                active
                  ? "bg-luka-primary text-white shadow-sm shadow-blue-200"
                  : "text-luka-muted hover:bg-blue-50 hover:text-luka-dark"
              )}
            >
              <Icon size={17} strokeWidth={active ? 2.2 : 1.8} />
              {label}
            </Link>
          );
        })}
        <div className="mt-2 pt-2 border-t border-slate-100">
          <NotificationBadge />
        </div>
      </nav>

      {/* User profile + sign-out */}
      <div className="border-t border-slate-100 p-3">
        <div className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-slate-50 transition-colors">
          {/* Avatar */}
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {initials || "?"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-luka-dark truncate">{name || "Usuario"}</p>
            <p className="text-[10px] text-luka-muted truncate">Cuenta personal</p>
          </div>
        </div>
        <button
          onClick={handleSignOut}
          className="mt-1 flex w-full items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-slate-400 hover:bg-red-50 hover:text-red-500 transition-colors"
        >
          <LogOut size={16} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
