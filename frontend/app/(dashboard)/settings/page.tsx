"use client";
import Script from "next/script";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { createClient } from "@/app/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";


function ConnectBankSection() {
  const { householdId, userId } = useLukaStore();
  const [scriptReady, setScriptReady] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    // Fintoc SDK v1 bug: internally calls postMessage() with options including callbacks,
    // which throws DataCloneError (functions can't be structured-cloned).
    // Patching Window.prototype intercepts all postMessage calls regardless of
    // when the SDK captured the reference.
    const proto = Window.prototype;
    const orig = proto.postMessage;
    proto.postMessage = function (this: Window, msg: unknown, ...args: unknown[]) {
      try { return orig.apply(this, [msg, ...args] as Parameters<typeof orig>); }
      catch (e) { if (e instanceof DOMException && e.name === "DataCloneError") return; throw e; }
    };
    return () => { proto.postMessage = orig; };
  }, []);

  function openWidget() {
    if (!window.Fintoc) {
      setMessage("El widget de Fintoc no está disponible. Recarga la página.");
      return;
    }
    if (!householdId || !userId) {
      setMessage("Error: sesión no inicializada. Recarga la página e intenta nuevamente.");
      console.warn("[Fintoc] householdId or userId missing from store", { householdId, userId });
      return;
    }
    setMessage(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const webhookUrl = `${apiUrl}/bank-accounts/webhooks/fintoc-link?household_id=${householdId}&user_id=${userId}`;

    console.log("[Fintoc] Opening widget with webhookUrl:", webhookUrl);

    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      holderType: "individual",
      webhookUrl,
      onSuccess: () => {
        setMessage("¡Cuenta conectada! El historial se importa en segundo plano.");
      },
      onExit: () => setMessage("Conexión cancelada."),
      onEvent: (eventName: string) => {
        if (eventName === "closed") setMessage("Conexión cancelada.");
      },
    });
    widget.open();
  }

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-luka-dark">Cuentas bancarias</CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={openWidget}
            disabled={!scriptReady}
            className="text-luka-primary border-luka-primary hover:bg-luka-light"
          >
            + Agregar cuenta
          </Button>
        </CardHeader>
        <CardContent>
          {message && <p className="text-sm text-luka-muted mb-3">{message}</p>}
          {!message && (
            <p className="text-sm text-luka-muted">
              Conecta tus cuentas para importar transacciones automáticamente.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { userFullName, reset } = useLukaStore();

  const signOut = async () => {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
    } finally {
      reset();
      router.push("/login");
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-luka-dark">Configuración</h2>

      <ConnectBankSection />

      <Card className="bg-white">
        <CardHeader><CardTitle className="text-sm font-semibold">Cuenta</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-luka-muted">Conectado como <span className="font-medium text-luka-dark">{userFullName ?? "tu cuenta"}</span></p>
          <Button variant="outline" className="text-luka-danger border-luka-danger hover:bg-red-50" onClick={signOut}>
            Cerrar sesión
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-white">
        <CardHeader><CardTitle className="text-sm font-semibold">Privacidad de datos</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm text-luka-muted">
          <p>Luka almacena solo el monto, comercio y categoría de tus transacciones.</p>
          <p>El contenido de tus correos se elimina automáticamente después de 24 horas.</p>
          <p>Nunca almacenamos números de tarjeta ni claves bancarias.</p>
          <p className="mt-2">
            <a href="#" className="text-luka-primary underline text-xs">
              Política de privacidad (Ley 21.719)
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
