"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, type Transaction } from "@/app/lib/api";

const SPLIT_OPTIONS = [
  { value: "personal", label: "Personal", className: "bg-blue-50 text-blue-600" },
  { value: "shared", label: "Compartido", className: "bg-emerald-50 text-emerald-600" },
  { value: "partner", label: "Pareja", className: "bg-purple-50 text-purple-600" },
];

interface SplitTypeEditorProps {
  txn: Transaction;
  isMobile: boolean;
}

export function SplitTypeEditor({ txn, isMobile }: SplitTypeEditorProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localSplit, setLocalSplit] = useState(txn.split_type ?? "personal");
  const queryClient = useQueryClient();

  const current = SPLIT_OPTIONS.find((o) => o.value === localSplit) ?? SPLIT_OPTIONS[0];

  async function handleSelect(value: string) {
    setOpen(false);
    if (value === localSplit) return;
    setSaving(true);
    setLocalSplit(value);
    try {
      await api.updateTransactionSplitType(txn.id, value);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      setLocalSplit(txn.split_type ?? "personal");
    } finally {
      setSaving(false);
    }
  }

  if (isMobile) {
    return (
      <>
        <button
          onClick={() => setOpen(true)}
          disabled={saving}
          className={cn(
            "text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 cursor-pointer hover:opacity-80",
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
          "flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded cursor-pointer hover:opacity-80",
          current.className,
          saving && "opacity-50"
        )}
      >
        {current.label}
        <ChevronDown size={8} />
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
