"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/app/lib/api";

/* ═══════════════════════════════════════════════════════════════════════════
   Bank registry — brand colors, icons, and availability
   ═══════════════════════════════════════════════════════════════════════════ */

interface BankDef {
  code: string;
  name: string;
  color: string;
  textColor: string;
  initials: string;
  available: boolean;
  requires2FA: boolean;
}

const BANKS: BankDef[] = [
  { code: "bchile",     name: "Banco de Chile",   color: "#003B71", textColor: "#FFFFFF", initials: "BC",  available: true,  requires2FA: false },
  { code: "bestado",    name: "Banco Estado",      color: "#D52B1E", textColor: "#FFFFFF", initials: "BE",  available: false, requires2FA: true },
  { code: "bci",        name: "BCI",               color: "#E63027", textColor: "#FFFFFF", initials: "BCI", available: false, requires2FA: true },
  { code: "santander",  name: "Banco Santander",   color: "#EC0000", textColor: "#FFFFFF", initials: "S",   available: false, requires2FA: true },
  { code: "itau",       name: "Banco Itau",       color: "#FF6600", textColor: "#FFFFFF", initials: "itu",available: false, requires2FA: true },
  { code: "scotiabank", name: "Scotiabank",        color: "#EC111A", textColor: "#FFFFFF", initials: "Sb",  available: false, requires2FA: true },
  { code: "bice",       name: "Banco BICE",        color: "#1B3A6B", textColor: "#FFFFFF", initials: "BI",  available: false, requires2FA: true },
  { code: "falabella",  name: "Banco Falabella",   color: "#8BC540", textColor: "#FFFFFF", initials: "BF",  available: false, requires2FA: true },
  { code: "edwards",    name: "Banco Edwards",     color: "#00529B", textColor: "#FFFFFF", initials: "Ed",  available: false, requires2FA: true },
];

/* ═══════════════════════════════════════════════════════════════════════════
   Shared components
   ═══════════════════════════════════════════════════════════════════════════ */

function BankIcon({ bank, size = 40 }: { bank: BankDef; size?: number }) {
  const fontSize = size < 36 ? 11 : bank.initials.length > 2 ? 11 : 14;
  return (
    <div
      className="rounded-lg flex items-center justify-center font-bold flex-shrink-0 shadow-sm"
      style={{
        width: size,
        height: size,
        backgroundColor: bank.color,
        color: bank.textColor,
        fontSize,
        letterSpacing: "-0.02em",
      }}
    >
      {bank.initials}
    </div>
  );
}

function ChevronRight({ className = "" }: { className?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className={className}>
      <path d="M7.5 5L12.5 10L7.5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ShieldCheck() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-luka-primary">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-luka-primary">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0110 0v4" />
    </svg>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute top-0 left-0 p-2 text-white/60 hover:text-white transition-colors"
      aria-label="Volver"
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M12.5 15L7.5 10L12.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main page component
   ═══════════════════════════════════════════════════════════════════════════ */

type Screen = "intro" | "select" | "credentials" | "connecting" | "success";

export default function ConnectBankPage() {
  const router = useRouter();

  const [screen, setScreen] = useState<Screen>("intro");
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
    setScreen("connecting");
    setError(null);

    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getSyncStatus(bankCode);
        const s = status.last_sync_status;
        if (s === "in_progress" || s === "awaiting_2fa" || s === "success") {
          stopPolling();
          setScreen("success");
        } else if (s?.startsWith("failed")) {
          stopPolling();
          setError(s === "failed_login" ? "Credenciales incorrectas. Verifica tu RUT y clave." : "Error al conectar con el banco.");
          setScreen("credentials");
          setPassword("");
        }
      } catch { /* ignore */ }
    }, 3000);

    timeoutRef.current = setTimeout(() => {
      stopPolling();
      setScreen("success");
    }, 60000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rut.trim() || !password.trim() || !selectedBank) return;

    setError(null);
    setIsSubmitting(true);

    try {
      await api.connectBank({ bank_code: selectedBank.code, rut: rut.trim(), password });
      waitForSessionStart(selectedBank.code);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al conectar";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => router.push("/");
  const handleContinue = () => router.push("/");

  /* ── Screen 0: Intro ──────────────────────────────────────────────────── */

  if (screen === "intro") {
    return (
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-xl font-bold text-white">
            <span className="text-luka-sky">Luka</span> se conectara con tu banco
          </h2>
          <p className="text-sm text-white/70">
            Importaremos tus movimientos de forma segura
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-start gap-3 bg-white/10 rounded-xl p-4 border border-white/10">
            <div className="mt-0.5 flex-shrink-0">
              <ShieldCheck />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Seguro</p>
              <p className="text-xs text-white/60 leading-relaxed">
                Tus credenciales se encriptan con AES-256 y nunca se comparten con terceros.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 bg-white/10 rounded-xl p-4 border border-white/10">
            <div className="mt-0.5 flex-shrink-0">
              <LockIcon />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Privado</p>
              <p className="text-xs text-white/60 leading-relaxed">
                Solo tu puedes ver tus datos. Puedes desconectar tu banco en cualquier momento.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-3 pt-2">
          <Button
            onClick={() => setScreen("select")}
            className="w-full bg-luka-primary text-white hover:bg-luka-primary-dark rounded-xl h-12 text-base font-semibold shadow-lg shadow-blue-500/20"
          >
            Continuar
          </Button>

          <button
            type="button"
            onClick={handleSkip}
            className="w-full text-sm text-white/50 hover:text-white/80 text-center py-1 transition-colors"
          >
            Omitir por ahora
          </button>
        </div>
      </div>
    );
  }

  /* ── Screen 1: Bank selector ──────────────────────────────────────────── */

  if (screen === "select") {
    return (
      <div className="space-y-4 relative">
        <BackButton onClick={() => setScreen("intro")} />

        <div className="text-center pt-2">
          <h2 className="text-xl font-bold text-white">Selecciona tu banco</h2>
        </div>

        <div className="space-y-1">
          {BANKS.map((bank) => (
            <button
              key={bank.code}
              type="button"
              disabled={!bank.available}
              onClick={() => {
                if (bank.available) {
                  setSelectedBank(bank);
                  setScreen("credentials");
                }
              }}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all ${
                bank.available
                  ? "hover:bg-white/15 active:bg-white/20 cursor-pointer"
                  : "opacity-40 cursor-not-allowed"
              }`}
            >
              <BankIcon bank={bank} />
              <span className="flex-1 text-left text-sm font-medium text-white">
                {bank.name}
              </span>
              {bank.available ? (
                <ChevronRight className="text-white/40" />
              ) : (
                <span className="text-[10px] text-white/30 font-medium uppercase tracking-wider">
                  Pronto
                </span>
              )}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={handleSkip}
          className="w-full text-sm text-white/50 hover:text-white/80 text-center py-1 transition-colors"
        >
          Omitir por ahora
        </button>
      </div>
    );
  }

  /* ── Screen 2: Credentials ────────────────────────────────────────────── */

  if (screen === "credentials" && selectedBank) {
    return (
      <div className="space-y-5 relative">
        <BackButton onClick={() => setScreen("select")} />

        <div className="flex flex-col items-center gap-3 pt-2">
          <BankIcon bank={selectedBank} size={52} />
          <h2 className="text-lg font-bold text-white">{selectedBank.name}</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="rut" className="text-white/80 text-sm font-medium">
              RUT
            </label>
            <Input
              id="rut"
              type="text"
              placeholder="12.345.678-9"
              value={rut}
              onChange={(e) => { setRut(e.target.value); setError(null); }}
              disabled={isSubmitting}
              className="rounded-xl h-11 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:ring-2 focus:ring-luka-primary/50 focus:border-luka-primary"
              autoComplete="username"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-white/80 text-sm font-medium">
              Clave Internet
            </label>
            <Input
              id="password"
              type="password"
              placeholder="Tu clave de acceso"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(null); }}
              disabled={isSubmitting}
              className="rounded-xl h-11 bg-white/10 border-white/20 text-white placeholder:text-white/30 focus:ring-2 focus:ring-luka-primary/50 focus:border-luka-primary"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p className="text-sm text-red-400 font-medium text-center">{error}</p>
          )}

          <Button
            type="submit"
            disabled={isSubmitting || !rut.trim() || !password.trim()}
            className="w-full bg-luka-primary text-white hover:bg-luka-primary-dark rounded-xl h-12 text-base font-semibold shadow-lg shadow-blue-500/20 disabled:opacity-50"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Conectando...
              </span>
            ) : (
              "Conectar"
            )}
          </Button>

          <div className="flex items-center justify-center gap-1.5 text-white/40">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0110 0v4" />
            </svg>
            <span className="text-[11px]">Encriptado con AES-256</span>
          </div>
        </form>
      </div>
    );
  }

  /* ── Screen 3: Connecting — waiting for session confirmation ─────────── */

  if (screen === "connecting" && selectedBank) {
    return (
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-xl font-bold text-white">Conectando con {selectedBank.name}</h2>
          <p className="text-sm text-white/60">Iniciando sesión, esto puede tomar unos segundos...</p>
        </div>
        <div className="flex justify-center py-4">
          <div className="relative">
            <div className="w-20 h-20 rounded-full border-[3px] border-white/10 border-t-luka-primary animate-spin" />
            <div className="absolute inset-0 flex items-center justify-center">
              <BankIcon bank={selectedBank} size={36} />
            </div>
          </div>
        </div>
        <button type="button" onClick={handleSkip} className="w-full text-sm text-white/50 hover:text-white/80 text-center py-1 transition-colors">
          Omitir por ahora
        </button>
      </div>
    );
  }

  /* ── Screen 4: Success — scrape started in background ────────────────── */

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold text-white">Sesión iniciada correctamente</h2>
        <p className="text-sm text-white/70">
          Estamos extrayendo tus movimientos históricos. Esto puede tomar alrededor de 5 minutos.
        </p>
        <p className="text-xs text-white/50">
          Tus transacciones aparecerán automáticamente en el dashboard.
        </p>
      </div>

      {/* Success animation */}
      <div className="flex justify-center py-6">
        <div className="relative">
          <div className="w-20 h-20 rounded-full bg-luka-success/20 flex items-center justify-center">
            <svg
              className="w-10 h-10 text-luka-success"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          {selectedBank && (
            <div className="absolute -bottom-1 -right-1 shadow-lg rounded-lg">
              <BankIcon bank={selectedBank} size={28} />
            </div>
          )}
        </div>
      </div>

      <Button
        onClick={handleContinue}
        className="w-full bg-luka-primary text-white hover:bg-luka-primary-dark rounded-xl h-12 text-base font-semibold shadow-lg shadow-blue-500/20"
      >
        Ir al dashboard
      </Button>
    </div>
  );
}
