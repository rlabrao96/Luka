"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/app/lib/api";

type Screen = "form" | "waiting" | "success";

const COUNTDOWN_SECONDS = 120;

export default function ConnectBankPage() {
  const router = useRouter();

  const [screen, setScreen] = useState<Screen>("form");
  const [rut, setRut] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup intervals on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const startWaiting = () => {
    setScreen("waiting");
    setCountdown(COUNTDOWN_SECONDS);
    setError(null);

    // Countdown timer
    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          stopPolling();
          setError("timeout");
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    // Poll sync status every 3 seconds
    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getSyncStatus("bchile");
        if (status.last_sync_status === "success") {
          stopPolling();
          setScreen("success");
        } else if (status.last_sync_status?.startsWith("failed")) {
          stopPolling();
          setError("failed");
        }
      } catch {
        // ignore transient network errors while polling
      }
    }, 3000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rut.trim() || !password.trim()) return;

    setError(null);
    setIsSubmitting(true);

    try {
      await api.connectBank({ bank_code: "bchile", rut: rut.trim(), password });
      startWaiting();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al conectar";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = () => {
    stopPolling();
    setError(null);
    setScreen("form");
    setPassword("");
  };

  const handleSkip = () => {
    router.push("/");
  };

  const handleContinue = () => {
    router.push("/");
  };

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  // ── Screen 1: Credential Entry Form ─────────────────────────────────────────

  if (screen === "form") {
    return (
      <Card className="w-full shadow-sm">
        <CardHeader>
          <CardTitle className="text-luka-dark">Conecta tu banco</CardTitle>
          <CardDescription className="text-luka-muted">
            Ingresa tus credenciales de banca en línea para importar tus movimientos.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Bank selector */}
            <div className="space-y-1.5">
              <label htmlFor="bank" className="text-luka-dark text-sm font-medium">
                Banco
              </label>
              <select
                id="bank"
                disabled
                className="w-full h-10 px-3 rounded-xl border border-input bg-background text-sm text-luka-dark focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <option value="bchile">Banco de Chile</option>
              </select>
            </div>

            {/* RUT input */}
            <div className="space-y-1.5">
              <label htmlFor="rut" className="text-luka-dark text-sm font-medium">
                RUT
              </label>
              <Input
                id="rut"
                type="text"
                placeholder="12.345.678-9"
                value={rut}
                onChange={(e) => { setRut(e.target.value); setError(null); }}
                disabled={isSubmitting}
                className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                autoComplete="username"
              />
            </div>

            {/* Password input */}
            <div className="space-y-1.5">
              <label htmlFor="password" className="text-luka-dark text-sm font-medium">
                Clave Internet
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Clave Internet"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(null); }}
                disabled={isSubmitting}
                className="rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                autoComplete="current-password"
              />
            </div>

            {/* Error message */}
            {error && (
              <p className="text-sm text-red-500 font-medium">{error}</p>
            )}

            {/* Submit button */}
            <Button
              type="submit"
              disabled={isSubmitting || !rut.trim() || !password.trim()}
              className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              {isSubmitting ? "Conectando..." : "Conectar"}
            </Button>

            {/* Trust / encryption message */}
            <div className="flex items-start gap-2 rounded-lg bg-blue-50 border border-blue-100 p-3">
              {/* Lock icon */}
              <svg
                className="w-4 h-4 text-luka-primary mt-0.5 flex-shrink-0"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <p className="text-xs text-luka-muted leading-relaxed">
                Tus datos están encriptados y solo se usan para sincronizar tus movimientos.
              </p>
            </div>

            {/* Skip link */}
            <button
              type="button"
              onClick={handleSkip}
              className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-1"
            >
              Omitir
            </button>
          </form>
        </CardContent>
      </Card>
    );
  }

  // ── Screen 2: Waiting / 2FA ──────────────────────────────────────────────────

  if (screen === "waiting") {
    const isTimeout = error === "timeout";
    const isFailed = error === "failed";
    const hasError = isTimeout || isFailed;

    return (
      <Card className="w-full shadow-sm">
        <CardHeader>
          <CardTitle className="text-luka-dark">
            {hasError ? "No se pudo conectar" : "Conectando con Banco de Chile..."}
          </CardTitle>
          <CardDescription className="text-luka-muted">
            {isTimeout
              ? "Se agotó el tiempo de espera. Inténtalo de nuevo."
              : isFailed
              ? "Ocurrió un error al conectar. Verifica tus credenciales e inténtalo de nuevo."
              : "Aprueba la Clave Dinámica en tu app del banco"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {!hasError ? (
            <>
              {/* Spinner */}
              <div className="flex justify-center py-4">
                <div className="w-12 h-12 rounded-full border-4 border-blue-100 border-t-luka-primary animate-spin" />
              </div>

              {/* Instructions */}
              <div className="rounded-lg bg-blue-50 border border-blue-100 p-4 text-center space-y-1">
                <p className="text-sm text-luka-dark font-medium">
                  Revisa la app de tu banco
                </p>
                <p className="text-xs text-luka-muted">
                  Banco de Chile enviará una Clave Dinámica. Apruébala para completar la conexión.
                </p>
              </div>

              {/* Countdown */}
              <div className="text-center">
                <p className="text-xs text-luka-muted mb-1">Tiempo restante</p>
                <p className="text-2xl font-bold text-luka-primary tabular-nums">
                  {formatCountdown(countdown)}
                </p>
              </div>
            </>
          ) : (
            <Button
              onClick={handleRetry}
              className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              Intentar de nuevo
            </Button>
          )}

          <button
            type="button"
            onClick={handleSkip}
            className="w-full text-sm text-luka-muted hover:text-luka-dark text-center py-1"
          >
            Omitir
          </button>
        </CardContent>
      </Card>
    );
  }

  // ── Screen 3: Success ────────────────────────────────────────────────────────

  return (
    <Card className="w-full shadow-sm">
      <CardHeader>
        <CardTitle className="text-luka-dark">Banco conectado</CardTitle>
        <CardDescription className="text-luka-muted">
          Se importaron tus movimientos correctamente.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Checkmark */}
        <div className="flex justify-center py-4">
          <div className="w-16 h-16 rounded-full bg-blue-50 border-2 border-luka-primary flex items-center justify-center">
            <svg
              className="w-8 h-8 text-luka-primary"
              xmlns="http://www.w3.org/2000/svg"
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
        </div>

        <Button
          onClick={handleContinue}
          className="w-full bg-luka-primary text-white hover:bg-blue-700 rounded-xl focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        >
          Continuar →
        </Button>
      </CardContent>
    </Card>
  );
}
