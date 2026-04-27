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
    <div className="fixed inset-0 z-50" style={{ touchAction: "none" }}>
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
        style={{ touchAction: "pan-y" }}
      >
        {/* Drag handle (tap to close) */}
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar"
          className="flex justify-center pt-3 pb-2 w-full cursor-pointer"
        >
          <div className="w-10 h-1.5 rounded-full bg-slate-300" />
        </button>
        {/* Title */}
        {title && (
          <div className="px-6 pb-3 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          </div>
        )}
        {/* Content */}
        <div className="overflow-y-auto flex-1 px-6 py-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
