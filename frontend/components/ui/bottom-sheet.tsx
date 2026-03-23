"use client";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 transition-opacity duration-200"
        onClick={onClose}
      />
      {/* Sheet */}
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-[0_-4px_24px_rgba(0,0,0,0.12)] animate-slide-up max-h-[70vh] flex flex-col"
      >
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-8 h-1 rounded-full bg-slate-300" />
        </div>
        {/* Title */}
        {title && (
          <div className="px-5 pb-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          </div>
        )}
        {/* Content */}
        <div className="overflow-y-auto flex-1 px-5 py-3">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
