"use client";

import Script from "next/script";
import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLukaStore } from "@/app/lib/store";
import { api, type BankAccountRow } from "@/app/lib/api";

// ── Label helpers ──────────────────────────────────────────

const ACCOUNT_TYPE_LABEL: Record<string, string> = {
  personal: "Personal",
  partner: "Pareja",
  joint: "Compartida",
};

const ACCOUNT_TYPE_COLOR: Record<string, string> = {
  personal: "bg-blue-100 text-blue-700",
  partner: "bg-purple-100 text-purple-700",
  joint: "bg-emerald-100 text-emerald-700",
};

const ACCOUNT_KIND_LABEL: Record<string, string> = {
  checking_account: "Cuenta Corriente",
  credit_card: "Tarjeta de Crédito",
  savings_account: "Cuenta de Ahorro",
  vista: "Cuenta Vista",
};

function formatLastSync(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 2) return "hace un momento";
  if (diff < 60) return `hace ${diff} min`;
  const hours = Math.floor(diff / 60);
  if (hours < 24) return `hace ${hours}h`;
  return `hace ${Math.floor(hours / 24)}d`;
}

function bankLabel(bankName: string): string {
  if (!bankName) return "Banco desconocido";
  // capitalize each word, trim "fintoc" fallback
  if (bankName.toLowerCase() === "fintoc") return "Banco (Fintoc)";
  return bankName
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

// ── Account card ───────────────────────────────────────────

function AccountCard({
  account,
  currentUserId,
  householdId,
  onDeleted,
  onUpdated,
}: {
  account: BankAccountRow;
  currentUserId: string | null;
  householdId: string | null;
  onDeleted: (id: string) => void;
  onUpdated: (id: string, patch: { account_type?: string; is_active?: boolean }) => void;
}) {
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showNumber, setShowNumber] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editType, setEditType] = useState<"personal" | "partner" | "joint">(account.account_type as "personal" | "partner" | "joint");
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const isOwn = account.user_id === currentUserId;
  const typeLabel = ACCOUNT_TYPE_LABEL[account.account_type] ?? account.account_type;
  const typeColor = account.is_active
    ? (ACCOUNT_TYPE_COLOR[account.account_type] ?? "bg-gray-100 text-gray-700")
    : "bg-gray-100 text-gray-400";
  const kindLabel = account.account_kind
    ? (ACCOUNT_KIND_LABEL[account.account_kind] ?? account.account_kind)
    : null;
  const isFirstImport = account.import_status === "importing" && !account.last_synced_at;
  const isFirstImportFailed = account.import_status === "failed" && !account.last_synced_at;

  const last4 = account.account_number ? account.account_number.slice(-4) : null;
  const maskedNumber = last4 ? `•••• ${last4}` : null;
  const fullNumber = account.account_number ?? null;

  async function handleToggle() {
    if (!householdId || toggling) return;
    setToggling(true);
    setInlineError(null);
    const newActive = !account.is_active;
    onUpdated(account.id, { is_active: newActive }); // optimistic
    try {
      await api.updateBankAccount(account.id, householdId, { is_active: newActive });
    } catch (e: unknown) {
      onUpdated(account.id, { is_active: account.is_active }); // revert
      const msg =
        e instanceof Error && e.message.includes("409")
          ? "Espera a que termine la sincronización antes de desactivar."
          : "No se pudo guardar. Intenta de nuevo.";
      setInlineError(msg);
    } finally {
      setToggling(false);
    }
  }

  async function handleSaveType() {
    if (!householdId) return;
    setSaving(true);
    setInlineError(null);
    onUpdated(account.id, { account_type: editType }); // optimistic
    try {
      await api.updateBankAccount(account.id, householdId, { account_type: editType });
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } catch {
      onUpdated(account.id, { account_type: account.account_type }); // revert
      setInlineError("No se pudo guardar. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!householdId) return;
    setDeleting(true);
    try {
      await api.deleteBankAccount(account.id, householdId);
      onDeleted(account.id);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  return (
    <div className={`rounded-xl border bg-white shadow-sm transition-opacity ${account.is_active ? "" : "opacity-60"}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-luka-dark text-sm">{bankLabel(account.bank_name)}</span>
          {account.currency && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${account.is_active ? "bg-slate-100 text-slate-600" : "bg-gray-100 text-gray-400"}`}>
              {account.currency}
            </span>
          )}
          {kindLabel && (
            <span className="text-xs text-luka-muted">{kindLabel}</span>
          )}
          {!isOwn && (
            <span className="text-xs text-purple-600 font-medium">· Pareja</span>
          )}
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>
          {typeLabel}
        </span>
      </div>

      {/* Body */}
      <div className="px-4 pb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {maskedNumber && (
          <span className="flex items-center gap-1 text-xs text-luka-muted">
            {showNumber ? fullNumber : maskedNumber}
            <button
              onClick={() => setShowNumber((v) => !v)}
              className="text-luka-muted hover:text-luka-dark"
              title={showNumber ? "Ocultar" : "Mostrar"}
            >
              {showNumber ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              )}
            </button>
          </span>
        )}
        {account.last_synced_at && (
          <span className="text-xs text-slate-400">Última sync: {formatLastSync(account.last_synced_at)}</span>
        )}
        {isFirstImport && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse inline-block" />
            Sincronizando...
          </span>
        )}
        {isFirstImportFailed && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
            Error al sincronizar
          </span>
        )}
      </div>

      {/* Footer — only for own accounts */}
      {isOwn && (
        <div className="flex items-center justify-between px-4 pb-3 pt-1 border-t border-gray-50 mt-1">
          {/* Active toggle */}
          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`flex items-center gap-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${account.is_active ? "text-luka-primary" : "text-luka-muted"}`}
          >
            <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${account.is_active ? "bg-luka-primary" : "bg-gray-300"}`}>
              <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${account.is_active ? "translate-x-4" : "translate-x-1"}`} />
            </span>
            {account.is_active ? "Activa" : "Inactiva"}
          </button>

          {/* Edit + Delete */}
          <div className="flex items-center gap-3">
            {!editing && (
              <button
                onClick={() => { setEditing(true); setEditType(account.account_type); setInlineError(null); }}
                className="text-xs text-luka-primary hover:text-blue-700 font-medium"
              >
                Editar tipo
              </button>
            )}
            {!confirmDelete && (
              <button onClick={() => setConfirmDelete(true)} className="text-xs text-red-400 hover:text-red-600">
                Desconectar
              </button>
            )}
            {confirmDelete && (
              <span className="flex items-center gap-1.5">
                <span className="text-xs text-luka-muted">¿Seguro?</span>
                <button onClick={handleDelete} disabled={deleting} className="text-xs text-red-500 font-medium hover:text-red-700 disabled:opacity-50">
                  {deleting ? "..." : "Sí"}
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-xs text-luka-muted hover:text-luka-dark">No</button>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Edit mode (inline expand) */}
      {editing && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 space-y-3">
          <p className="text-xs text-luka-muted font-medium">Tipo de cuenta</p>
          <div className="flex gap-2">
            {(["personal", "partner", "joint"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setEditType(t)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  editType === t
                    ? "bg-luka-primary text-white border-luka-primary"
                    : "bg-white text-luka-muted border-gray-200 hover:border-luka-primary"
                }`}
              >
                {ACCOUNT_TYPE_LABEL[t]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveType}
              disabled={saving}
              className="text-xs px-4 py-1.5 rounded-md bg-luka-primary text-white font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
            <button
              onClick={() => { setEditing(false); setInlineError(null); }}
              className="text-xs text-luka-muted hover:text-luka-dark"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Inline error */}
      {inlineError && (
        <p className="px-4 pb-3 text-xs text-red-500">{inlineError}</p>
      )}
    </div>
  );
}

// ── Connect bank section ───────────────────────────────────

function ConnectBankSection() {
  const householdId = useLukaStore((s) => s.householdId);
  const userId = useLukaStore((s) => s.userId);
  const queryClient = useQueryClient();

  const [scriptReady, setScriptReady] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Patch Fintoc SDK v1 postMessage DataCloneError bug
  useEffect(() => {
    const proto = Window.prototype;
    const orig = proto.postMessage;
    proto.postMessage = function (this: Window, msg: unknown, ...args: unknown[]) {
      try {
        return orig.apply(this, [msg, ...args] as Parameters<typeof orig>);
      } catch (e) {
        if (e instanceof DOMException && e.name === "DataCloneError") return;
        throw e;
      }
    };
    return () => {
      proto.postMessage = orig;
    };
  }, []);


  function openWidget() {
    if (!window.Fintoc) {
      setMessage("El widget de Fintoc no está disponible. Recarga la página.");
      return;
    }
    if (!householdId || !userId) {
      setMessage("Aún cargando tu sesión — espera un momento e intenta de nuevo.");
      return;
    }
    setMessage(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const webhookUrl = `${apiUrl}/bank-accounts/webhooks/fintoc-link?household_id=${householdId}&user_id=${userId}`;

    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      holderType: "individual",
      webhookUrl,
      onSuccess: () => {
        setMessage("¡Cuenta conectada! El historial se importa en segundo plano.");
        queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
      },
      onExit: () => setMessage("Conexión cancelada."),
      onEvent: (eventName: string) => {
        if (eventName === "closed") setMessage("Conexión cancelada.");
      },
    });
    widget.open();
  }

  const [pollStart] = useState(() => Date.now());

  // Any account doing its first-ever import?
  const hasActiveFirstImport = (accounts: BankAccountRow[] | undefined) =>
    !!accounts?.some((a) => a.import_status === "importing" && !a.last_synced_at);

  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 0,
    refetchInterval: (query) => {
      const data = query.state.data;
      const elapsed = Date.now() - pollStart;
      if (elapsed > 10 * 60 * 1000) return false;        // hard stop at 10 min
      if (hasActiveFirstImport(data)) return 5_000;       // poll every 5s while importing
      return false;                                        // no active import — stop
    },
  });

  return (
    <div className="w-full">
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-luka-dark">Cuentas bancarias</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={openWidget}
            disabled={!scriptReady || !householdId}
            className="text-luka-primary border-luka-primary hover:bg-luka-light"
          >
            + Agregar cuenta
          </Button>
        </CardHeader>
        <CardContent>
          {message && <p className="text-sm text-luka-muted mb-3">{message}</p>}

          {loadingAccounts && (
            <p className="text-sm text-luka-muted">Cargando cuentas...</p>
          )}

          {!loadingAccounts && (!accounts || accounts.length === 0) && (
            <p className="text-sm text-luka-muted">
              Conecta tus cuentas para importar transacciones automáticamente.
            </p>
          )}

          {!loadingAccounts && accounts && accounts.length > 0 && (
            <div className="space-y-3">
              {accounts.map((account) => (
                <AccountCard
                  key={account.id}
                  account={account}
                  currentUserId={userId}
                  householdId={householdId}
                  onDeleted={(id) => {
                    queryClient.setQueryData<BankAccountRow[]>(
                      ["bank-accounts", householdId],
                      (prev) => prev?.filter((a) => a.id !== id) ?? []
                    );
                    queryClient.invalidateQueries({ queryKey: ["transactions"] });
                  }}
                  onUpdated={(id, patch) => {
                    queryClient.setQueryData<BankAccountRow[]>(
                      ["bank-accounts", householdId],
                      (prev) =>
                        prev?.map((a) =>
                          a.id === id ? { ...a, ...patch } as BankAccountRow : a
                        ) ?? []
                    );
                  }}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Exported section ───────────────────────────────────────

export function BankAccountsSection({ householdId }: { householdId: string | null }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="px-5 pt-5 pb-2">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">
          Cuentas Bancarias
        </h3>
      </div>
      <div className="px-5 pb-5">
        <ConnectBankSection />
      </div>
    </div>
  );
}
