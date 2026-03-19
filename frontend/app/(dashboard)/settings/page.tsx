"use client";
import Script from "next/script";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { createClient } from "@/app/lib/supabase/client";
import { useRouter } from "next/navigation";
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

const IMPORT_STATUS_LABEL: Record<string, string> = {
  pending: "En cola",
  importing: "Importando...",
  done: "Listo",
  failed: "Error",
};

const IMPORT_STATUS_COLOR: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  importing: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

function bankLabel(bankName: string): string {
  if (!bankName) return "Banco desconocido";
  // capitalize each word, trim "fintoc" fallback
  if (bankName.toLowerCase() === "fintoc") return "Banco (Fintoc)";
  return bankName
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

// ── Account row ────────────────────────────────────────────

function AccountRow({ account, currentUserId }: { account: BankAccountRow; currentUserId: string | null }) {
  const isOwn = account.user_id === currentUserId;
  const typeLabel = ACCOUNT_TYPE_LABEL[account.account_type] ?? account.account_type;
  const typeColor = ACCOUNT_TYPE_COLOR[account.account_type] ?? "bg-gray-100 text-gray-700";
  const kindLabel = account.account_kind
    ? (ACCOUNT_KIND_LABEL[account.account_kind] ?? account.account_kind)
    : null;
  const importLabel = IMPORT_STATUS_LABEL[account.import_status] ?? account.import_status;
  const importColor = IMPORT_STATUS_COLOR[account.import_status] ?? "bg-gray-100 text-gray-700";

  return (
    <div className="flex items-center justify-between py-3 border-b last:border-0">
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-luka-dark">{bankLabel(account.bank_name)}</p>
        <p className="text-xs text-luka-muted">
          {kindLabel ?? "Cuenta bancaria"}
          {!isOwn && (
            <span className="ml-1 text-purple-600">· Pareja</span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-2 flex-wrap justify-end">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>
          {typeLabel}
        </span>
        {account.import_status !== "done" && (
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${importColor}`}>
            {importLabel}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Connect bank section ───────────────────────────────────

function ConnectBankSection() {
  const setUser = useLukaStore((s) => s.setUser);
  const setHousehold = useLukaStore((s) => s.setHousehold);

  const [householdId, setHouseholdId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [loadingUser, setLoadingUser] = useState(false);

  useEffect(() => {
    setHouseholdId(useLukaStore.getState().householdId);
    setUserId(useLukaStore.getState().userId);
  }, []);

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

  // Refetch accounts after successful connection
  const { refetch } = useQuery({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: false, // only triggered manually via refetch()
  });

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
        refetch();
      },
      onExit: () => setMessage("Conexión cancelada."),
      onEvent: (eventName: string) => {
        if (eventName === "closed") setMessage("Conexión cancelada.");
      },
    });
    widget.open();
  }

  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ["bank-accounts", householdId],
    queryFn: () => api.getBankAccounts(householdId!),
    enabled: !!householdId,
    staleTime: 30_000,
  });

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

          {loadingAccounts && (
            <p className="text-sm text-luka-muted">Cargando cuentas...</p>
          )}

          {!loadingAccounts && accounts && accounts.length === 0 && (
            <p className="text-sm text-luka-muted">
              Conecta tus cuentas para importar transacciones automáticamente.
            </p>
          )}

          {!loadingAccounts && accounts && accounts.length > 0 && (
            <div className="divide-y divide-gray-100">
              {accounts.map((account) => (
                <AccountRow key={account.id} account={account} currentUserId={userId} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

// ── Page ───────────────────────────────────────────────────

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
