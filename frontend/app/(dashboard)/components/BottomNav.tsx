"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, CreditCard, Users, PieChart, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Inicio", icon: Home },
  { href: "/dashboard/transactions", label: "Gastos", icon: CreditCard },
  { href: "/dashboard/household", label: "Hogar", icon: Users },
  { href: "/dashboard/budgets", label: "Presupuesto", icon: PieChart },
  { href: "/dashboard/settings", label: "Config", icon: Settings },
];

export function BottomNav() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === href : pathname.startsWith(href);
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 flex z-50">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs font-medium transition-colors",
            isActive(href) ? "text-luka-primary" : "text-luka-muted"
          )}
        >
          <Icon size={20} />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}
