import { cn } from "@/lib/utils";
import { type LucideIcon } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
  icon?: LucideIcon;
  iconColor?: string;
  iconTextColor?: string;
}

export function KpiCard({
  label,
  value,
  sublabel,
  trend,
  className,
  icon: Icon,
  iconColor = "bg-blue-100",
  iconTextColor = "text-blue-600",
}: KpiCardProps) {
  return (
    <div
      className={cn(
        "bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)] p-4 flex flex-col gap-3",
        className
      )}
    >
      {Icon && (
        <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", iconColor)}>
          <Icon size={20} className={iconTextColor} strokeWidth={2} />
        </div>
      )}
      <div>
        <p className="text-xs font-medium text-luka-muted uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-luka-dark mt-1 tabular-nums">{value}</p>
        {sublabel && (
          <p
            className={cn(
              "text-xs mt-1 font-medium",
              trend === "up"   ? "text-luka-success" :
              trend === "down" ? "text-luka-danger"  : "text-luka-muted"
            )}
          >
            {trend === "up" ? "▲ " : trend === "down" ? "▼ " : ""}
            {sublabel}
          </p>
        )}
      </div>
    </div>
  );
}
