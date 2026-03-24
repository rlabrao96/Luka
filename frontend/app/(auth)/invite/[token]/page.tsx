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

  const [status, setStatus] = useState<"loading" | "self-invite" | "error" | "success">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    async function tryAccept() {
      try {
        const data = await api.acceptInvite(token);
        setHousehold(data.household_id);
        setStatus("success");
        router.push("/");
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : "";

        // Not logged in — redirect to login with return URL
        if (errMsg.includes("401") || errMsg.includes("403") || errMsg.includes("Could not validate")) {
          router.push(`/login?redirect=/invite/${token}`);
          return;
        }

        // Self-invite — special UI with option to switch accounts
        if (errMsg.includes("propia invitación") || errMsg.includes("Ya eres miembro")) {
          setErrorMessage(errMsg);
          setStatus("self-invite");
          return;
        }

        setErrorMessage(errMsg || "Este enlace ya fue usado o expiró.");
        setStatus("error");
      }
    }
    tryAccept();
  }, [token, router, setHousehold]);

  async function handleSwitchAccount() {
    const supabase = createClient();
    await supabase.auth.signOut();
    reset();
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
          {status === "loading" && (
            <>
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-luka-primary border-t-transparent" />
              <p className="text-luka-muted text-sm">Uniéndote al hogar...</p>
            </>
          )}

          {status === "self-invite" && (
            <>
              <p className="text-center text-sm text-slate-700 font-medium">{errorMessage}</p>
              <p className="text-center text-xs text-slate-500">
                Abre este enlace en el navegador de tu pareja, o cambia de cuenta aquí.
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
