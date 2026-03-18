"use client";
import Script from "next/script";
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { createClient } from "@/app/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";
import { api } from "@/app/lib/api";

function ConnectBankSection() {
  // Read from store; if empty, fetch directly from /auth/me on mount
  const storeHouseholdId = useLukaStore((s) => s.householdId);
  const storeUserId = useLukaStore((s) => s.userId);
  const setUser = useLukaStore((s) => s.setUser);
  const setHousehold = useLukaStore((s) => s.setHousehold);

  const [householdId, setHouseholdId] = useState<string | null>(storeHouseholdId);
  const [userId, setUserId] = useState<string | null>(storeUserId);
  const [scriptReady, setScriptReady] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [loadingUser, setLoadingUser] = useState(false);

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

  // Fetch user info directly from API if store is empty
  // (StoreInitializer may not have run yet, or the backend just (re)deployed)
  useEffect(() => {
    if (householdId && userId) return;
    setLoadingUser(true);
    api
      .getMe()
      .then((user) => {
        const uid = String(user.id);
        setUserId(uid);
        setUser(uid, user.full_name);
        if (user.household_id) {
          setHouseholdId(user.household_id);
          setHousehold(user.household_id);
        }
      })
      .catch(() => {
        setMessage("No se pudo verificar tu sesión. Recarga la página.");
      })
      .finally(() => setLoadingUser(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
            disabled={!scriptReady || loadingUser}
            className="text-luka-primary border-luka-primary hover:bg-luka-light"
          >
            {loadingUser ? "Cargando..." : "+ Agregar cuenta"}
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
