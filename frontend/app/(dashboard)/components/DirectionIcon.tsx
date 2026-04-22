import { TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface DirectionIconProps {
  direction: "outflow" | "inflow";
  /** `hidden` defaults to `"sm"` — icon hidden on `<sm` viewports. Pass `"never"`
   *  to force it visible on every viewport. */
  hidden?: "sm" | "never";
  className?: string;
}

/** 38×38 gradient-backed trend icon. Consolidates the
 *  linear-gradient(135deg, #fef2f2, #fecaca) / #ecfdf5, #d1fae5 pairs that
 *  were pasted across TransactionCard, PairedTransactionCard, and
 *  RecentTransactions. */
export function DirectionIcon({ direction, hidden = "sm", className }: DirectionIconProps) {
  const isOutflow = direction === "outflow";
  return (
    <div
      aria-hidden
      className={cn(
        "w-[38px] h-[38px] rounded-[10px] items-center justify-center shrink-0",
        hidden === "sm" ? "hidden sm:flex" : "flex",
        className,
      )}
      style={{
        background: isOutflow
          ? "linear-gradient(135deg, #fef2f2, #fecaca)"
          : "linear-gradient(135deg, #ecfdf5, #d1fae5)",
      }}
    >
      {isOutflow ? (
        <TrendingDown size={16} className="text-red-400" strokeWidth={2.5} />
      ) : (
        <TrendingUp size={16} className="text-emerald-500" strokeWidth={2.5} />
      )}
    </div>
  );
}
