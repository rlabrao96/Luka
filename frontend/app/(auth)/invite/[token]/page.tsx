"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";
import { createClient } from "@/app/lib/supabase/client";

export default function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = React.use(params);
  const router = useRouter();
  const setHousehold = useLukaStore((s) => s.setHousehold);
  const reset = useLukaStore((s) => s.reset);

  const [status, setStatus] = useState<"checking" | "unauthenticated" | "loading" | "self-invite" | "error" | "success">("checking");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    async function init() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();

      if (!session) {
        setStatus("unauthenticated");
        return;
      }

      await tryAccept();
    }

    async function tryAccept() {
      setStatus("loading");
      try {
        const data = await api.acceptInvite(token);
        setHousehold(data.household_id);
        localStorage.removeItem("pending_invite_token");
        setStatus("success");
        router.push("/household");
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : "";

        // Self-invite or same-account member — special UI
        if (
          errMsg.includes("propia invitación") ||
          errMsg.includes("Ya eres miembro") ||
          errMsg.includes("Ya perteneces a un grupo compartido")
        ) {
          setErrorMessage(errMsg);
          setStatus("self-invite");
          return;
        }

        setErrorMessage(errMsg || "Este enlace ya fue usado o expiró.");
        setStatus("error");
      }
    }

    init();
  }, [token, router, setHousehold]);

  function handleRedirectToLogin() {
    localStorage.setItem("pending_invite_token", token);
    router.push(`/login?redirect=/invite/${token}`);
  }

  async function handleSwitchAccount() {
    const supabase = createClient();
    await supabase.auth.signOut();
    reset();
    localStorage.setItem("pending_invite_token", token);
    router.push(`/login?redirect=/invite/${token}`);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-luka-light px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="flex justify-center">
            <Image
              src="/logo.svg"
              alt="Luka Logo"
              width={150}
              height={50}
              className="h-16 w-auto"
              priority
            />
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center space-y-4 py-4">
          {(status === "checking" || status === "loading") && (
            <>
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-luka-primary border-t-transparent" />
              <p className="text-luka-muted text-sm">Uniéndote al grupo...</p>
            </>
          )}

          {status === "unauthenticated" && (
            <>
              <p className="text-center text-base font-semibold text-slate-800">
                Te han invitado a un grupo compartido
              </p>
              <p className="text-center text-sm text-slate-500">
                Inicia sesión o crea una cuenta para aceptar la invitación.
              </p>
              <Button
                onClick={handleRedirectToLogin}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                Ya tengo cuenta
              </Button>
              <Button
                variant="outline"
                onClick={handleRedirectToLogin}
                className="w-full"
              >
                Crear cuenta
              </Button>
            </>
          )}

          {status === "self-invite" && (
            <>
              <p className="text-center text-sm text-slate-700 font-medium">{errorMessage}</p>
              <p className="text-center text-xs text-slate-500">
                Este enlace es para otro miembro. Cambia de cuenta si necesitas.
              </p>
              <Button
                onClick={handleSwitchAccount}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                Cambiar de cuenta
              </Button>
              <Button
                variant="outline"
                onClick={() => router.push("/")}
                className="w-full"
              >
                Volver al inicio
              </Button>
            </>
          )}

          {status === "error" && (
            <>
              <p className="text-center text-sm text-luka-danger">{errorMessage}</p>
              <Button
                onClick={() => router.push("/login")}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                Iniciar sesión
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
