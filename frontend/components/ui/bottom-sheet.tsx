"use client";
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { createPortal } from "react-dom";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

const DISMISS_OFFSET_PX = 80;
const DISMISS_VELOCITY_PX_PER_MS = 0.5;
const TAP_MAX_MOVEMENT_PX = 6;
const TAP_MAX_DURATION_MS = 300;
const SNAP_BACK_MS = 180;

export function BottomSheet({ open, onClose, title, children }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);
  const pointerStartY = useRef<number | null>(null);
  const pointerStartTime = useRef<number>(0);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

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

  // Reset drag state whenever the sheet opens.
  useEffect(() => {
    if (open) {
      setDragOffset(0);
      setIsDragging(false);
      pointerStartY.current = null;
    }
  }, [open]);

  if (!open) return null;

  const handlePointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    pointerStartY.current = e.clientY;
    pointerStartTime.current = performance.now();
    setIsDragging(true);
    try {
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      // ignore — capture is best-effort
    }
  };

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (pointerStartY.current === null) return;
    const delta = e.clientY - pointerStartY.current;
    setDragOffset(Math.max(0, delta));
  };

  const finishDrag = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (pointerStartY.current === null) return;
    const offset = Math.max(0, e.clientY - pointerStartY.current);
    const elapsed = performance.now() - pointerStartTime.current;
    const velocity = elapsed > 0 ? offset / elapsed : 0;

    try {
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }
    pointerStartY.current = null;
    setIsDragging(false);

    const isTap = offset < TAP_MAX_MOVEMENT_PX && elapsed < TAP_MAX_DURATION_MS;
    const shouldDismiss = offset > DISMISS_OFFSET_PX || velocity > DISMISS_VELOCITY_PX_PER_MS;

    if (isTap || shouldDismiss) {
      onClose();
      return;
    }
    // Snap back
    setDragOffset(0);
  };

  const handleKeyDownHandle = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClose();
    }
  };

  const sheetTransform = dragOffset > 0 ? `translateY(${dragOffset}px)` : undefined;
  const sheetTransition = isDragging ? "none" : `transform ${SNAP_BACK_MS}ms ease-out`;

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
        style={{
          touchAction: "pan-y",
          transform: sheetTransform,
          transition: sheetTransition,
          willChange: "transform",
        }}
      >
        {/* Drag handle — drag to dismiss, tap to close, large hit area */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Cerrar"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
          onKeyDown={handleKeyDownHandle}
          className="flex justify-center items-center w-full select-none"
          style={{
            touchAction: "none",
            cursor: isDragging ? "grabbing" : "grab",
            height: 36,
          }}
        >
          <div className="w-10 h-1.5 rounded-full bg-slate-300" />
        </div>
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
