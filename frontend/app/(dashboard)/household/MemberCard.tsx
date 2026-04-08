"use client";

import { useState } from "react";
import { useRemoveMember, useUpdateMemberRole } from "@/app/lib/hooks/useHousehold";

interface Props {
  name: string;
  amount: number;
  percentage: number;
  color: string;
  balance?: number;
  settlementEnabled: boolean;
  currency: string;
  isOwner: boolean;
  memberId?: string;
  memberRole?: string;
  isSelf: boolean;
}

function fmt(n: number, currency: string = "CLP") {
  const isDecimal = currency !== "CLP";
  const displayVal = isDecimal ? Math.abs(n) / 100 : Math.abs(n);
  if (currency === "USD") {
    return `US$${displayVal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Math.round(displayVal).toLocaleString("es-CL")}`;
}

export default function MemberCard({
  name, amount, percentage, color, balance, settlementEnabled,
  currency, isOwner, memberId, memberRole, isSelf,
}: Props) {
  const [showMenu, setShowMenu] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const removeMutation = useRemoveMember();
  const roleMutation = useUpdateMemberRole();

  const initials = name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div
      className="relative flex-shrink-0 w-48 bg-white rounded-xl border border-slate-100 shadow-sm p-4 text-center cursor-pointer"
      onClick={() => isOwner && !isSelf && setShowMenu(!showMenu)}
    >
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center mx-auto mb-2 text-sm font-bold text-white"
        style={{ backgroundColor: color }}
      >
        {initials}
      </div>
      <p className="text-sm font-semibold text-slate-700 truncate">{name}</p>
      <p className="text-xl font-bold text-luka-dark mt-1">{fmt(amount, currency)}</p>
      <p className="text-xs text-slate-400">{percentage}% del total</p>

      {settlementEnabled && balance !== undefined && balance !== 0 && (
        <div className={`mt-2 inline-block px-2 py-0.5 rounded text-xs font-semibold ${
          balance > 0 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"
        }`}>
          {balance > 0 ? `+${fmt(balance, currency)} a favor` : `-${fmt(balance, currency)} debe`}
        </div>
      )}

      {showMenu && isOwner && !isSelf && memberId && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 text-left">
          <button
            onClick={(e) => {
              e.stopPropagation();
              roleMutation.mutate({ memberId, role: memberRole === "owner" ? "member" : "owner" });
              setShowMenu(false);
            }}
            className="w-full px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 text-left"
          >
            {memberRole === "owner" ? "Quitar administrador" : "Hacer administrador"}
          </button>
          {!confirmRemove ? (
            <button
              onClick={(e) => { e.stopPropagation(); setConfirmRemove(true); }}
              className="w-full px-3 py-2 text-xs text-red-600 hover:bg-red-50 text-left"
            >
              Eliminar miembro
            </button>
          ) : (
            <div className="px-3 py-2 space-y-1">
              <p className="text-xs text-red-600">¿Confirmar eliminación?</p>
              <div className="flex gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); removeMutation.mutate(memberId); setShowMenu(false); setConfirmRemove(false); }}
                  className="flex-1 px-2 py-1 text-xs bg-red-600 text-white rounded"
                >Sí</button>
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmRemove(false); }}
                  className="flex-1 px-2 py-1 text-xs bg-slate-100 text-slate-600 rounded"
                >No</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
