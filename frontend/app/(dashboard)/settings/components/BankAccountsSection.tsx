"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLukaStore } from "@/app/lib/store";
import { api, type BankAccountRow, type BankConnection } from "@/app/lib/api";
import { useBankConnections, useSyncStatus } from "@/app/lib/hooks/useSyncStatus";

/* ═══════════════════════════════════════════════════════════════════
   Bank registry (shared with onboarding)
   ═══════════════════════════════════════════════════════════════════ */

interface BankDef {
  code: string;
  name: string;
  color: string;
  initials: string;
  available: boolean;
  requires2FA: boolean;
}

const BANKS: BankDef[] = [
  { code: "bchile",     name: "Banco de Chile",  color: "#003B71", initials: "BC",  available: true,  requires2FA: false },
  { code: "bestado",    name: "Banco Estado",     color: "#D52B1E", initials: "BE",  available: false, requires2FA: true },
  { code: "bci",        name: "BCI",              color: "#E63027", initials: "BCI", available: false, requires2FA: true },
  { code: "santander",  name: "Banco Santander",  color: "#EC0000", initials: "S",   available: false, requires2FA: true },
  { code: "itau",       name: "Banco Itaú",       color: "#FF6600", initials: "itú", available: false, requires2FA: true },
  { code: "scotiabank", name: "Scotiabank",       color: "#EC111A", initials: "Sb",  available: false, requires2FA: true },
  { code: "bice",       name: "Banco BICE",       color: "#1B3A6B", initials: "BI",  available: false, requires2FA: true },
  { code: "falabella",  name: "Banco Falabella",  color: "#8BC540", initials: "BF",  available: true,  requires2FA: false },
  { code: "edwards",    name: "Banco Edwards",    color: "#00529B", initials: "Ed",  available: false, requires2FA: true },
];

function BankIcon({ bank, size = 36 }: { bank: BankDef; size?: number }) {
  const fontSize = size < 32 ? 10 : bank.initials.length > 2 ? 10 : 13;
  return (
    <div
      className="rounded-lg flex items-center justify-center font-bold flex-shrink-0 shadow-sm"
      style={{ width: size, height: size, backgroundColor: bank.color, color: "#fff", fontSize, letterSpacing: "-0.02em" }}
    >
      {bank.initials}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Label helpers
   ═══════════════════════════════════════════════════════════════════ */

const ACCOUNT_TYPE_LABEL: Record<string, string> = { personal: "Personal", partner: "Personal", joint: "Hogar" };
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

function syncStatusDot(status: string | null): { color: string; label: string } {
  if (!status) return { color: "bg-gray-300", label: "Pendiente" };
  if (status === "success") return { color: "bg-green-500", label: "Sincronizado" };
  if (status.startsWith("failed")) return { color: "bg-red-500", label: "Error" };
  if (status === "in_progress" || status === "awaiting_2fa") return { color: "bg-yellow-400", label: "Sincronizando..." };
  return { color: "bg-gray-300", label: "Pendiente" };
}

/* ═══════════════════════════════════════════════════════════════════
   Bank connection card (Luka Connect)
   ═══════════════════════════════════════════════════════════════════ */

function BankConnectionCard({ connection }: { connection: BankConnection }) {
  const queryClient = useQueryClient();
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const { data: syncStatus } = useSyncStatus(connection.bank_code);
  const bank = BANKS.find((b) => b.code === connection.bank_code);

  const status = syncStatus?.last_sync_status ?? connection.last_sync_status;
  const lastSyncAt = syncStatus?.last_sync_at ?? connection.last_sync_at;
  const { color, label } = syncStatusDot(status);

  const { mutate: triggerSync, isPending: syncing } = useMutation({
    mutationFn: () => api.manualSync(connection.bank_code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync-status", connection.bank_code] });
      queryClient.invalidateQueries({ queryKey: ["bank-connections"] });
    },
  });

  const { mutate: disconnect, isPending: disconnecting } = useMutation({
    mutationFn: () => api.disconnectBank(connection.bank_code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bank-connections"] }),
  });

  return (
    <div className="rounded-xl border bg-white shadow-sm">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-3">
          {bank && <BankIcon bank={bank} />}
          <div>
            <span className="font-semibold text-luka-dark text-sm">{bank?.name ?? connection.bank_code}</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
              <span className="text-xs text-luka-muted">{label}</span>
              {lastSyncAt && <span className="text-xs text-slate-400 ml-2">{formatLastSync(lastSyncAt)}</span>}
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between px-4 pb-3 pt-1 border-t border-gray-50 mt-1">
        <Button
          size="sm" variant="outline"
          onClick={() => triggerSync()}
          disabled={syncing || status === "in_progress" || status === "awaiting_2fa"}
          className="text-xs text-luka-primary border-luka-primary hover:bg-luka-light h-7 px-3"
        >
          {syncing ? "Iniciando..." : "Sincronizar ahora"}
        </Button>
        <div className="flex items-center gap-2">
          {!confirmDisconnect ? (
            <Button
              size="sm" variant="outline"
              onClick={() => setConfirmDisconnect(true)}
              className="text-xs text-red-500 border-red-200 !bg-red-50 hover:!bg-red-100 hover:text-red-600 hover:border-red-300 h-7 px-3"
            >
              Desconectar
            </Button>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-luka-muted mr-1">¿Seguro?</span>
              <Button
                size="sm" variant="outline"
                onClick={() => disconnect()}
                disabled={disconnecting}
                className="text-xs text-red-600 border-red-300 !bg-red-50 hover:!bg-red-100 h-7 px-3 disabled:opacity-50"
              >
                {disconnecting ? "..." : "Sí, desconectar"}
              </Button>
              <Button
                size="sm" variant="outline"
                onClick={() => setConfirmDisconnect(false)}
                className="text-xs text-slate-500 border-slate-200 hover:bg-slate-50 h-7 px-3"
              >
                Cancelar
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Bank account card (email-linked accounts)
   ═══════════════════════════════════════════════════════════════════ */

function AccountCard({ account, currentUserId, householdId, onDeleted, onUpdated }: {
  account: BankAccountRow; currentUserId: string | null; householdId: string | null;
  onDeleted: (id: string) => void;
  onUpdated: (id: string, patch: { account_type?: string; is_active?: boolean }) => void;
}) {
  const queryClient = useQueryClient();
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showNumber, setShowNumber] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toggling, setToggling] = useState(false);

  const isOwn = account.user_id === currentUserId;
  const typeLabel = ACCOUNT_TYPE_LABEL[account.account_type] ?? account.account_type;
  const typeColor = account.is_active ? (ACCOUNT_TYPE_COLOR[account.account_type] ?? "bg-gray-100 text-gray-700") : "bg-gray-100 text-gray-400";
  const kindLabel = account.account_kind ? (ACCOUNT_KIND_LABEL[account.account_kind] ?? account.account_kind) : null;
  const last4 = account.account_number ? account.account_number.slice(-4) : null;

  async function handleToggle() {
    if (!householdId || toggling) return;
    setToggling(true);
    const newActive = !account.is_active;
    onUpdated(account.id, { is_active: newActive });
    try { await api.updateBankAccount(account.id, householdId, { is_active: newActive }); }
    catch { onUpdated(account.id, { is_active: account.is_active }); }
    finally { setToggling(false); }
  }

  async function handleTypeChange(newType: "personal" | "joint") {
    if (!householdId || saving || newType === account.account_type) return;
    setSaving(true);
    onUpdated(account.id, { account_type: newType });
    try {
      await api.updateBankAccount(account.id, householdId, { account_type: newType });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
    } catch { onUpdated(account.id, { account_type: account.account_type }); }
    finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!householdId) return;
    setDeleting(true);
    try { await api.deleteBankAccount(account.id, householdId); onDeleted(account.id); }
    finally { setDeleting(false); setConfirmDelete(false); }
  }

  return (
    <div className={`rounded-xl border bg-white shadow-sm transition-opacity ${account.is_active ? "" : "opacity-60"}`}>
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-luka-dark text-sm">{account.bank_name}</span>
          {account.currency && <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">{account.currency}</span>}
          {kindLabel && <span className="text-xs text-luka-muted">{kindLabel}</span>}
        </div>
        {isOwn ? (
          <select
            value={account.account_type}
            onChange={(e) => handleTypeChange(e.target.value as "personal" | "joint")}
            disabled={saving}
            className={`text-xs font-medium px-2 py-1 rounded-full border appearance-none cursor-pointer pr-6 disabled:opacity-50 ${
              account.account_type === "joint"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-blue-50 text-blue-700 border-blue-200"
            }`}
            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`, backgroundRepeat: "no-repeat", backgroundPosition: "right 6px center" }}
          >
            <option value="personal">Personal</option>
            <option value="joint">Compartida</option>
          </select>
        ) : (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>{typeLabel}</span>
        )}
      </div>
      <div className="px-4 pb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        {last4 && (
          <span className="flex items-center gap-1 text-xs text-luka-muted">
            {showNumber ? account.account_number : `•••• ${last4}`}
            <button onClick={() => setShowNumber((v) => !v)} className="text-luka-muted hover:text-luka-dark">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {showNumber ? <><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/></> : <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>}
              </svg>
            </button>
          </span>
        )}
      </div>
      {isOwn && (
        <div className="flex items-center justify-between px-4 pb-3 pt-1 border-t border-gray-50 mt-1">
          <button onClick={handleToggle} disabled={toggling} className={`flex items-center gap-1.5 text-xs font-medium ${account.is_active ? "text-luka-primary" : "text-luka-muted"}`}>
            <span className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${account.is_active ? "bg-luka-primary" : "bg-gray-300"}`}>
              <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${account.is_active ? "translate-x-4" : "translate-x-1"}`} />
            </span>
            {account.is_active ? "Activa" : "Inactiva"}
          </button>
          <div className="flex items-center gap-3">
            {!confirmDelete ? (
              <button onClick={() => setConfirmDelete(true)} className="text-xs text-red-400 hover:text-red-600">Eliminar</button>
            ) : (
              <span className="flex items-center gap-1.5">
                <span className="text-xs text-luka-muted">¿Seguro?</span>
                <button onClick={handleDelete} disabled={deleting} className="text-xs text-red-500 font-medium">{deleting ? "..." : "Sí"}</button>
                <button onClick={() => setConfirmDelete(false)} className="text-xs text-luka-muted">No</button>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Connect Bank Modal (Luka Connect flow — for settings)
   ═══════════════════════════════════════════════════════════════════ */

type ModalStep = "select" | "credentials" | "connecting" | "success";

function ConnectBankModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<ModalStep>("select");
  const [selectedBank, setSelectedBank] = useState<BankDef | null>(null);
  const [rut, setRut] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
  };

  const waitForSessionStart = (bankCode: string) => {
    setStep("connecting");
    setError(null);

    // Poll every 3s for up to 60s to confirm session started
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getSyncStatus(bankCode);
        const s = status.last_sync_status;
        if (s === "in_progress" || s === "awaiting_2fa" || s === "success") {
          stopPolling();
          setStep("success");
        } else if (s?.startsWith("failed")) {
          stopPolling();
          setError(s === "failed_login" ? "Credenciales incorrectas. Verifica tu RUT y clave." : "Error al conectar con el banco.");
          setStep("credentials");
          setPassword("");
        }
      } catch { /* ignore */ }
    }, 3000);

    // Timeout after 60s
    timeoutRef.current = setTimeout(() => {
      stopPolling();
      // If still connecting after 60s, assume it's working (scrape is slow)
      setStep("success");
    }, 60000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rut.trim() || !password.trim() || !selectedBank) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await api.connectBank({ bank_code: selectedBank.code, rut: rut.trim(), password });
      // API responded "started" — now poll to confirm session actually started
      waitForSessionStart(selectedBank.code);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al conectar");
    } finally { setIsSubmitting(false); }
  };

  const handleSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["bank-connections"] });
    queryClient.invalidateQueries({ queryKey: ["transactions"] });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="font-semibold text-luka-dark">
            {step === "select" && "Selecciona tu banco"}
            {step === "credentials" && selectedBank?.name}
            {step === "connecting" && `Conectando con ${selectedBank?.name}`}
            {step === "success" && "Sesión iniciada"}
          </h3>
          <button onClick={onClose} className="text-luka-muted hover:text-luka-dark">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M15 5L5 15M5 5l10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
          </button>
        </div>

        <div className="p-6">
          {/* Step 1: Bank selector */}
          {step === "select" && (
            <div className="space-y-1">
              {BANKS.map((bank) => (
                <button
                  key={bank.code} type="button" disabled={!bank.available}
                  onClick={() => { if (bank.available) { setSelectedBank(bank); setStep("credentials"); } }}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all ${bank.available ? "hover:bg-slate-50 cursor-pointer" : "opacity-40 cursor-not-allowed"}`}
                >
                  <BankIcon bank={bank} />
                  <span className="flex-1 text-left text-sm font-medium text-luka-dark">{bank.name}</span>
                  {bank.available ? (
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="text-luka-muted"><path d="M7.5 5L12.5 10L7.5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  ) : (
                    <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Pronto</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Step 2: Credentials */}
          {step === "credentials" && selectedBank && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="flex items-center gap-3 mb-4">
                <BankIcon bank={selectedBank} size={44} />
                <div>
                  <p className="font-semibold text-luka-dark text-sm">{selectedBank.name}</p>
                  <p className="text-xs text-luka-muted">Ingresa tus credenciales de banca en línea</p>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-luka-dark">RUT</label>
                <Input placeholder="12.345.678-9" value={rut} onChange={(e) => { setRut(e.target.value); setError(null); }} disabled={isSubmitting} className="rounded-xl" autoComplete="username" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-luka-dark">Clave Internet</label>
                <Input type="password" placeholder="Tu clave de acceso" value={password} onChange={(e) => { setPassword(e.target.value); setError(null); }} disabled={isSubmitting} className="rounded-xl" autoComplete="current-password" />
              </div>
              {error && <p className="text-sm text-red-500 text-center">{error}</p>}
              <Button type="submit" disabled={isSubmitting || !rut.trim() || !password.trim()} className="w-full bg-luka-primary text-white hover:bg-luka-primary-dark rounded-xl h-11">
                {isSubmitting ? "Conectando..." : "Conectar"}
              </Button>
              <div className="flex items-center justify-center gap-1.5 text-luka-muted">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></svg>
                <span className="text-[11px]">Encriptado con AES-256</span>
              </div>
              <button type="button" onClick={() => setStep("select")} className="w-full text-xs text-luka-muted hover:text-luka-dark text-center">Volver</button>
            </form>
          )}

          {/* Step 3: Connecting — waiting for session confirmation */}
          {step === "connecting" && selectedBank && (
            <div className="space-y-5 text-center">
              <div className="flex justify-center py-3">
                <div className="relative">
                  <div className="w-16 h-16 rounded-full border-[3px] border-slate-100 border-t-luka-primary animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center"><BankIcon bank={selectedBank} size={32} /></div>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-luka-dark">Iniciando sesión en {selectedBank.name}...</p>
                <p className="text-xs text-luka-muted mt-1">Esto puede tomar unos segundos.</p>
              </div>
            </div>
          )}

          {/* Step 4: Success — scrape started in background */}
          {step === "success" && selectedBank && (
            <div className="space-y-5 text-center">
              <div className="flex justify-center py-4">
                <div className="w-16 h-16 rounded-full bg-green-50 flex items-center justify-center">
                  <svg className="w-8 h-8 text-luka-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold text-luka-dark">Sesión iniciada correctamente</p>
                <p className="text-sm text-luka-muted mt-2">
                  Estamos extrayendo tus movimientos históricos. Esto puede tomar alrededor de 5 minutos.
                </p>
                <p className="text-xs text-luka-muted mt-1">
                  Tus transacciones aparecerán automáticamente en el dashboard.
                </p>
              </div>
              <Button onClick={handleSuccess} className="w-full bg-luka-primary text-white rounded-xl h-11">
                Volver a configuración
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Detected account card (Luka Connect — auto-created accounts)
   ═══════════════════════════════════════════════════════════════════ */

function DetectedAccountCard({
  account,
  householdId,
}: {
  account: BankAccountRow;
  householdId: string;
}) {
  const queryClient = useQueryClient();
  const [updating, setUpdating] = useState(false);

  const kindLabels: Record<string, string> = {
    checking_account: "Cta. Corriente",
    credit_card: "Tarjeta de Crédito",
    line_of_credit: "Línea de Crédito",
    savings_account: "Cuenta Ahorro",
  };

  async function toggleActive() {
    setUpdating(true);
    try {
      await api.updateBankAccount(account.id, householdId, {
        is_active: !account.is_active,
      });
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
    } finally {
      setUpdating(false);
    }
  }

  async function changeType(newType: "personal" | "joint") {
    if (newType === account.account_type) return;
    setUpdating(true);
    try {
      await api.updateBankAccount(account.id, householdId, {
        account_type: newType,
      });
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", householdId] });
      await queryClient.invalidateQueries({ queryKey: ["transactions"] });
    } finally {
      setUpdating(false);
    }
  }

  const formatBalance = (val: number | null, currency: string | null) => {
    if (val === null) return "—";
    const abs = Math.abs(Math.round(val));
    const formatted =
      currency === "USD"
        ? `US$${abs.toLocaleString("en-US")}`
        : `$${abs.toLocaleString("es-CL")}`;
    return val < 0 ? `(${formatted})` : formatted;
  };

  return (
    <div
      className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
        account.is_active
          ? "bg-white border-slate-100"
          : "bg-slate-50 border-slate-100 opacity-60"
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">
            {account.account_name ?? account.bank_name}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] font-medium text-slate-400">
              {kindLabels[account.account_kind ?? ""] ?? account.account_kind}
            </span>
            {account.currency && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                {account.currency}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right">
          <p className={`text-sm font-bold tabular-nums ${account.balance_current !== null && account.balance_current < 0 ? "text-red-500" : "text-slate-800"}`}>
            {formatBalance(account.balance_current, account.currency)}
          </p>
          {account.last_synced_at && (
            <p className="text-[9px] text-slate-400">
              {new Date(account.last_synced_at).toLocaleDateString("es-CL")}
            </p>
          )}
        </div>

        <select
          value={account.account_type}
          onChange={(e) => changeType(e.target.value as "personal" | "joint")}
          disabled={updating}
          className={`text-[10px] font-medium px-2 py-1 rounded-md border cursor-pointer appearance-none pr-5 disabled:opacity-50 transition-colors ${
            account.account_type === "joint"
              ? "bg-emerald-50 border-emerald-200 text-emerald-700"
              : "bg-blue-50 border-blue-200 text-blue-700"
          }`}
          style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`, backgroundRepeat: "no-repeat", backgroundPosition: "right 4px center" }}
        >
          <option value="personal">Personal</option>
          <option value="joint">Compartida</option>
        </select>

        <button
          onClick={toggleActive}
          disabled={updating}
          className="text-[10px] font-medium text-slate-400 hover:text-slate-600 transition-colors"
        >
          {account.is_active ? "Ocultar" : "Mostrar"}
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Exported section — single unified card
   ═══════════════════════════════════════════════════════════════════ */

export function BankAccountsSection({ householdId }: { householdId: string | null }) {
  const userId = useLukaStore((s) => s.userId);
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);

  const { data: connections, isLoading: loadingConnections } = useBankConnections();
  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 30_000,
  });

  const hasConnections = connections && connections.length > 0;
  const hasAccounts = accounts && accounts.length > 0;
  const isEmpty = !hasConnections && !hasAccounts;
  const isLoading = loadingConnections || loadingAccounts;

  return (
    <div className="bg-white rounded-xl border border-slate-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="px-5 pt-5 pb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Cuentas Bancarias</h3>
        <Button size="sm" variant="outline" onClick={() => setShowModal(true)} className="text-luka-primary border-luka-primary hover:bg-luka-light">
          + Conectar banco
        </Button>
      </div>

      <div className="px-5 pb-5 space-y-3">
        {isLoading && <p className="text-sm text-luka-muted py-2">Cargando...</p>}

        {!isLoading && isEmpty && (
          <p className="text-sm text-luka-muted py-2">No hay bancos conectados. Conecta tu banco para importar transacciones automáticamente.</p>
        )}

        {/* Luka Connect connections */}
        {hasConnections && connections.map((conn) => (
          <BankConnectionCard key={conn.bank_code} connection={conn} />
        ))}

        {/* Email-linked bank accounts */}
        {hasAccounts && accounts.filter((a) => a.account_name === null).map((account) => (
          <AccountCard
            key={account.id} account={account} currentUserId={userId} householdId={householdId}
            onDeleted={(id) => {
              queryClient.setQueryData<BankAccountRow[]>(["bank-accounts", householdId], (prev) => prev?.filter((a) => a.id !== id) ?? []);
              queryClient.invalidateQueries({ queryKey: ["transactions"] });
            }}
            onUpdated={(id, patch) => {
              queryClient.setQueryData<BankAccountRow[]>(["bank-accounts", householdId], (prev) => prev?.map((a) => a.id === id ? { ...a, ...patch } as BankAccountRow : a) ?? []);
            }}
          />
        ))}

        {/* Detected accounts from Luka Connect */}
        {(() => {
          // Connect-created accounts have account_name set; email-linked ones don't
          const detectedAccounts = accounts?.filter((a) => a.account_name !== null) ?? [];
          if (detectedAccounts.length === 0) return null;

          // Group by bank
          const byBank = new Map<string, BankAccountRow[]>();
          detectedAccounts.forEach((a) => {
            const list = byBank.get(a.bank_name) ?? [];
            list.push(a);
            byBank.set(a.bank_name, list);
          });

          return (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-700">Cuentas Detectadas</h3>
              <p className="text-xs text-slate-400">
                Cuentas creadas automáticamente al sincronizar con tu banco.
              </p>
              {Array.from(byBank.entries()).map(([bankName, bankAccounts]) => (
                <div key={bankName} className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                    {bankName}
                  </p>
                  {bankAccounts.map((a) => (
                    <DetectedAccountCard
                      key={a.id}
                      account={a}
                      householdId={householdId!}
                    />
                  ))}
                </div>
              ))}
            </div>
          );
        })()}
      </div>

      {showModal && <ConnectBankModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
