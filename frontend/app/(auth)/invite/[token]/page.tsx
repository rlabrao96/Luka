"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/app/lib/api";
import { useLukaStore } from "@/app/lib/store";

export default function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = React.use(params);
  const router = useRouter();
  const setHousehold = useLukaStore((s) => s.setHousehold);

  const [status, setStatus] = useState<"loading" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
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
        setErrorMessage(msg);
        setStatus("error");
      });
  }, [token, router, setHousehold]);

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
          {status === "loading" && (
            <>
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-luka-primary border-t-transparent" />
              <p className="text-luka-muted text-sm">Uniéndote al hogar...</p>
            </>
          )}
          {status === "error" && (
            <>
              <p className="text-center text-sm text-luka-danger">{errorMessage}</p>
              <Button
                onClick={() => router.push("/")}
                className="w-full bg-luka-primary hover:bg-blue-700"
              >
                Ir al inicio
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
