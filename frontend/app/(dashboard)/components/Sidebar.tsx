"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, CreditCard, Users, PieChart, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLukaStore } from "@/app/lib/store";

const NAV = [
  { href: "/", label: "Inicio", icon: Home },
  { href: "/transactions", label: "Transacciones", icon: CreditCard },
  { href: "/household", label: "Hogar", icon: Users },
  { href: "/budgets", label: "Presupuesto", icon: PieChart },
  { href: "/settings", label: "Configuración", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const name = useLukaStore((s) => s.userFullName);
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="hidden lg:flex flex-col w-60 min-h-screen bg-white border-r border-slate-200 px-4 py-6 gap-2">
      <div className="mb-6 px-2">
        <h1 className="text-2xl font-bold text-luka-primary">Luka</h1>
        <p className="text-xs text-luka-muted mt-0.5">Finanzas personales</p>
      </div>
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className={cn(
            "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
            isActive(href)
              ? "bg-luka-light text-luka-primary"
              : "text-luka-muted hover:bg-slate-50 hover:text-luka-dark"
          )}
        >
          <Icon size={18} />
          {label}
        </Link>
      ))}
      <div className="mt-auto px-3 py-2 text-xs text-luka-muted">{name}</div>
    </aside>
  );
}
