"use client";

import { useState } from "react";
import { Link2, Check, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useGenerateInviteLink,
  useRevokeInviteLink,
} from "@/app/lib/hooks/useTrips";
import { ApiError, type InviteLink } from "@/app/lib/api";

interface ShareInviteDialogProps {
  tripId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatExpiry(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function ShareInviteDialog({
  tripId,
  open,
  onOpenChange,
}: ShareInviteDialogProps) {
  const generateMutation = useGenerateInviteLink(tripId);
  const revokeMutation = useRevokeInviteLink(tripId);
  const [link, setLink] = useState<InviteLink | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setLink(null);
    setCopied(false);
    setError(null);
    generateMutation.reset();
    revokeMutation.reset();
  }

  function handleClose(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  async function handleGenerate() {
    setError(null);
    try {
      const result = await generateMutation.mutateAsync();
      setLink(result);
      setCopied(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No pudimos generar el enlace. Intenta de nuevo.");
      }
    }
  }

  async function handleRevoke() {
    setError(null);
    try {
      await revokeMutation.mutateAsync();
      setLink(null);
      setCopied(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No pudimos revocar el enlace. Intenta de nuevo.");
      }
    }
  }

  async function handleCopy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("No pudimos copiar el enlace al portapapeles.");
    }
  }

  const isPending = generateMutation.isPending || revokeMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Compartir invitación</DialogTitle>
        </DialogHeader>

        <div className="space-y-3 pt-1">
          <p className="text-sm text-slate-500">
            Genera un enlace que tus amigos pueden usar para unirse al viaje. El enlace expira en 30 días y se renueva al usarse.
          </p>

          <button
            type="button"
            onClick={handleGenerate}
            disabled={isPending}
            className="w-full inline-flex items-center justify-center gap-1.5 h-11 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            <Link2 size={14} />
            {generateMutation.isPending
              ? "Generando..."
              : link
                ? "Regenerar enlace"
                : "Generar enlace"}
          </button>

          {link && (
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={link.url}
                  readOnly
                  onFocus={(e) => e.currentTarget.select()}
                  className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 truncate"
                />
                <button
                  type="button"
                  onClick={handleCopy}
                  aria-label="Copiar enlace"
                  className="shrink-0 inline-flex items-center justify-center gap-1 px-3 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? "Copiado" : "Copiar"}
                </button>
              </div>
              <p className="text-[11px] text-slate-400">
                Expira el {formatExpiry(link.expires_at)}.
              </p>
              <button
                type="button"
                onClick={handleRevoke}
                disabled={isPending}
                className="w-full px-3 h-9 rounded-lg bg-white text-red-600 border border-red-200 text-xs font-semibold hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                {revokeMutation.isPending ? "Revocando..." : "Revocar enlace"}
              </button>
            </div>
          )}

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
