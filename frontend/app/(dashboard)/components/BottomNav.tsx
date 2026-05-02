"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, MoreHorizontal } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { useUnreadCount } from "@/app/lib/hooks/useNotifications";
import { api } from "@/app/lib/api";
import { visibleNavItems, type NavItem } from "./nav-items";

function isActiveHref(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function BottomNav() {
  const pathname = usePathname();
  const { data } = useUnreadCount();
  const unreadCount = data?.count ?? 0;
  const [moreOpen, setMoreOpen] = useState(false);

  // Reuse the cached /auth/me payload (same query key as the rest of the app)
  // so flag-gated entries (e.g. Viajes) only render for opted-in users.
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
  const navItems = visibleNavItems({
    featureTripsEnabled: me?.feature_trips_enabled ?? false,
  });

  const primary = navItems.filter((i) => i.section === "primary");
  const more = navItems.filter((i) => i.section === "more");
  const moreActive = more.some((i) => isActiveHref(pathname, i.href));

  return (
    <>
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
          "flex items-stretch",
          "px-1 py-1"
        )}
      >
        {primary.map(({ href, label, shortLabel, icon: Icon }) => {
          const active = isActiveHref(pathname, href);
          const showDot = href === "/notifications" && unreadCount > 0;
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 rounded-xl transition-all duration-200",
                "text-[10px] font-medium relative min-h-[44px]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary focus-visible:ring-offset-1",
                active
                  ? "text-luka-primary bg-luka-primary-light/60"
                  : "text-slate-400 active:bg-slate-50"
              )}
            >
              <span className="relative">
                <Icon size={20} strokeWidth={active ? 2.2 : 1.7} />
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

        {/* Más — opens an overflow sheet. Marked active when the route matches
             one of the secondary sections so the user sees where they are. */}
        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          aria-label="Más opciones"
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
          aria-current={moreActive ? "page" : undefined}
          className={cn(
            "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 rounded-xl transition-all duration-200",
            "text-[10px] font-medium relative min-h-[44px]",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary focus-visible:ring-offset-1",
            moreActive
              ? "text-luka-primary bg-luka-primary-light/60"
              : "text-slate-400 active:bg-slate-50"
          )}
        >
          <MoreHorizontal size={20} strokeWidth={moreActive ? 2.2 : 1.7} />
          <span className="truncate max-w-full px-0.5">Más</span>
        </button>
      </nav>

      <BottomSheet open={moreOpen} onClose={() => setMoreOpen(false)} title="Más opciones">
        <div className="flex flex-col gap-1 pb-2">
          {more.map((item) => (
            <MoreRow
              key={item.href}
              item={item}
              active={isActiveHref(pathname, item.href)}
              onNavigate={() => setMoreOpen(false)}
            />
          ))}
        </div>
      </BottomSheet>
    </>
  );
}

function MoreRow({
  item,
  active,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  onNavigate: () => void;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 px-3 py-3 rounded-xl transition-colors min-h-[56px]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-luka-primary",
        active
          ? "bg-luka-primary-light/60 text-luka-primary"
          : "text-slate-700 hover:bg-slate-50 active:bg-slate-100"
      )}
    >
      <span
        className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors",
          active
            ? "bg-luka-primary text-white"
            : "bg-slate-100 text-slate-500"
        )}
      >
        <Icon size={18} strokeWidth={2} />
      </span>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm font-semibold truncate", active ? "text-luka-primary" : "text-luka-dark")}>
          {item.label}
        </p>
        <p className="text-xs text-luka-muted truncate">{item.description}</p>
      </div>
      <ChevronRight size={16} className="text-slate-300 shrink-0" />
    </Link>
  );
}
