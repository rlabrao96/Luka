"use client";

import { Dialog, DialogContent } from "@/components/ui/dialog";

interface CountrySelectorModalProps {
  open: boolean;
  onClose: () => void;
  onSelectChile: () => void;
  onSelectUSA: () => void;
}

export function CountrySelectorModal({
  open,
  onClose,
  onSelectChile,
  onSelectUSA,
}: CountrySelectorModalProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-[320px]">
        <div className="flex flex-col items-center gap-6 py-4">
          <p className="text-sm text-muted-foreground">
            Selecciona el pais de la cuenta
          </p>
          <div className="flex gap-8">
            <button
              onClick={onSelectChile}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-transparent hover:border-luka-primary hover:bg-luka-light transition-all"
            >
              <span className="text-5xl">🇨🇱</span>
            </button>
            <button
              onClick={onSelectUSA}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border-2 border-transparent hover:border-luka-primary hover:bg-luka-light transition-all"
            >
              <span className="text-5xl">🇺🇸</span>
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
