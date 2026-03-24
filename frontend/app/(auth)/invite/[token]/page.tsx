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

  const [status, setStatus] = useState<"signing-out" | "loading" | "error">("signing-out");
  const [errorMessage, setErrorMessage] = useState<string>("");

  // Step 1: Sign out any existing session so the partner logs in with their own account
  useEffect(() => {
    async function signOutAndRedirect() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();

      if (session) {
        // There's an active session — sign out first
        await supabase.auth.signOut();
        reset();
      }

      // Now try to accept (will fail with 401 if not logged in, which is expected)
      setStatus("loading");
    }
    signOutAndRedirect();
  }, [reset]);

  // Step 2: Once signed out, try to accept the invite
  useEffect(() => {
    if (status !== "loading") return;

    api
      .acceptInvite(token)
      .then((data) => {
        setHousehold(data.household_id);
        router.push("/");
      })
      .catch((err: unknown) => {
        const msg =
          err instanceof Error && err.message
            ? err.message
            : "Este enlace ya fue usado o expiró.";

        // If 401/403, user needs to log in first — redirect to login with return URL
        if (msg.includes("401") || msg.includes("403")) {
          router.push(`/login?redirect=/invite/${token}`);
          return;
        }

        setErrorMessage(msg);
        setStatus("error");
      });
  }, [token, router, setHousehold, status]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-luka-light">
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
          {(status === "signing-out" || status === "loading") && (
            <>
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-luka-primary border-t-transparent" />
              <p className="text-luka-muted text-sm">
                {status === "signing-out"
                  ? "Preparando sesión..."
                  : "Uniéndote al hogar..."}
              </p>
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
