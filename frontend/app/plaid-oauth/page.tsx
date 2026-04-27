"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { usePlaidLink } from "react-plaid-link";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/app/lib/api";
import { PLAID_LINK_TOKEN_STORAGE_KEY } from "@/app/(dashboard)/settings/components/PlaidLinkButton";

// Plaid OAuth re-entry page. After the user authenticates at their bank
// (Chase / BofA / Wells / etc.), the bank redirects to cdn.plaid.com, which
// then redirects here. We re-open Plaid Link with the original link_token and
// the current URL as `receivedRedirectUri` so Plaid Link can resume the flow
// and fire onSuccess. See: https://plaid.com/docs/link/oauth/
export default function PlaidOAuthPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const receivedRedirectUri = useMemo(
    () => (typeof window !== "undefined" ? window.location.href : ""),
    []
  );

  useEffect(() => {
    try {
      const token = window.localStorage.getItem(PLAID_LINK_TOKEN_STORAGE_KEY);
      if (!token) {
        setError("No encontramos tu sesión de Plaid. Vuelve a Configuración e inténtalo de nuevo.");
        return;
      }
      setLinkToken(token);
    } catch {
      setError("Tu navegador bloqueó el almacenamiento local. Habilítalo e inténtalo de nuevo.");
    }
  }, []);

  const onSuccess = useCallback(
    async (publicToken: string, metadata: any) => {
      try {
        await api.exchangePlaidToken(
          publicToken,
          metadata.institution.institution_id,
          metadata.institution.name
        );
        queryClient.invalidateQueries({ queryKey: ["bank-accounts"] });
        queryClient.invalidateQueries({ queryKey: ["bank-connections"] });
        queryClient.invalidateQueries({ queryKey: ["plaid-items"] });
      } catch {
        setError("Error al vincular cuenta. Inténtalo de nuevo.");
      } finally {
        try {
          window.localStorage.removeItem(PLAID_LINK_TOKEN_STORAGE_KEY);
        } catch {}
        router.replace("/settings");
      }
    },
    [queryClient, router]
  );

  const onExit = useCallback(() => {
    try {
      window.localStorage.removeItem(PLAID_LINK_TOKEN_STORAGE_KEY);
    } catch {}
    router.replace("/settings");
  }, [router]);

  const { open, ready } = usePlaidLink({
    token: linkToken,
    receivedRedirectUri: linkToken ? receivedRedirectUri : undefined,
    onSuccess,
    onExit,
  });

  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
      <p className="text-sm text-muted-foreground">
        {error ?? "Terminando de vincular tu cuenta..."}
      </p>
      {error && (
        <button
          onClick={() => router.replace("/settings")}
          className="text-sm font-medium text-blue-600 underline-offset-4 hover:underline"
        >
          Volver a Configuración
        </button>
      )}
    </div>
  );
}
