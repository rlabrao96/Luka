"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FintocAccount, SelectedFintocAccount } from "@/app/lib/api";

interface Props {
  accounts: FintocAccount[];
  onConfirm: (selected: SelectedFintocAccount[]) => void;
  loading: boolean;
}

const LABEL_OPTIONS: Array<{ value: SelectedFintocAccount["label"]; label: string }> = [
  { value: "personal", label: "Personal" },
  { value: "partner", label: "Pareja" },
  { value: "joint", label: "Compartida" },
];

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  checking_account: "Cuenta Corriente",
  credit_card: "Tarjeta de Crédito",
  saving_account: "Cuenta de Ahorro",
  vista_account: "Cuenta Vista",
};

export function FintocAccountPicker({ accounts, onConfirm, loading }: Props) {
  const [selections, setSelections] = useState<
    Record<string, { checked: boolean; label: SelectedFintocAccount["label"] }>
  >(
    Object.fromEntries(accounts.map((a) => [a.id, { checked: true, label: "personal" }]))
  );

  function toggleAccount(id: string) {
    setSelections((prev) => ({
      ...prev,
      [id]: { ...prev[id], checked: !prev[id].checked },
    }));
  }

  function setLabel(id: string, label: SelectedFintocAccount["label"]) {
    setSelections((prev) => ({
      ...prev,
      [id]: { ...prev[id], label },
    }));
  }

  function handleConfirm() {
    const selected = accounts
      .filter((a) => selections[a.id]?.checked)
      .map((a) => ({ fintoc_account_id: a.id, label: selections[a.id].label }));
    onConfirm(selected);
  }

  const anySelected = Object.values(selections).some((s) => s.checked);

  return (
    <div className="space-y-3">
      <p className="text-sm text-luka-muted">
        Selecciona las cuentas que quieres conectar y etiqueta cada una.
      </p>

      {accounts.map((account) => {
        const sel = selections[account.id];
        return (
          <div
            key={account.id}
            className={`rounded-lg border p-4 transition-colors ${
              sel?.checked ? "border-luka-primary bg-luka-light" : "border-gray-200 bg-white"
            }`}
          >
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={sel?.checked ?? false}
                onChange={() => toggleAccount(account.id)}
                className="mt-1 h-4 w-4 accent-luka-primary"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-luka-dark text-sm">{account.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {ACCOUNT_TYPE_LABELS[account.type] ?? account.type}
                  </Badge>
                  <span className="text-luka-muted text-xs">{account.number}</span>
                </div>

                {sel?.checked && (
                  <div className="flex gap-2 mt-2">
                    {LABEL_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setLabel(account.id, opt.value)}
                        className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                          sel.label === opt.value
                            ? "bg-luka-primary text-white border-luka-primary"
                            : "bg-white text-luka-muted border-gray-200 hover:border-luka-primary"
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <Button
        onClick={handleConfirm}
        disabled={!anySelected || loading}
        className="w-full bg-luka-primary text-white hover:bg-blue-700"
      >
        {loading ? "Conectando..." : "Confirmar cuentas"}
      </Button>
    </div>
  );
}
