"use client";
import Link from "next/link";
import { Bell } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUnreadCount } from "@/app/lib/hooks/useNotifications";

export function NotificationBadge() {
  const pathname = usePathname();
  const { data } = useUnreadCount();
  const count = data?.count ?? 0;
  const active = pathname.startsWith("/notifications");

  return (
    <Link
      href="/notifications"
      className={cn(
        "flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
        count > 0
          ? "bg-amber-50 text-amber-700 border border-amber-200"
          : active
            ? "bg-luka-primary text-white shadow-sm shadow-blue-200"
            : "text-luka-muted hover:bg-blue-50 hover:text-luka-dark"
      )}
    >
      <span className="flex items-center gap-3">
        <Bell size={17} strokeWidth={count > 0 ? 2.2 : 1.8} />
        Notificaciones
      </span>
      {count > 0 && (
        <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[20px] text-center">
          {count}
        </span>
      )}
    </Link>
  );
}
