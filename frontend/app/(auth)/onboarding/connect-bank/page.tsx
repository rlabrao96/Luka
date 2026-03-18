"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLukaStore } from "@/app/lib/store";


type Step = "connect" | "done";

export default function ConnectBankPage() {
  const router = useRouter();
  const { householdId, userId } = useLukaStore();
  const [step, setStep] = useState<Step>("connect");
  const [error, setError] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    const proto = Window.prototype;
    const orig = proto.postMessage;
    proto.postMessage = function (this: Window, msg: unknown, ...args: unknown[]) {
      try { return orig.apply(this, [msg, ...args] as Parameters<typeof orig>); }
      catch (e) { if (e instanceof DOMException && e.name === "DataCloneError") return; throw e; }
    };
    return () => { proto.postMessage = orig; };
  }, []);

  async function openFintocWidget() {
    if (!window.Fintoc) {
      setError("Widget no disponible. Recarga la página.");
      return;
    }
    setError(null);

    let hId = householdId;
    let uId = userId;

    // Graceful fallback: if Zustand is empty, fetch the source of truth immediately
    if (!hId || !uId) {
      try {
        const { api } = await import("@/app/lib/api");
        const user = await api.getMe();
        hId = user.household_id;
        uId = String(user.id);
        
        // Hydrate store so we don't need to fetch again
        if (hId) useLukaStore.getState().setHousehold(hId);
        if (uId) useLukaStore.getState().setUser(uId, user.full_name);
      } catch (e) {
        setError("Falló la conexión de tu sesión. Asegúrate de estar conectado.");
        return;
      }
    }

    if (!hId || !uId) {
      setError("No tienes un hogar creado todavía. Por favor vuelve al paso anterior.");
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://luka-production-eb87.up.railway.app";
    const webhookUrl = `${apiUrl}/bank-accounts/webhooks/fintoc-link?household_id=${hId}&user_id=${uId}`;

    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      holderType: "individual",
      webhookUrl,
      onSuccess: () => {
        setStep("done");
        setTimeout(() => router.push("/"), 1500);
      },
      onExit: () => setError("Conexión cancelada."),
      onEvent: (eventName) => {
        if (eventName === "closed") setError("Conexión cancelada.");
      },
    });

    widget.open();
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
                  onClick={() => router.push("/")}
                  className="w-full text-sm text-luka-muted hover:text-luka-dark text-center"
                >
                  Saltar por ahora
                </button>
              </div>
            )}

            {step === "done" && (
              <div className="text-center py-8">
                <p className="text-luka-dark font-medium">¡Cuenta conectada!</p>
                <p className="text-sm text-luka-muted mt-1">El historial se importa en segundo plano. Redirigiendo.</p>
              </div>
            )}
          </CardContent>
      </Card>
    </>
  );
}
