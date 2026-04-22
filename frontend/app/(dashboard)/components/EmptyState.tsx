import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  message: string;
  /** Height of the block. Defaults to 200. Dashboard cards used 200; the
   *  SpendingChart variant used 140. Pass the number of pixels, not a class. */
  height?: number;
}

/** Small placeholder used across dashboard cards and compact lists when a
 *  query returns zero rows. Consolidates the circular-icon + muted-text
 *  block that was pasted in 4 sites. */
export function EmptyState({ icon: Icon, message, height = 200 }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2"
      style={{ height }}
    >
      <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
        <Icon size={18} className="text-slate-400" />
      </div>
      <p className="text-xs text-luka-muted">{message}</p>
    </div>
  );
}
