"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CreditCard, Users, Wallet, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/",             label: "Inicio",      icon: LayoutDashboard },
  { href: "/transactions", label: "Gastos",       icon: CreditCard      },
  { href: "/household",    label: "Hogar",         icon: Users           },
  { href: "/budgets",      label: "Presupuesto",  icon: Wallet          },
  { href: "/settings",     label: "Config",        icon: Settings        },
];

export function BottomNav() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      className={cn(
        "fixed left-3 right-3 z-50 lg:hidden",
        /* Lift above the home indicator: 8px base + iOS safe area */
        "bottom-[calc(0.5rem+env(safe-area-inset-bottom,0px))]",
        /* Floating card style */
        "bg-white/95 backdrop-blur-lg",
        "rounded-2xl",
        "shadow-[0_2px_24px_rgba(0,0,0,0.10)]",
        "border border-slate-100",
        /* Layout */
        "flex items-center",
        "px-1 py-1"
      )}
    >
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 rounded-xl transition-all duration-200",
              "text-[10px] font-medium",
              active
                ? "text-luka-primary bg-luka-primary-light/60"
                : "text-slate-400 active:bg-slate-50"
            )}
          >
            <Icon size={20} strokeWidth={active ? 2.2 : 1.7} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
