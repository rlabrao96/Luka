"use client";
import Script from "next/script";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { createClient } from "@/app/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useLukaStore } from "@/app/lib/store";
import { api, FintocAccount, SelectedFintocAccount } from "@/app/lib/api";
import { FintocAccountPicker } from "@/app/(dashboard)/components/FintocAccountPicker";

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

function ConnectBankSection() {
  const { householdId } = useLukaStore();
  const [scriptReady, setScriptReady] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [fintocAccounts, setFintocAccounts] = useState<FintocAccount[]>([]);
  const [linkToken, setLinkToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function openWidget() {
    if (!window.Fintoc) return;
    setMessage(null);
    const widget = window.Fintoc.create({
      publicKey: process.env.NEXT_PUBLIC_FINTOC_PUBLIC_KEY ?? "",
      product: "movements",
      country: "cl",
      onSuccess: async (token: string) => {
        setLinkToken(token);
        try {
          const accounts = await api.getFintocAccounts(token);
          setFintocAccounts(accounts);
          setShowPicker(true);
        } catch {
          setMessage("Error al cargar las cuentas.");
        }
      },
      onExit: () => setMessage("Conexión cancelada."),
      onError: () => setMessage("Error al conectar."),
    });
    widget.open();
  }

  async function handleConfirm(selected: SelectedFintocAccount[]) {
    if (!householdId) return;
    setConnecting(true);
    try {
      await api.connectFintocAccounts({ link_token: linkToken, household_id: householdId, accounts: selected });
      setShowPicker(false);
      setFintocAccounts([]);
      setMessage("¡Cuentas conectadas! El historial se importa en segundo plano.");
    } catch {
      setMessage("Error al guardar las cuentas.");
    } finally {
      setConnecting(false);
    }
  }

  return (
    <>
      <Script src="https://js.fintoc.com/v1/" onReady={() => setScriptReady(true)} />
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base text-luka-dark">Cuentas bancarias</CardTitle>
          {!showPicker && (
            <Button
              size="sm"
              variant="outline"
              onClick={openWidget}
              disabled={!scriptReady}
              className="text-luka-primary border-luka-primary hover:bg-luka-light"
            >
              + Agregar cuenta
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {message && <p className="text-sm text-luka-muted mb-3">{message}</p>}
          {showPicker && (
            <FintocAccountPicker
              key={fintocAccounts[0]?.id}
              accounts={fintocAccounts}
              onConfirm={handleConfirm}
              loading={connecting}
            />
          )}
          {!showPicker && !message && (
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
