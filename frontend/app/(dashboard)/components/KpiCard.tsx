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
  /** Optional overrides for the inner elements. Use `valueClassName` to recolor
   *  the main number (e.g., red for negative positions). */
  valueClassName?: string;
  /** `default`: roomy card (icon + 2xl value). `compact`: tighter layout used
   *  for dense summary bars (no icon chip, lg value, truncating). */
  variant?: "default" | "compact";
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
  valueClassName,
  variant = "default",
}: KpiCardProps) {
  const isCompact = variant === "compact";
  return (
    <div
      className={cn(
        "bg-white rounded-xl border border-slate-100 shadow-[var(--shadow-card)]",
        isCompact ? "p-4" : "p-4 flex flex-col gap-3",
        className
      )}
    >
      {Icon && !isCompact && (
        <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", iconColor)}>
          <Icon size={20} className={iconTextColor} strokeWidth={2} />
        </div>
      )}
      <div>
        <p
          className={cn(
            "font-medium uppercase leading-tight",
            isCompact
              ? "text-[10px] tracking-widest text-slate-400"
              : "text-xs tracking-wide text-luka-muted"
          )}
        >
          {label}
        </p>
        <p
          className={cn(
            "font-bold mt-1 tabular-nums",
            isCompact ? "text-lg truncate" : "text-2xl",
            valueClassName ?? "text-luka-dark"
          )}
        >
          {value}
        </p>
        {sublabel && (
          <p
            className={cn(
              "mt-0.5 font-medium",
              isCompact ? "text-[10px] text-slate-400" : "text-xs",
              !isCompact && (
                trend === "up"   ? "text-luka-success" :
                trend === "down" ? "text-luka-danger"  : "text-luka-muted"
              )
            )}
          >
            {!isCompact && trend === "up" ? "▲ " : !isCompact && trend === "down" ? "▼ " : ""}
            {sublabel}
          </p>
        )}
      </div>
    </div>
  );
}
