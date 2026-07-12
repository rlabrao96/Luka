"use client";
/**
 * CategoryBulkApplyToast — inline confirmation pill that asks the user to
 * apply a just-set category to all other transactions of the same merchant.
 *
 * Shared between RecentTransactions' CategoryCell and PendingBlock's
 * PendingCategoryCell so the UX is identical across surfaces. Mirrors the
 * bulk-rename UX but uses an inline pill (not a checkbox in a dialog) since
 * the category dropdown is itself inline.
 *
 * Lifecycle:
 *   1. Parent fires a category PATCH, then opens this toast with the
 *      anchor txn id, the new category, and the matching count.
 *   2. We auto-dismiss after AUTO_DISMISS_MS if the user doesn't act.
 *   3. "Sí" → calls the bulk endpoint, swaps to a brief success message
 *      that disappears after SUCCESS_MS.
 *   4. "No" → dismiss immediately.
 *
 * Positioning: rendered by the parent in the same flex/relative container as
 * the dropdown trigger, so it sits directly below the pill on desktop.
 * On narrow screens we stretch to full width via `w-full sm:w-auto`.
 */
import { useEffect, useState } from "react";
import { Check, Sparkles, X } from "lucide-react";
import { useUpdateCategoryBulk } from "@/app/lib/hooks/useTransactions";

const AUTO_DISMISS_MS = 8000;
const SUCCESS_MS = 1500;

interface CategoryBulkApplyToastProps {
  transactionId: string;
  category: string | null;
  merchantName: string;
  matchingCount: number;
  onClose: () => void;
  /** "bulk" prompts to apply to existing siblings; "learned" just confirms
   *  that Luka will auto-categorize this merchant going forward (shown when
   *  there are no siblings — the pure teaching moment). */
  mode?: "bulk" | "learned";
}

export function CategoryBulkApplyToast({
  transactionId,
  category,
  merchantName,
  matchingCount,
  onClose,
  mode = "bulk",
}: CategoryBulkApplyToastProps) {
  const [phase, setPhase] = useState<"prompt" | "success">("prompt");
  const [appliedCount, setAppliedCount] = useState(0);
  const bulk = useUpdateCategoryBulk();

  // Auto-dismiss: the learned pill after SUCCESS_MS, the bulk prompt after
  // AUTO_DISMISS_MS unless the user acted.
  useEffect(() => {
    if (mode === "learned") {
      const t = setTimeout(onClose, SUCCESS_MS + 700);
      return () => clearTimeout(t);
    }
    if (phase !== "prompt") return;
    const t = setTimeout(onClose, AUTO_DISMISS_MS);
    return () => clearTimeout(t);
  }, [phase, onClose, mode]);

  // Auto-dismiss the success state after SUCCESS_MS.
  useEffect(() => {
    if (phase !== "success") return;
    const t = setTimeout(onClose, SUCCESS_MS);
    return () => clearTimeout(t);
  }, [phase, onClose]);

  async function handleYes() {
    try {
      const res = await bulk.mutateAsync({ transactionId, category });
      setAppliedCount(res.updated_count);
      setPhase("success");
    } catch {
      onClose();
    }
  }

  // Pure teaching moment: no siblings to bulk-apply, just reinforce that
  // Luka learned this merchant → category mapping for future transactions.
  if (mode === "learned") {
    return (
      <div
        role="status"
        className="mt-1 w-full sm:w-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] text-emerald-700"
      >
        <Sparkles size={12} />
        <span className="truncate max-w-[280px]">
          {`Aprendido: recordaré '${merchantName}' como '${category ?? "Sin categoría"}'.`}
        </span>
      </div>
    );
  }

  if (phase === "success") {
    return (
      <div
        role="status"
        className="mt-1 w-full sm:w-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] text-emerald-700"
      >
        <Check size={12} />
        <span>Actualizamos {appliedCount} transacciones.</span>
      </div>
    );
  }

  const label = category ?? "Sin categoría";
  return (
    <div
      role="status"
      className="mt-1 w-full sm:w-auto inline-flex items-center gap-1.5 rounded-full bg-blue-50 border border-blue-200 px-2.5 py-1 text-[11px] text-slate-700"
    >
      <span className="truncate max-w-[260px]">
        {`Aplicar '${label}' a las otras ${matchingCount} transacciones de '${merchantName}'?`}
      </span>
      <button
        onClick={handleYes}
        disabled={bulk.isPending}
        className="font-semibold text-luka-primary hover:underline disabled:opacity-50"
      >
        Sí
      </button>
      <button
        onClick={onClose}
        disabled={bulk.isPending}
        aria-label="No aplicar"
        className="text-slate-500 hover:text-slate-700 disabled:opacity-50"
      >
        <X size={12} />
      </button>
    </div>
  );
}
