"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { Link2, Check, Copy } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  householdId: string | null;
}

export default function InviteModal({ open, onOpenChange, householdId }: Props) {
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const inviteMutation = useMutation({
    mutationFn: async () => {
      if (!householdId) {
        // Create household and invite atomically
        return await api.createAndInvite();
      }
      return await api.inviteMember(householdId);
    },
    onSuccess: (data) => {
      setInviteLink(`${window.location.origin}/invite/${data.token}`);
    },
  });

  async function handleCopy() {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleClose(open: boolean) {
    if (!open) {
      setInviteLink(null);
      setCopied(false);
    }
    onOpenChange(open);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Invitar miembro</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          {!inviteLink ? (
            <>
              <p className="text-sm text-slate-500">
                Genera un enlace de invitación para compartir con quien quieras agregar al grupo.
              </p>
              <Button
                onClick={() => inviteMutation.mutate()}
                disabled={inviteMutation.isPending}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                <Link2 size={14} className="mr-2" />
                {inviteMutation.isPending ? "Generando..." : "Generar enlace"}
              </Button>
              {inviteMutation.isError && (
                <p className="text-xs text-red-500">Error al generar invitación. Intenta de nuevo.</p>
              )}
            </>
          ) : (
            <>
              <p className="text-sm text-emerald-600 font-medium">
                Enlace creado. Compártelo con el nuevo miembro:
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={inviteLink}
                  readOnly
                  className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 truncate"
                />
                <Button onClick={handleCopy} size="sm" variant="outline">
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                </Button>
              </div>
              <p className="text-xs text-slate-400">El enlace expira en 7 días.</p>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
