"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  MoreHorizontal,
  Plus,
  Link2,
  Link as LinkIcon,
  User as UserIcon,
  LogOut,
  Trash2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  api,
  ApiError,
  type TripDetail,
  type TripAttendee,
} from "@/app/lib/api";
import {
  useRemoveAttendee,
  useForceRemoveAttendee,
} from "@/app/lib/hooks/useTrips";
import AddAttendeeDialog from "./AddAttendeeDialog";
import ShareInviteDialog from "./ShareInviteDialog";

interface AsistentesTabProps {
  trip: TripDetail;
}

type ConfirmKind =
  | { kind: "self-leave"; attendee: TripAttendee }
  | { kind: "remove"; attendee: TripAttendee }
  | { kind: "force-remove"; attendee: TripAttendee; reason: string };

function sortAttendees(
  attendees: TripAttendee[],
  creatorUserId: string,
): TripAttendee[] {
  return [...attendees].sort((a, b) => {
    // Active first
    const aActive = a.left_at == null;
    const bActive = b.left_at == null;
    if (aActive !== bActive) return aActive ? -1 : 1;
    // Creator first within group
    const aCreator = a.user_id === creatorUserId;
    const bCreator = b.user_id === creatorUserId;
    if (aCreator !== bCreator) return aCreator ? -1 : 1;
    // Alphabetical
    return a.display_name.localeCompare(b.display_name, "es", {
      sensitivity: "base",
    });
  });
}

export default function AsistentesTab({ trip }: AsistentesTabProps) {
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });

  const [addOpen, setAddOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmKind | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const removeMutation = useRemoveAttendee(trip.id);
  const forceRemoveMutation = useForceRemoveAttendee(trip.id);

  const isCreator = me?.id === trip.creator_user_id;
  const sorted = useMemo(
    () => sortAttendees(trip.attendees, trip.creator_user_id),
    [trip.attendees, trip.creator_user_id],
  );
  const activeCount = trip.attendees.filter((a) => a.left_at == null).length;

  async function handleConfirm() {
    if (!confirm) return;
    setActionError(null);
    try {
      if (confirm.kind === "self-leave" || confirm.kind === "remove") {
        await removeMutation.mutateAsync(confirm.attendee.id);
        setConfirm(null);
      } else {
        await forceRemoveMutation.mutateAsync(confirm.attendee.id);
        setConfirm(null);
      }
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        confirm.kind === "remove"
      ) {
        // Surface unsettled-balance message + offer force remove.
        setConfirm({
          kind: "force-remove",
          attendee: confirm.attendee,
          reason: err.message,
        });
        setActionError(null);
      } else if (err instanceof ApiError) {
        setActionError(err.message);
      } else {
        setActionError("No pudimos completar la acción. Intenta de nuevo.");
      }
    }
  }

  const isPending = removeMutation.isPending || forceRemoveMutation.isPending;

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm font-semibold text-luka-dark">
          {activeCount} {activeCount === 1 ? "asistente activo" : "asistentes activos"}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-luka-primary text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
          >
            <Plus size={14} />
            Agregar
          </button>
          {isCreator && (
            <button
              type="button"
              onClick={() => setShareOpen(true)}
              className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg bg-white text-luka-primary border border-blue-200 text-sm font-semibold hover:bg-blue-50 transition-colors"
            >
              <Link2 size={14} />
              Compartir enlace
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {actionError}
        </p>
      )}

      {/* Member list */}
      <div className="space-y-2">
        {sorted.map((attendee) => (
          <AttendeeRow
            key={attendee.id}
            attendee={attendee}
            isCreator={attendee.user_id === trip.creator_user_id}
            isSelf={!!me && attendee.user_id === me.id}
            callerIsCreator={isCreator}
            onSelfLeave={() =>
              setConfirm({ kind: "self-leave", attendee })
            }
            onRemove={() => setConfirm({ kind: "remove", attendee })}
          />
        ))}
      </div>

      <AddAttendeeDialog
        tripId={trip.id}
        open={addOpen}
        onOpenChange={setAddOpen}
      />
      {isCreator && (
        <ShareInviteDialog
          tripId={trip.id}
          open={shareOpen}
          onOpenChange={setShareOpen}
        />
      )}

      <AlertDialog
        open={confirm != null}
        onOpenChange={(open) => {
          if (!open) {
            setConfirm(null);
            setActionError(null);
          }
        }}
      >
        <AlertDialogContent>
          {confirm && (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>
                  {confirm.kind === "self-leave"
                    ? "¿Salir del viaje?"
                    : confirm.kind === "remove"
                      ? `¿Eliminar a ${confirm.attendee.display_name}?`
                      : `¿Forzar eliminación de ${confirm.attendee.display_name}?`}
                </AlertDialogTitle>
                <AlertDialogDescription>
                  {confirm.kind === "self-leave"
                    ? "Dejarás de aparecer como asistente activo. Tus gastos y aportes previos se mantendrán para el cálculo de saldos."
                    : confirm.kind === "remove"
                      ? "El asistente dejará de aparecer como activo. Solo se permite si no tiene saldo pendiente."
                      : `Saldo pendiente: ${confirm.reason} Se creará un settlement de cierre (write-off) para llevar el saldo a cero. Esta acción no se puede deshacer.`}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={isPending}>
                  Cancelar
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleConfirm}
                  disabled={isPending}
                  className={
                    confirm.kind === "force-remove"
                      ? "bg-red-600 hover:bg-red-700"
                      : undefined
                  }
                >
                  {isPending
                    ? "Procesando..."
                    : confirm.kind === "self-leave"
                      ? "Salir del viaje"
                      : confirm.kind === "remove"
                        ? "Eliminar"
                        : "Forzar eliminación"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

interface AttendeeRowProps {
  attendee: TripAttendee;
  isCreator: boolean;
  isSelf: boolean;
  callerIsCreator: boolean;
  onSelfLeave: () => void;
  onRemove: () => void;
}

function AttendeeRow({
  attendee,
  isCreator,
  isSelf,
  callerIsCreator,
  onSelfLeave,
  onRemove,
}: AttendeeRowProps) {
  const initial = attendee.display_name.trim().charAt(0).toUpperCase() || "?";
  const isLuka = attendee.user_id != null;
  const hasLeft = attendee.left_at != null;

  // Determine if any kebab action is available for this row.
  const canSelfLeave = isSelf && !hasLeft;
  const canRemove = callerIsCreator && !isSelf && !hasLeft;
  const showKebab = canSelfLeave || canRemove;

  return (
    <div
      className={`flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-[var(--shadow-card)] ${
        hasLeft ? "opacity-60" : ""
      }`}
    >
      <span className="shrink-0 w-9 h-9 rounded-full bg-blue-50 text-luka-primary text-xs font-semibold flex items-center justify-center">
        {initial}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <p className="text-sm font-semibold text-luka-dark truncate">
            {attendee.display_name}
          </p>
          {isLuka ? (
            <span
              title="Usuario de Luka"
              className="inline-flex items-center gap-0.5 text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded-full"
            >
              <LinkIcon size={10} />
              Luka
            </span>
          ) : (
            <span
              title="Externo"
              className="inline-flex items-center gap-0.5 text-[10px] font-medium text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded-full"
            >
              <UserIcon size={10} />
              Externo
            </span>
          )}
          {isCreator && (
            <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-full">
              Creador
            </span>
          )}
          {hasLeft && (
            <span className="text-[10px] font-medium text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded-full">
              Salió
            </span>
          )}
        </div>
      </div>
      {showKebab && (
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="Acciones del asistente"
            className="flex items-center justify-center h-7 w-7 rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <MoreHorizontal size={14} />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[180px]">
            {canSelfLeave && (
              <DropdownMenuItem onClick={onSelfLeave}>
                <LogOut />
                Salir del viaje
              </DropdownMenuItem>
            )}
            {canRemove && (
              <DropdownMenuItem variant="destructive" onClick={onRemove}>
                <Trash2 />
                Eliminar
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
