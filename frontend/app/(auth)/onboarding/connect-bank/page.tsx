"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FintocAccountPicker } from "@/app/(dashboard)/components/FintocAccountPicker";
import { api, FintocAccount, SelectedFintocAccount } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

declare global {
  interface Window {
    Fintoc?: {
      create: (options: {
        publicKey: string;
        product: string;
        country: string;
        onSuccess: (linkToken: string) => void;
        onExit: () => void;
        onError: (err: Error) => void;
      }) => { open: () => void };
    };
  }
}

type Step = "connect" | "pick" | "loading" | "done";

export default function ConnectBankPage() {
  const router = useRouter();
  const { householdId } = useLukaStore();
  const [step, setStep] = useState<Step>("connect");
  const [fintocAccounts, setFintocAccounts] = useState<FintocAccount[]>([]);
  const [linkToken, setLinkToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  function openFintocWidget() {
    if (!window.Fintoc) {
      setError("Widget no disponible. Recarga la página.");
      return;
    }
    setError(null);
    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      onSuccess: async (token: string) => {
        setLinkToken(token);
        try {
          const accounts = await api.getFintocAccounts(token);
          setFintocAccounts(accounts);
          setStep("pick");
        } catch {
          setError("No se pudieron cargar las cuentas. Intenta de nuevo.");
        }
      },
      onExit: () => setError("Conexión cancelada."),
      onError: (err: Error) => {
        console.error("Fintoc widget error:", err);
        setError("Error al conectar. Intenta de nuevo.");
      },
    });
    widget.open();
  }

  async function handleConfirm(selected: SelectedFintocAccount[]) {
    if (!householdId) {
      setError("No se pudo identificar tu hogar. Recarga la página.");
      setStep("pick");
      return;
    }
    setStep("loading");
    try {
      await api.connectFintocAccounts({
        link_token: linkToken,
        household_id: householdId,
        accounts: selected,
      });
      setStep("done");
      setTimeout(() => router.push("/onboarding/verify-whatsapp"), 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      setError(
        msg.includes("409")
          ? "Una de las cuentas ya está conectada."
          : "Error al guardar las cuentas. Intenta de nuevo."
      );
      setStep("pick");
    }
  }

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="w-full shadow-sm">
          <CardHeader>
            <CardTitle className="text-luka-dark">Conecta tu banco</CardTitle>
            <CardDescription className="text-luka-muted">
              Conecta tus cuentas bancarias y tarjetas. Importaremos los últimos 3 meses automáticamente.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <p className="text-sm text-luka-danger bg-red-50 rounded-md px-3 py-2">{error}</p>
            )}

            {step === "connect" && (
              <div className="space-y-4">
                <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
                  <p className="text-sm text-luka-dark font-medium mb-1">¿Cómo funciona?</p>
                  <ul className="text-sm text-luka-muted space-y-1 list-disc list-inside">
                    <li>Conecta de forma segura con tu banco</li>
                    <li>Elige qué cuentas y tarjetas incluir</li>
                    <li>Importamos 3 meses de historial automáticamente</li>
                  </ul>
                </div>
                <Button
                  onClick={openFintocWidget}
                  disabled={!scriptReady}
                  className="w-full bg-luka-primary text-white hover:bg-blue-700"
                >
                  {scriptReady ? "Conectar banco" : "Cargando..."}
                </Button>
                <button
                  onClick={() => router.push("/onboarding/verify-whatsapp")}
                  className="w-full text-sm text-luka-muted hover:text-luka-dark text-center"
                >
                  Saltar por ahora
                </button>
              </div>
            )}

            {step === "pick" && fintocAccounts.length > 0 && (
              <FintocAccountPicker
                key={fintocAccounts[0]?.id}
                accounts={fintocAccounts}
                onConfirm={handleConfirm}
                loading={false}
              />
            )}

            {step === "loading" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">Guardando cuentas...</p>
                <p className="text-sm text-luka-muted mt-1">El historial se importará en segundo plano.</p>
              </div>
            )}

            {step === "done" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">¡Cuentas conectadas!</p>
                <p className="text-sm text-luka-muted mt-1">Importando historial... Redirigiendo.</p>
              </div>
            )}
          </CardContent>
      </Card>
    </>
  );
}
