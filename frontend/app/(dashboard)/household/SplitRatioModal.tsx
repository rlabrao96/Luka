"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUpdateSplitRatio } from "@/app/lib/hooks/useHousehold";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentRatio: number[];
  memberNames: [string, string];
}

export default function SplitRatioModal({ open, onOpenChange, currentRatio, memberNames }: Props) {
  const [left, setLeft] = useState(currentRatio[0]);
  const mutation = useUpdateSplitRatio();

  useEffect(() => setLeft(currentRatio[0]), [currentRatio]);

  const right = 100 - left;
  const valid = left >= 0 && left <= 100;

  function handleSave() {
    if (!valid) return;
    mutation.mutate([left, right], {
      onSuccess: () => onOpenChange(false),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Configurar split</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <label className="text-xs text-slate-500">{memberNames[0]}</label>
              <Input
                type="number"
                min={0}
                max={100}
                value={left}
                onChange={(e) => setLeft(Number(e.target.value))}
                className="text-center text-lg font-bold"
              />
            </div>
            <span className="text-slate-400 font-medium pt-4">/</span>
            <div className="flex-1">
              <label className="text-xs text-slate-500">{memberNames[1]}</label>
              <div className="flex h-10 items-center justify-center rounded-md border bg-slate-50 text-lg font-bold text-slate-600">
                {right}
              </div>
            </div>
          </div>
          {!valid && <p className="text-xs text-red-500">El valor debe estar entre 0 y 100</p>}
          <Button onClick={handleSave} disabled={!valid || mutation.isPending} className="w-full">
            {mutation.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
