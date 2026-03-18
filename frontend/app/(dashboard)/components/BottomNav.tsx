"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CreditCard, Users, Wallet, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/",             label: "Inicio",       icon: LayoutDashboard },
  { href: "/transactions", label: "Gastos",        icon: CreditCard      },
  { href: "/household",    label: "Hogar",          icon: Users           },
  { href: "/budgets",      label: "Presupuesto",   icon: Wallet          },
  { href: "/settings",     label: "Config",         icon: Settings        },
];

export function BottomNav() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur border-t border-slate-200 flex z-50 lg:hidden">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex-1 flex flex-col items-center justify-center py-2.5 gap-0.5 text-[10px] font-medium transition-colors",
              active ? "text-luka-primary" : "text-slate-400"
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
