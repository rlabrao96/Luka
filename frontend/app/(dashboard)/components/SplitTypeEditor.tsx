"use client";
import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, ApiError, type Transaction } from "@/app/lib/api";

const SPLIT_OPTIONS = [
  { value: "personal", label: "Personal", className: "bg-blue-50 text-blue-600" },
  { value: "shared", label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
  // For a purchase made by your partner on a card you share (e.g. an
  // authorized-user Amex): drops it out of your totals without hiding yours.
  { value: "partner", label: "De mi pareja", className: "bg-purple-50 text-purple-600" },
];

const PARTNER_CLASS = "bg-purple-50 text-purple-600";

interface SplitTypeEditorProps {
  txn: Transaction;
  isMobile: boolean;
}

export function SplitTypeEditor({ txn, isMobile }: SplitTypeEditorProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localSplit, setLocalSplit] = useState(txn.split_type ?? "personal");
  const queryClient = useQueryClient();

  useEffect(() => {
    setLocalSplit(txn.split_type ?? "personal");
  }, [txn.split_type]);

  const current = SPLIT_OPTIONS.find((o) => o.value === localSplit) ?? SPLIT_OPTIONS[0];

  function invalidate(withNotifications: boolean) {
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    if (withNotifications) {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    }
  }

  async function handleSelect(value: string) {
    setOpen(false);
    if (value === localSplit) return;
    const previous = txn.split_type ?? "personal";
    setSaving(true);
    setLocalSplit(value);
    try {
      if (value === "partner") {
        // Owner tags a partner charge → hand it off (server auto-resolves the
        // couple partner). Fall back to a plain exclude-only "partner" split
        // when there's no partner to hand off to (single-user household).
        try {
          await api.attributeTransaction(txn.id);
          invalidate(true);
        } catch (err) {
          if (err instanceof ApiError && err.message === "no_partner_in_household") {
            await api.updateTransactionSplitType(txn.id, "partner");
            invalidate(false);
          } else if (err instanceof ApiError && err.message === "ambiguous_recipient") {
            // Multiple candidates: a member-picker is out of scope for v1 and
            // couples never reach this. Leave the value unchanged and log.
            console.warn("Attribution ambiguous — recipient picker not implemented", err);
            setLocalSplit(previous);
          } else {
            throw err;
          }
        }
      } else if (txn.attributed_by_me) {
        // Sender switches a handed-off charge away from partner: remove the
        // attribution first (notifies the recipient if acknowledged). Un-tagging
        // reverts the split to personal, so only "shared" needs a follow-up set.
        await api.unattributeTransaction(txn.id);
        if (value === "shared") {
          await api.updateTransactionSplitType(txn.id, "shared");
        }
        invalidate(true);
      } else {
        // Plain personal↔shared (or leaving an exclude-only partner split).
        await api.updateTransactionSplitType(txn.id, value);
        invalidate(false);
      }
    } catch {
      setLocalSplit(previous);
    } finally {
      setSaving(false);
    }
  }

  // Recipient view: the charge lives on the partner's card and was handed off
  // to the caller. It's read-only here — confirm/reject happens from the
  // notification, not this control.
  if (txn.attributed_to_me) {
    return (
      <span
        title="Cargo de la tarjeta compartida de tu pareja"
        className={cn(
          "inline-block text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 text-center cursor-default",
          PARTNER_CLASS,
          isMobile ? "w-[80px]" : "w-[90px]"
        )}
      >
        De mi pareja
      </span>
    );
  }

  if (isMobile) {
    return (
      <>
        <button
          onClick={() => setOpen(true)}
          disabled={saving}
          className={cn(
            "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 cursor-pointer hover:opacity-80 w-[80px] text-center",
            current.className,
            saving && "opacity-50"
          )}
        >
          {current.label}
        </button>
        <BottomSheet open={open} onClose={() => setOpen(false)} title="Tipo de gasto">
          {SPLIT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleSelect(opt.value)}
              className={cn(
                "w-full text-left px-3 py-2.5 text-sm rounded-lg transition-colors",
                localSplit === opt.value
                  ? "font-semibold bg-blue-50 text-luka-primary"
                  : "text-slate-700 hover:bg-slate-50"
              )}
            >
              <span className={cn("inline-block w-2 h-2 rounded-full mr-2", opt.className)} />
              {opt.label}
            </button>
          ))}
        </BottomSheet>
      </>
    );
  }

  // Desktop: inline dropdown
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className={cn(
          "flex items-center justify-between gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80 w-[90px]",
          current.className,
          saving && "opacity-50"
        )}
      >
        <span className="truncate">{current.label}</span>
        <ChevronDown size={8} className="shrink-0" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-[120px]">
            {SPLIT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => handleSelect(opt.value)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-[11px] hover:bg-blue-50 hover:text-luka-primary transition-colors",
                  localSplit === opt.value ? "text-luka-primary font-semibold bg-blue-50" : "text-slate-700"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
