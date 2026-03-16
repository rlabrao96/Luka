import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function KpiCard({ label, value, sublabel, trend, className }: KpiCardProps) {
  return (
    <Card className={cn("bg-white border border-slate-100 shadow-sm", className)}>
      <CardContent className="p-4">
        <p className="text-xs font-medium text-luka-muted uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-luka-dark mt-1">{value}</p>
        {sublabel && (
          <p className={cn(
            "text-xs mt-0.5",
            trend === "up" ? "text-luka-success" :
            trend === "down" ? "text-luka-danger" : "text-luka-muted"
          )}>
            {sublabel}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
