"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { api, ApiError, type ClassifyOutcome, type PorClasificarRow } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { useHouseholdMembers } from "@/app/lib/hooks/useHousehold";
import { formatStoredAmount } from "@/app/lib/currency";

function formatShortDate(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("T")[0].split("-").map(Number);
  if (!y || !m || !d) return "";
  return new Date(y, m - 1, d).toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "short",
  });
}

interface ChargeRowProps {
  row: PorClasificarRow;
  partnerName: string;
  isPending: boolean;
  note: string | null;
  onClassify: (outcome: ClassifyOutcome) => void;
}

/** One pending shared-card charge with its four-way sort control. Collapses
 *  into an inline "already classified" pill when a second sorter loses the
 *  first-wins race (409 already_classified). */
function ChargeRow({ row, partnerName, isPending, note, onClassify }: ChargeRowProps) {
  const label = row.display_name || row.raw_merchant_name;
  const amountLabel = formatStoredAmount(Number(row.amount), row.currency);
  const dateLabel = formatShortDate(row.transaction_date);

  return (
    <li className="rounded-lg border border-amber-200 bg-amber-50/50 p-3 space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-luka-dark truncate">{label}</span>
        <span className="text-sm font-semibold text-luka-dark shrink-0">{amountLabel}</span>
      </div>
      {dateLabel && <div className="text-xs text-luka-muted">{dateLabel}</div>}

      {note ? (
        <p className="rounded-md border border-purple-200 bg-purple-50 px-2 py-1 text-xs font-medium text-purple-600">
          {note}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            disabled={isPending}
            onClick={() => onClassify("owner_personal")}
            className="rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-medium text-luka-dark hover:bg-slate-50 disabled:opacity-50"
          >
            Mío
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={() => onClassify("partner_personal")}
            className="rounded-md border border-purple-200 bg-purple-50 px-2 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
          >
            De {partnerName}
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={() => onClassify("owner_shared")}
            className="rounded-md border border-amber-300 bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-50"
          >
            Compartido · yo pagué
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={() => onClassify("partner_shared")}
            className="rounded-md border border-amber-300 bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-50"
          >
            Compartido · {partnerName} pagó
          </button>
        </div>
      )}
    </li>
  );
}

/** Shared-card charges pending a four-way sort ("por clasificar"): visible to
 *  both household members, first-to-sort wins. Self-hides when there is
 *  nothing pending or no household. */
export function PorClasificar() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const qc = useQueryClient();
  const [noteId, setNoteId] = useState<string | null>(null);

  const { data: membersData } = useHouseholdMembers();
  const partner = membersData?.members.find((m) => m.user_id !== userId);
  const partnerName = partner?.full_name?.split(" ")[0] || "mi pareja";

  const { data: rows = [] } = useQuery({
    queryKey: ["por-clasificar", householdId],
    queryFn: () => api.getPorClasificar(householdId!),
    enabled: !!householdId,
    staleTime: 30 * 1000,
  });

  const classify = useMutation({
    mutationFn: ({ id, outcome }: { id: string; outcome: ClassifyOutcome }) =>
      api.classifyTransaction(id, outcome),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["por-clasificar"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (err, vars) => {
      // Someone else sorted this charge first — first-wins. Drop it from
      // view instead of leaving dead buttons around.
      if (err instanceof ApiError && err.message === "already_classified") {
        setNoteId(vars.id);
        qc.invalidateQueries({ queryKey: ["por-clasificar"] });
        setTimeout(() => setNoteId((cur) => (cur === vars.id ? null : cur)), 3000);
      }
    },
  });

  if (!householdId || rows.length === 0) return null;

  return (
    <div className="bg-white rounded-xl border border-amber-200 shadow-[var(--shadow-card)] p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
          <Users size={15} />
        </span>
        <h2 className="text-sm font-semibold text-luka-dark">Por clasificar ({rows.length})</h2>
      </div>
      <ul className="space-y-2">
        {rows.map((row) => (
          <ChargeRow
            key={row.id}
            row={row}
            partnerName={partnerName}
            isPending={classify.isPending && classify.variables?.id === row.id}
            note={noteId === row.id ? "ya lo clasificó tu pareja" : null}
            onClassify={(outcome) => classify.mutate({ id: row.id, outcome })}
          />
        ))}
      </ul>
    </div>
  );
}
