"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  useUpdateSplitRatio,
  useUpdateSettlementEnabled,
} from "@/app/lib/hooks/useHousehold";
import type { HouseholdMember } from "@/app/lib/api";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentRatio: number[];
  members: HouseholdMember[];
  settlementEnabled: boolean;
}

export default function RatioSettingsModal({
  open, onOpenChange, currentRatio, members, settlementEnabled,
}: Props) {
  const [ratios, setRatios] = useState<number[]>(currentRatio);
  const [settlement, setSettlement] = useState(settlementEnabled);
  const ratioMutation = useUpdateSplitRatio();
  const settlementMutation = useUpdateSettlementEnabled();

  useEffect(() => {
    setRatios(currentRatio);
    setSettlement(settlementEnabled);
  }, [currentRatio, settlementEnabled]);

  const total = ratios.reduce((s, r) => s + r, 0);
  const valid = total === 100 && ratios.every((r) => r >= 0);

  function handleEqualSplit() {
    const n = members.length;
    const base = Math.floor(100 / n);
    const remainder = 100 % n;
    setRatios(members.map((_, i) => base + (i < remainder ? 1 : 0)));
  }

  function handleSave() {
    if (!valid) return;
    const promises: Promise<unknown>[] = [];
    if (JSON.stringify(ratios) !== JSON.stringify(currentRatio)) {
      promises.push(ratioMutation.mutateAsync(ratios));
    }
    if (settlement !== settlementEnabled) {
      promises.push(settlementMutation.mutateAsync(settlement));
    }
    Promise.all(promises).then(() => onOpenChange(false));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Configurar ratios</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div className="space-y-3">
            {members.map((member, i) => (
              <div key={member.user_id} className="flex items-center gap-3">
                <label className="text-sm text-slate-600 flex-1 truncate">
                  {member.full_name.split(" ")[0]}
                </label>
                <div className="flex items-center gap-1">
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={ratios[i] ?? 0}
                    onChange={(e) => {
                      const next = [...ratios];
                      next[i] = Number(e.target.value);
                      setRatios(next);
                    }}
                    className="w-20 text-center text-lg font-bold"
                  />
                  <span className="text-sm text-slate-400">%</span>
                </div>
              </div>
            ))}
          </div>
          <div className={`text-xs text-center ${valid ? "text-emerald-600" : "text-red-500"}`}>
            Total: {total}% {!valid && "(debe sumar 100%)"}
          </div>
          <Button variant="outline" onClick={handleEqualSplit} className="w-full" size="sm">
            Repartir equitativamente
          </Button>
          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <label className="text-sm text-slate-600">Activar liquidación</label>
            <Switch checked={settlement} onCheckedChange={setSettlement} />
          </div>
          <Button
            onClick={handleSave}
            disabled={!valid || ratioMutation.isPending || settlementMutation.isPending}
            className="w-full"
          >
            {ratioMutation.isPending || settlementMutation.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
