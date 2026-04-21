"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Image from "next/image";
import {
  LayoutDashboard,
  CreditCard,
  Users,
  Wallet,
  Repeat,
  Settings,
  LogOut,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useLukaStore } from "@/app/lib/store";
import { createClient } from "@/app/lib/supabase/client";
import { NotificationBadge } from "./NotificationBadge";

const NAV = [
  { href: "/",             label: "Dashboard",      icon: LayoutDashboard },
  { href: "/transactions", label: "Transacciones",  icon: CreditCard      },
  { href: "/household",    label: "Compartido",      icon: Users           },
  { href: "/budgets",      label: "Presupuesto",     icon: Wallet          },
  { href: "/subscriptions", label: "Suscripciones",  icon: Repeat          },
  { href: "/settings",     label: "Configuración",   icon: Settings        },
];

export function Sidebar() {
  const pathname = usePathname();
  const router   = useRouter();
  const name     = useLukaStore((s) => s.userFullName) ?? "";
  const reset    = useLukaStore((s) => s.reset);

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
        <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
          Menú
        </p>
        {NAV.map(({ href, label, icon: Icon }) => {
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
