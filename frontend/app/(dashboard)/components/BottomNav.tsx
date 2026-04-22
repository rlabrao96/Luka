"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUnreadCount } from "@/app/lib/hooks/useNotifications";
import { NAV_ITEMS } from "./nav-items";

export function BottomNav() {
  const pathname = usePathname();
  const { data } = useUnreadCount();
  const unreadCount = data?.count ?? 0;
  const items = NAV_ITEMS.filter((i) => i.showInBottom);
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <nav
      aria-label="Navegación principal"
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
      {items.map(({ href, label, shortLabel, icon: Icon }) => {
        const active = isActive(href);
        const showDot = href === "/notifications" && unreadCount > 0;
        return (
          <Link
            key={href}
            href={href}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 rounded-xl transition-all duration-200",
              "text-[9.5px] font-medium relative min-h-[44px]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary focus-visible:ring-offset-1",
              active
                ? "text-luka-primary bg-luka-primary-light/60"
                : "text-slate-400 active:bg-slate-50"
            )}
          >
            <span className="relative">
              <Icon size={18} strokeWidth={active ? 2.2 : 1.7} />
              {showDot && (
                <span
                  aria-hidden
                  className="absolute -top-0.5 -right-1 w-2 h-2 bg-red-500 rounded-full border border-white"
                />
              )}
            </span>
            <span className="truncate max-w-full px-0.5">{shortLabel}</span>
          </Link>
        );
      })}
    </nav>
  );
}
